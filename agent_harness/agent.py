"""Loop de tool-use — replica del patron en
``agents/01-motor-bi-conversacional/backend/app/core/agent.py`` de David.

El modelo recibe ``tools=TOOL_SCHEMA`` (declarado en el middleware), decide
cuando invocarlos, el dispatcher ejecuta las funciones Python y devuelve los
resultados como ``tool_result``. Repetir hasta ``stop_reason != 'tool_use'``.

Prompt caching: en produccion agregar ``cache_control`` al system prompt y al
array de tools (ambos son grandes + estables, saturan el precio por token).
Acá lo dejo fuera por simplicidad — ver skill `claude-api` para la receta.
"""

from __future__ import annotations

import json
import os
from typing import Any

import anthropic

from agent_harness.registry import ToolRegistry

MODEL = os.getenv("AGENT_MODEL", "claude-haiku-4-5-20251001")
MAX_TURNS = 10
MAX_TOKENS = 4096


class Agent:
    def __init__(
        self,
        api_key: str,
        tools: list[dict[str, Any]],
        registry: ToolRegistry,
        system_prompt: str,
    ) -> None:
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.tools = tools
        self.registry = registry
        self.system_prompt = system_prompt

    async def chat(
        self, messages: list[dict[str, Any]]
    ) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
        """Ejecuta el loop de tool-use sobre ``messages`` (mutable).

        Devuelve: (texto final del assistant, historial actualizado, trace de
        llamadas tool-use para debug).
        """
        trace: list[dict[str, Any]] = []

        for turn in range(MAX_TURNS):
            resp = await self.client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=self.system_prompt,
                tools=self.tools,
                messages=messages,
            )

            # Serializar la respuesta del assistant al historial.
            messages.append(
                {
                    "role": "assistant",
                    "content": _serialize_assistant_blocks(resp.content),
                }
            )

            if resp.stop_reason != "tool_use":
                text = "\n".join(b.text for b in resp.content if b.type == "text")
                return text, messages, trace

            # Ejecutar cada tool_use y armar el mensaje user con los tool_results.
            tool_result_blocks: list[dict[str, Any]] = []
            for block in resp.content:
                if block.type != "tool_use":
                    continue
                params = dict(block.input) if block.input else {}
                result = await self.registry.dispatch(block.name, params)
                trace.append(
                    {
                        "turn": turn,
                        "tool": block.name,
                        "input": params,
                        "output_keys": (
                            sorted(result.keys()) if isinstance(result, dict) else None
                        ),
                        "status": (
                            result.get("status") if isinstance(result, dict) else None
                        ),
                    }
                )
                tool_result_blocks.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, default=str, ensure_ascii=False),
                    }
                )

            messages.append({"role": "user", "content": tool_result_blocks})

        # Salvaguarda: si el modelo queda atascado pidiendo tools 10 veces.
        return "[harness: MAX_TURNS alcanzado sin end_turn]", messages, trace

    async def aclose(self) -> None:
        await self.client.close()


def _serialize_assistant_blocks(blocks: list[Any]) -> list[dict[str, Any]]:
    """Convierte los ContentBlock del SDK a dicts planos (para rehidratar en
    el siguiente messages.create)."""
    out: list[dict[str, Any]] = []
    for b in blocks:
        if b.type == "text":
            out.append({"type": "text", "text": b.text})
        elif b.type == "tool_use":
            out.append(
                {
                    "type": "tool_use",
                    "id": b.id,
                    "name": b.name,
                    "input": b.input,
                }
            )
    return out
