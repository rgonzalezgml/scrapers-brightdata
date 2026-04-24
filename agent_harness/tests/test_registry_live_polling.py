"""Tests del wrapper de polling interno en live mode.

Valida:
- ``_live_get_result`` polea hasta que el middleware devuelve done.
- Si el middleware nunca termina, se dispara TIMEOUT después del wall-clock.
- ``_live_get_result`` propaga el resultado final sin modificarlo.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from agent_harness import registry as registry_module


async def test_live_get_result_polls_until_done() -> None:
    """Simula middleware que devuelve running 3 veces y done al 4to poll."""
    calls = {"n": 0}

    async def fake_poll(job_id: str) -> dict[str, Any]:
        calls["n"] += 1
        if calls["n"] < 4:
            return {"status": "running", "progress_pct": 25 * calls["n"]}
        return {
            "status": "done",
            "data": {"source": "cosmetics_design", "data": []},
        }

    async def fake_sleep(_s: float) -> None:
        return None  # no perder tiempo real en el test

    result = await registry_module._live_get_result(
        "job-xyz",
        poll_fn=fake_poll,
        interval_seconds=0.01,
        timeout_seconds=5.0,
        sleep=fake_sleep,
    )

    assert calls["n"] == 4
    assert result["status"] == "done"
    assert "data" in result


async def test_live_get_result_times_out_when_never_done() -> None:
    """Simula middleware que nunca devuelve done — debe reportar TIMEOUT."""
    calls = {"n": 0}

    async def fake_poll(job_id: str) -> dict[str, Any]:
        calls["n"] += 1
        return {"status": "running", "progress_pct": 10}

    async def fast_sleep(s: float) -> None:
        # Advance reloj monótono del event loop con await asyncio.sleep(0)
        # y confiar en el deadline real. Reducimos el timeout a 0.2s.
        await asyncio.sleep(s)

    result = await registry_module._live_get_result(
        "job-forever",
        poll_fn=fake_poll,
        interval_seconds=0.05,
        timeout_seconds=0.2,
        sleep=fast_sleep,
    )

    assert result["status"] == "failed"
    assert result["error"]["code"] == "TIMEOUT"
    assert "job-forever" in result["error"]["message"]
    assert result["error"]["retriable"] is True
    # Debería haber poleado varias veces antes del timeout.
    assert calls["n"] >= 2


async def test_live_get_result_returns_failed_immediately() -> None:
    """Si el primer poll ya devuelve failed, no poleamos más."""
    calls = {"n": 0}

    async def fake_poll(job_id: str) -> dict[str, Any]:
        calls["n"] += 1
        return {
            "status": "failed",
            "error": {"code": "SITE_BLOCKED", "message": "403", "retriable": False},
        }

    async def fake_sleep(_s: float) -> None:
        return None

    result = await registry_module._live_get_result(
        "job-fail",
        poll_fn=fake_poll,
        interval_seconds=0.01,
        timeout_seconds=5.0,
        sleep=fake_sleep,
    )

    assert calls["n"] == 1
    assert result["status"] == "failed"
    assert result["error"]["code"] == "SITE_BLOCKED"


async def test_live_poll_defaults_read_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Los defaults vienen de env vars si están seteadas."""
    monkeypatch.setenv("LIVE_POLL_INTERVAL_SECONDS", "7.5")
    monkeypatch.setenv("LIVE_POLL_TIMEOUT_SECONDS", "123")
    assert registry_module._live_poll_interval_seconds() == 7.5
    assert registry_module._live_poll_timeout_seconds() == 123.0

    monkeypatch.delenv("LIVE_POLL_INTERVAL_SECONDS", raising=False)
    monkeypatch.delenv("LIVE_POLL_TIMEOUT_SECONDS", raising=False)
    assert registry_module._live_poll_interval_seconds() == 30.0
    assert registry_module._live_poll_timeout_seconds() == 1800.0


async def test_build_registry_live_mode_registers_wrapped_get_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """En live mode, el registry despacha a _live_get_result (que polea)."""
    monkeypatch.setenv("AGENT_MODE", "live")

    r = registry_module.build_registry()
    assert "cosmetics_design_get_result" in r._tools
    # Usamos el nombre qualname del módulo para confirmar que es el wrapper
    # async correcto — el fixture dispatcher se llama _fixture_get_result.
    assert r._tools["cosmetics_design_get_result"] is registry_module._live_get_result


async def test_build_registry_fixture_mode_registers_fixture_get_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_MODE", "fixture")
    r = registry_module.build_registry()
    assert r._tools["cosmetics_design_get_result"] is registry_module._fixture_get_result
