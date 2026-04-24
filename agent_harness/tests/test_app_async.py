"""Tests del contrato HTTP async: POST /chat + GET /chat/{id} + DELETE.

Stub del loop del LLM (`Agent.chat`) para evitar pegarle a Anthropic y para
controlar el timing (tarea running vs done). La lógica del dispatcher de
tools se valida en ``test_registry_live_polling.py``.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from agent_harness import app as app_module
from agent_harness.app import app


@pytest.fixture
def _set_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("AGENT_MODE", "fixture")


async def _async_client() -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    )


class _FakeAgent:
    """Stub de Agent que completa instantáneamente con un reply fijo."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    async def chat(
        self, messages: list[dict[str, Any]]
    ) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
        # Simular que el LLM respondió inmediatamente; extender history.
        updated = list(messages)
        updated.append({"role": "assistant", "content": [{"type": "text", "text": "ok-reply"}]})
        return "ok-reply", updated, [{"turn": 0, "tool": "fixture", "status": "done"}]

    async def aclose(self) -> None:
        return None


class _SlowAgent:
    """Stub de Agent que espera un evento externo antes de completar.

    Permite testear el estado 'running' y el DELETE mientras la task está
    viva.
    """

    release_event: asyncio.Event

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    async def chat(
        self, messages: list[dict[str, Any]]
    ) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
        await _SlowAgent.release_event.wait()
        updated = list(messages)
        updated.append({"role": "assistant", "content": [{"type": "text", "text": "slow-ok"}]})
        return "slow-ok", updated, []

    async def aclose(self) -> None:
        return None


async def test_post_chat_returns_202_with_session_id(
    _set_api_key: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(app_module, "Agent", _FakeAgent)

    async with await _async_client() as client:
        resp = await client.post("/chat", json={"message": "hola"})

    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "running"
    assert isinstance(body["session_id"], str) and body["session_id"]


async def test_get_chat_eventually_reports_done_with_reply(
    _set_api_key: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(app_module, "Agent", _FakeAgent)

    async with await _async_client() as client:
        post_resp = await client.post("/chat", json={"message": "hola"})
        sid = post_resp.json()["session_id"]

        # Esperar a que la task del _FakeAgent termine. Como es
        # instantánea, un await 0 alcanza; pero damos un pequeño margen.
        task = app_module._SESSIONS[sid]["task"]
        assert task is not None
        await task

        get_resp = await client.get(f"/chat/{sid}")

    assert get_resp.status_code == 200
    body = get_resp.json()
    assert body["session_id"] == sid
    assert body["status"] == "done"
    assert body["reply"] == "ok-reply"
    assert isinstance(body["trace"], list)
    assert body["error"] is None


async def test_get_chat_reports_running_before_task_completes(
    _set_api_key: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _SlowAgent.release_event = asyncio.Event()
    monkeypatch.setattr(app_module, "Agent", _SlowAgent)

    async with await _async_client() as client:
        post_resp = await client.post("/chat", json={"message": "hola"})
        sid = post_resp.json()["session_id"]

        # La task todavía no se liberó → status running.
        get_resp = await client.get(f"/chat/{sid}")
        assert get_resp.status_code == 200
        assert get_resp.json()["status"] == "running"
        assert get_resp.json()["reply"] is None

        # Liberar y esperar terminación.
        _SlowAgent.release_event.set()
        task = app_module._SESSIONS[sid]["task"]
        assert task is not None
        await task

        final = await client.get(f"/chat/{sid}")
        assert final.json()["status"] == "done"
        assert final.json()["reply"] == "slow-ok"


async def test_post_chat_on_busy_session_returns_409(
    _set_api_key: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _SlowAgent.release_event = asyncio.Event()
    monkeypatch.setattr(app_module, "Agent", _SlowAgent)

    async with await _async_client() as client:
        post_resp = await client.post("/chat", json={"message": "hola"})
        sid = post_resp.json()["session_id"]

        # Segundo POST con la misma sesión → 409.
        busy_resp = await client.post(
            "/chat", json={"message": "otra", "session_id": sid}
        )
        assert busy_resp.status_code == 409
        assert "busy" in busy_resp.json()["detail"].lower()

        _SlowAgent.release_event.set()
        task = app_module._SESSIONS[sid]["task"]
        assert task is not None
        await task


async def test_delete_session_cancels_running_task(
    _set_api_key: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _SlowAgent.release_event = asyncio.Event()
    monkeypatch.setattr(app_module, "Agent", _SlowAgent)

    async with await _async_client() as client:
        post_resp = await client.post("/chat", json={"message": "hola"})
        sid = post_resp.json()["session_id"]

        task = app_module._SESSIONS[sid]["task"]
        assert task is not None and not task.done()

        del_resp = await client.delete(f"/sessions/{sid}")
        assert del_resp.status_code == 200
        assert del_resp.json() == {"session_id": sid, "status": "cleared"}
        assert task.done() or task.cancelled()
        assert sid not in app_module._SESSIONS


async def test_post_chat_reuses_session_after_previous_turn_done(
    _set_api_key: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(app_module, "Agent", _FakeAgent)

    async with await _async_client() as client:
        first = await client.post("/chat", json={"message": "uno"})
        sid = first.json()["session_id"]
        await app_module._SESSIONS[sid]["task"]

        second = await client.post(
            "/chat", json={"message": "dos", "session_id": sid}
        )
        assert second.status_code == 202
        assert second.json()["session_id"] == sid
        await app_module._SESSIONS[sid]["task"]

        # History debe contener ambos mensajes del user + asistente por turno.
        hist = app_module._SESSIONS[sid]["history"]
        user_msgs = [m for m in hist if m["role"] == "user"]
        assert len(user_msgs) == 2
        assert user_msgs[0]["content"] == "uno"
        assert user_msgs[1]["content"] == "dos"


async def test_get_chat_unknown_session_returns_404(_set_api_key: None) -> None:
    async with await _async_client() as client:
        resp = await client.get("/chat/does-not-exist")
    assert resp.status_code == 404


async def test_post_chat_without_api_key_returns_500(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    async with await _async_client() as client:
        resp = await client.post("/chat", json={"message": "hola"})
    assert resp.status_code == 500


async def test_health_returns_mode_and_model(_set_api_key: None) -> None:
    async with await _async_client() as client:
        resp = await client.get("/health")
    body = resp.json()
    assert body["status"] == "ok"
    assert body["mode"] == "fixture"
    assert "model" in body
