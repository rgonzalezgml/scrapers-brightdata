"""FastAPI mirror del backend de agente de David — patrón HTTP async.

El loop del LLM puede tardar minutos (en live mode, el middleware polea
BrightData durante 10-30 min). Un ``POST /chat`` que bloquee hasta tener la
respuesta final sobrepasa los timeouts de Swagger / uvicorn / proxies. Por eso
el contrato es HTTP polling:

    POST   /chat                    -> 202 {session_id, status: "running"}
    GET    /chat/{session_id}       -> 200 {session_id, status: "running"}
                                   | 200 {session_id, status: "done", reply, trace}
                                   | 200 {session_id, status: "failed", error: {...}}
    DELETE /sessions/{session_id}   -> 200 {session_id, status: "cleared"}
    GET    /health                  -> 200 {status, mode, model}
    GET    /middlewares             -> 200 [{name, tools: [...]}, ...]

Selector de middleware
----------------------
``POST /chat`` acepta el campo ``middleware`` con el scraper elegido. Los
valores posibles se descubren al arranque desde ``middlewares/`` (todos los
paquetes que exporten ``TOOL_SCHEMA``, ``trigger``, ``get_result``). Swagger
renderiza un dropdown porque el tipo es un ``Enum`` dinámico.

El primer turno de una sesión fija el middleware: pedir otro middleware con
el mismo ``session_id`` responde 409. El default es ``cosmetics_design`` (si
existe) o el primero alfabético.

Reglas generales
----------------
- Cada sesión mantiene su ``history`` (compartido entre turnos) + el ``Task``
  actualmente en ejecución (si lo hay) + el último resultado terminal + el
  ``middleware`` al que quedó "pinned".
- ``POST /chat`` arranca una tarea en background y vuelve inmediatamente.
- Si se llama ``POST /chat`` con un ``session_id`` cuya tarea aún está
  ``running`` → 409. No encolamos mensajes.
- Si la tarea anterior terminó (done/failed), un nuevo ``POST`` extiende el
  history y arranca una tarea nueva sobre él.
- ``DELETE /sessions/{id}`` cancela la tarea activa si la hay y olvida la
  sesión.

Sesiones en memoria (dict) — suficiente para el harness local.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from enum import Enum
from typing import Any, Literal, TypedDict

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from agent_harness.agent import Agent
from agent_harness.registry import (
    AVAILABLE_MIDDLEWARES,
    build_registry,
    build_tool_schema,
)

load_dotenv()


# -----------------------------------------------------------------------------
# Middleware enum (dinámico) — para que FastAPI renderice un dropdown.
# -----------------------------------------------------------------------------

if not AVAILABLE_MIDDLEWARES:
    # Estado imposible en condiciones normales: el paquete ``middlewares/``
    # no expuso ningún wrapper. Seguimos arrancando para no romper el import
    # del app pero marcamos un placeholder que falla en runtime.
    _ENUM_MEMBERS = {"__none__": "__none__"}
else:
    _ENUM_MEMBERS = {name: name for name in AVAILABLE_MIDDLEWARES}

MiddlewareEnum: type[Enum] = Enum(  # type: ignore[assignment]
    "MiddlewareEnum",
    _ENUM_MEMBERS,
    type=str,
)

_DEFAULT_MIDDLEWARE = (
    "cosmetics_design"
    if "cosmetics_design" in AVAILABLE_MIDDLEWARES
    else (AVAILABLE_MIDDLEWARES[0] if AVAILABLE_MIDDLEWARES else "__none__")
)
_DEFAULT_MIDDLEWARE_ENUM = MiddlewareEnum(_DEFAULT_MIDDLEWARE)


# -----------------------------------------------------------------------------
# System prompts por middleware
# -----------------------------------------------------------------------------

_GENERIC_SYSTEM_PROMPT = (
    "Eres un asistente que ayuda a consultar un scraper de BrightData "
    "llamado {source_name!r}.\n\n"
    "Cuando el usuario pida datos:\n"
    "  1. Llama a {trigger_name} con los parametros apropiados.\n"
    "  2. Recibiras un job_id + eta_seconds.\n"
    "  3. Llama a {get_result_name}(job_id). En modo live, esa llamada\n"
    "     bloquea internamente hasta que el run termine (done o failed),\n"
    "     asi que NO necesitas reintentarla.\n"
    "  4. Sintetiza las rows del envelope data[] en espanol.\n\n"
    "Si status='failed', explica el error al usuario sin inventar datos."
)

_SYSTEM_PROMPTS: dict[str, str] = {
    "cosmetics_design": (
        "Eres un asistente de I+D cosmetico de Genomma Lab. Tienes acceso al "
        "scraper 'cosmetics_design' (nutraingredients.com / William Reed) "
        "para buscar noticias de la industria: formulacion, ingredientes, "
        "claims, regulacion, lanzamientos.\n\n"
        "Cuando el usuario pida informacion del scraper:\n"
        "  1. Llama a cosmetics_design_trigger con los parametros apropiados.\n"
        "  2. Recibiras un job_id + eta_seconds.\n"
        "  3. Llama a cosmetics_design_get_result(job_id). En modo live, esa "
        "     llamada bloquea internamente hasta que el run termine (done o "
        "     failed), asi que NO necesitas reintentarla.\n"
        "  4. Sintetiza los articulos del envelope data[] en espanol.\n\n"
        "Si status='failed', explica el error al usuario sin inventar datos."
    ),
}


def _system_prompt_for(middleware: str) -> str:
    """Devuelve el prompt específico del middleware o uno genérico."""
    prompt = _SYSTEM_PROMPTS.get(middleware)
    if prompt is not None:
        return prompt
    return _GENERIC_SYSTEM_PROMPT.format(
        source_name=middleware,
        trigger_name=f"{middleware}_trigger",
        get_result_name=f"{middleware}_get_result",
    )


# -----------------------------------------------------------------------------
# Session store
# -----------------------------------------------------------------------------


class Session(TypedDict):
    history: list[dict[str, Any]]
    task: asyncio.Task[Any] | None
    status: Literal["running", "done", "failed"]
    reply: str | None
    trace: list[dict[str, Any]] | None
    error: dict[str, Any] | None
    middleware: str


# Session store minimal. El agente real usa RDS; acá basta un dict.
_SESSIONS: dict[str, Session] = {}


# -----------------------------------------------------------------------------
# Request / response models
# -----------------------------------------------------------------------------


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    middleware: MiddlewareEnum = Field(  # type: ignore[valid-type]
        default=_DEFAULT_MIDDLEWARE_ENUM,
        description=(
            "Scraper middleware to use for this turn. Only the tools of the "
            "selected middleware are exposed to the LLM. The first turn of a "
            "session pins the choice; subsequent turns must send the same "
            "value or omit it."
        ),
    )


class ChatAcceptedResponse(BaseModel):
    session_id: str
    status: Literal["running"] = "running"
    middleware: str


class ChatStatusResponse(BaseModel):
    session_id: str
    status: Literal["running", "done", "failed"]
    middleware: str
    reply: str | None = None
    trace: list[dict[str, Any]] | None = None
    error: dict[str, Any] | None = None


class MiddlewareDescriptor(BaseModel):
    name: str
    tools: list[str]


# -----------------------------------------------------------------------------
# App
# -----------------------------------------------------------------------------

app = FastAPI(title="Agent harness — BrightData scrapers (HTTP async)")


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "mode": os.getenv("AGENT_MODE", "fixture").lower(),
        "model": "claude-opus-4-7",
        "middlewares": list(AVAILABLE_MIDDLEWARES),
        "default_middleware": _DEFAULT_MIDDLEWARE,
    }


@app.get("/middlewares", response_model=list[MiddlewareDescriptor])
async def list_middlewares() -> list[MiddlewareDescriptor]:
    """Lista los middlewares disponibles con sus tools."""
    out: list[MiddlewareDescriptor] = []
    for name in AVAILABLE_MIDDLEWARES:
        try:
            schema = build_tool_schema(name)
            tools = [t["name"] for t in schema if isinstance(t, dict) and "name" in t]
        except Exception:  # noqa: BLE001
            tools = []
        out.append(MiddlewareDescriptor(name=name, tools=tools))
    return out


async def _run_agent_turn(session_id: str, api_key: str) -> None:
    """Ejecuta un turno del agente sobre el history actual de la sesión.

    Vive como asyncio.Task en background. Al terminar deja la sesión en
    ``done`` o ``failed``; no devuelve nada. Si la task es cancelada
    (DELETE /sessions/{id}) dejamos la sesión en ``failed`` con CANCELLED
    — pero típicamente el delete ya quitó la entrada de ``_SESSIONS``.
    """
    session = _SESSIONS.get(session_id)
    if session is None:
        return

    middleware = session["middleware"]
    agent = Agent(
        api_key=api_key,
        tools=build_tool_schema(middleware),
        registry=build_registry(middleware),
        system_prompt=_system_prompt_for(middleware),
    )
    try:
        reply, updated_history, trace = await agent.chat(session["history"])
    except asyncio.CancelledError:
        current = _SESSIONS.get(session_id)
        if current is not None:
            current["status"] = "failed"
            current["error"] = {
                "code": "CANCELLED",
                "message": "session task cancelled",
            }
        raise
    except Exception as e:  # noqa: BLE001
        current = _SESSIONS.get(session_id)
        if current is not None:
            current["status"] = "failed"
            current["error"] = {
                "code": "AGENT_ERROR",
                "message": f"{type(e).__name__}: {e}",
            }
        return
    finally:
        await agent.aclose()

    current = _SESSIONS.get(session_id)
    if current is None:
        return
    current["history"] = updated_history
    current["reply"] = reply
    current["trace"] = trace
    current["error"] = None
    current["status"] = "done"


@app.post("/chat", status_code=202, response_model=ChatAcceptedResponse)
async def chat(req: ChatRequest) -> JSONResponse:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="ANTHROPIC_API_KEY no esta configurada en el entorno.",
        )

    requested_middleware = req.middleware.value
    session_id = req.session_id or str(uuid.uuid4())
    session = _SESSIONS.get(session_id)

    if session is None:
        session = Session(
            history=[],
            task=None,
            status="running",
            reply=None,
            trace=None,
            error=None,
            middleware=requested_middleware,
        )
        _SESSIONS[session_id] = session
    else:
        # Session pinned al middleware del primer turno.
        if session["middleware"] != requested_middleware:
            raise HTTPException(
                status_code=409,
                detail=f"session bound to {session['middleware']}",
            )
        # Si ya hay una task corriendo, rechazar: no encolamos.
        task = session["task"]
        if task is not None and not task.done():
            raise HTTPException(
                status_code=409,
                detail=f"session busy, poll GET /chat/{session_id}",
            )

    # Extender el historial con el mensaje del usuario y resetear estado.
    session["history"].append({"role": "user", "content": req.message})
    session["status"] = "running"
    session["reply"] = None
    session["trace"] = None
    session["error"] = None

    session["task"] = asyncio.create_task(
        _run_agent_turn(session_id, api_key),
        name=f"agent-turn-{session_id}",
    )

    return JSONResponse(
        status_code=202,
        content={
            "session_id": session_id,
            "status": "running",
            "middleware": session["middleware"],
        },
    )


@app.get("/chat/{session_id}", response_model=ChatStatusResponse)
async def get_chat(session_id: str) -> ChatStatusResponse:
    session = _SESSIONS.get(session_id)
    if session is None:
        raise HTTPException(
            status_code=404,
            detail=f"unknown session_id: {session_id}",
        )
    return ChatStatusResponse(
        session_id=session_id,
        status=session["status"],
        middleware=session["middleware"],
        reply=session["reply"],
        trace=session["trace"],
        error=session["error"],
    )


@app.delete("/sessions/{session_id}")
async def clear_session(session_id: str) -> dict[str, str]:
    session = _SESSIONS.pop(session_id, None)
    if session is None:
        return {"session_id": session_id, "status": "cleared"}
    task = session["task"]
    if task is not None and not task.done():
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass
    return {"session_id": session_id, "status": "cleared"}
