"""Tests para la selección de middleware en ``POST /chat``.

Cubre:
- POST /chat sin campo ``middleware`` usa el default (cosmetics_design).
- POST /chat con ``middleware=<name>`` despacha los tools correctos al Agent.
- POST /chat con un middleware desconocido → 422 (pydantic Enum).
- Reusar un ``session_id`` con otro middleware → 409.
- GET /middlewares devuelve los 6 middlewares con sus tools.
- En fixture mode cada middleware devuelve un envelope consistente con su
  propio snapshot.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from agent_harness import app as app_module
from agent_harness import registry as registry_module
from agent_harness.app import app

ALL_MIDDLEWARES = (
    "alibaba",
    "cosme",
    "cosmetics_design",
    "indiamart",
    "made_in_china",
    "olive_young",
)


@pytest.fixture
def _set_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("AGENT_MODE", "fixture")


async def _async_client() -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    )


class _RecordingAgent:
    """Stub de Agent que captura los tools que le pasaron + responde instant."""

    # Donde el test va a encontrar lo observado.
    last_tools: list[dict[str, Any]] = []
    last_system_prompt: str = ""
    last_registry_tools: list[str] = []

    def __init__(
        self,
        *,
        api_key: str,
        tools: list[dict[str, Any]],
        registry: Any,
        system_prompt: str,
    ) -> None:
        _RecordingAgent.last_tools = tools
        _RecordingAgent.last_system_prompt = system_prompt
        _RecordingAgent.last_registry_tools = sorted(registry._tools.keys())

    async def chat(
        self, messages: list[dict[str, Any]]
    ) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
        updated = list(messages)
        updated.append(
            {"role": "assistant", "content": [{"type": "text", "text": "ok"}]}
        )
        return "ok", updated, []

    async def aclose(self) -> None:
        return None


# -----------------------------------------------------------------------------
# Dropdown / enum
# -----------------------------------------------------------------------------


async def test_get_middlewares_lists_all_with_tools(_set_api_key: None) -> None:
    async with await _async_client() as client:
        resp = await client.get("/middlewares")

    assert resp.status_code == 200
    body = resp.json()
    names = [item["name"] for item in body]

    for expected in ALL_MIDDLEWARES:
        assert expected in names, f"{expected!r} not in {names}"

    for item in body:
        assert isinstance(item["tools"], list)
        assert f"{item['name']}_trigger" in item["tools"]
        assert f"{item['name']}_get_result" in item["tools"]


async def test_health_includes_middleware_catalog(_set_api_key: None) -> None:
    async with await _async_client() as client:
        resp = await client.get("/health")
    body = resp.json()
    for expected in ALL_MIDDLEWARES:
        assert expected in body["middlewares"]
    assert body["default_middleware"] == "cosmetics_design"


# -----------------------------------------------------------------------------
# Default cuando no se especifica middleware
# -----------------------------------------------------------------------------


async def test_post_chat_without_middleware_uses_cosmetics_design_default(
    _set_api_key: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(app_module, "Agent", _RecordingAgent)

    async with await _async_client() as client:
        resp = await client.post("/chat", json={"message": "hola"})

    assert resp.status_code == 202
    body = resp.json()
    assert body["middleware"] == "cosmetics_design"

    # Esperar a que la task corra una vez para observar qué tools le pasó el
    # app al Agent.
    sid = body["session_id"]
    task = app_module._SESSIONS[sid]["task"]
    assert task is not None
    await task

    tool_names = {t["name"] for t in _RecordingAgent.last_tools}
    assert tool_names == {
        "cosmetics_design_trigger",
        "cosmetics_design_get_result",
    }
    assert set(_RecordingAgent.last_registry_tools) == tool_names


# -----------------------------------------------------------------------------
# Selección explícita
# -----------------------------------------------------------------------------


@pytest.mark.parametrize("middleware", ALL_MIDDLEWARES)
async def test_post_chat_with_middleware_dispatches_matching_tools(
    middleware: str, _set_api_key: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(app_module, "Agent", _RecordingAgent)

    async with await _async_client() as client:
        resp = await client.post(
            "/chat",
            json={"message": "hola", "middleware": middleware},
        )

    assert resp.status_code == 202
    body = resp.json()
    assert body["middleware"] == middleware

    sid = body["session_id"]
    task = app_module._SESSIONS[sid]["task"]
    assert task is not None
    await task

    expected_tools = {f"{middleware}_trigger", f"{middleware}_get_result"}
    tool_names = {t["name"] for t in _RecordingAgent.last_tools}
    assert tool_names == expected_tools
    assert set(_RecordingAgent.last_registry_tools) == expected_tools


# -----------------------------------------------------------------------------
# Validación de input
# -----------------------------------------------------------------------------


async def test_post_chat_with_unknown_middleware_returns_422(
    _set_api_key: None,
) -> None:
    async with await _async_client() as client:
        resp = await client.post(
            "/chat",
            json={"message": "hola", "middleware": "does_not_exist"},
        )
    assert resp.status_code == 422


# -----------------------------------------------------------------------------
# Session pinning
# -----------------------------------------------------------------------------


async def test_post_chat_changing_middleware_midsession_returns_409(
    _set_api_key: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(app_module, "Agent", _RecordingAgent)

    async with await _async_client() as client:
        first = await client.post(
            "/chat",
            json={"message": "uno", "middleware": "cosme"},
        )
        assert first.status_code == 202
        sid = first.json()["session_id"]
        await app_module._SESSIONS[sid]["task"]

        second = await client.post(
            "/chat",
            json={
                "message": "dos",
                "session_id": sid,
                "middleware": "alibaba",
            },
        )

    assert second.status_code == 409
    assert "bound to cosme" in second.json()["detail"]


async def test_post_chat_same_middleware_on_existing_session_ok(
    _set_api_key: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(app_module, "Agent", _RecordingAgent)

    async with await _async_client() as client:
        first = await client.post(
            "/chat",
            json={"message": "uno", "middleware": "alibaba"},
        )
        sid = first.json()["session_id"]
        await app_module._SESSIONS[sid]["task"]

        second = await client.post(
            "/chat",
            json={
                "message": "dos",
                "session_id": sid,
                "middleware": "alibaba",
            },
        )
    assert second.status_code == 202
    assert second.json()["middleware"] == "alibaba"


# -----------------------------------------------------------------------------
# GET /chat/{id} devuelve middleware
# -----------------------------------------------------------------------------


async def test_get_chat_includes_middleware_field(
    _set_api_key: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(app_module, "Agent", _RecordingAgent)

    async with await _async_client() as client:
        resp = await client.post(
            "/chat",
            json={"message": "hola", "middleware": "olive_young"},
        )
        sid = resp.json()["session_id"]
        await app_module._SESSIONS[sid]["task"]

        get_resp = await client.get(f"/chat/{sid}")

    assert get_resp.status_code == 200
    body = get_resp.json()
    assert body["middleware"] == "olive_young"
    assert body["status"] == "done"


# -----------------------------------------------------------------------------
# Fixture mode end-to-end — el trigger/get_result de cada middleware levanta
# su propio snapshot.
# -----------------------------------------------------------------------------


@pytest.mark.parametrize("middleware", ALL_MIDDLEWARES)
async def test_fixture_registry_for_each_middleware_returns_consistent_envelope(
    middleware: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AGENT_MODE", "fixture")
    registry_module.reset_fixture_state()

    r = registry_module.build_registry(middleware)
    trigger_name = f"{middleware}_trigger"
    get_result_name = f"{middleware}_get_result"

    assert set(r._tools.keys()) == {trigger_name, get_result_name}

    trig = await r.dispatch(trigger_name, {})
    assert "job_id" in trig, f"trigger for {middleware} did not return job_id: {trig}"
    job_id = trig["job_id"]

    # Primer poll: running.
    first = await r.dispatch(get_result_name, {"job_id": job_id})
    assert first["status"] == "running"
    assert first["progress_pct"] == 40

    # Segundo poll: done (o failed si el middleware no tiene fixture — no
    # debería pasar con los 6 oficiales pero si pasa, lo reportamos).
    final = await r.dispatch(get_result_name, {"job_id": job_id})
    assert final["status"] == "done", f"{middleware}: {final}"

    env = final["data"]
    # El source del envelope coincide con el middleware (el SOURCE_NAME de
    # cada client coincide con su clave; ver docs/specs/scrapers/<name>.md).
    # Comparamos en lower-case por tolerancia (algunos source names usan
    # guión — cosmetics_design vs cosmetics-design).
    source = str(env.get("source", "")).lower().replace("-", "_")
    assert middleware in source or source in middleware, (
        f"envelope.source={env.get('source')!r} inconsistente con {middleware}"
    )
    assert isinstance(env.get("data"), list)


# -----------------------------------------------------------------------------
# Fixture missing path
# -----------------------------------------------------------------------------


async def test_fixture_missing_returns_failed_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Si el fixture no existe, trigger responde con FIXTURE_MISSING."""
    # Simulamos forzando el lookup sobre un middleware que no existe via
    # el helper de bajo nivel.
    result = registry_module._fixture_for("__definitely_not_a_middleware__")
    assert result["status"] == "failed"
    assert result["error"]["code"] == "FIXTURE_MISSING"
