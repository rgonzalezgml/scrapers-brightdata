"""Tests for the strategy-pattern plumbing in ``BaseScraperClient``.

These exercise:

    - Transport selection via ``API_MODE`` / ``api_mode=`` kwarg.
    - Mapping of ``TransportError`` (normalized code) to ``ScraperError``.
    - Error surfacing when no resource id is configured.
    - Behaviour of the ``dataset_id=`` backwards-compat alias.

We use a tiny ``_TestClient`` subclass so the base's abstract methods are
satisfied — the subclass only implements ``_build_brightdata_inputs`` and
``_build_envelope``, since those are the two abstract hooks.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from gli_scrapers.core.client import (
    DEFAULT_APIcore,
    DEFAULT_DCA_APIcore,
    BaseScraperClient,
)
from gli_scrapers.core.errors import ScraperError
from gli_scrapers.core.transports import (
    BaseTransport,
    DCATransport,
    V3Transport,
)

pytestmark = pytest.mark.asyncio


class _TestClient(BaseScraperClient):
    SOURCE_NAME = "_test-scraper"

    def _build_brightdata_inputs(self, public_inputs: Any) -> list[dict[str, Any]]:
        return [{"seed": 1}]

    def _build_envelope(
        self, rows: list[dict[str, Any]], public_inputs: dict[str, Any]
    ) -> dict[str, Any]:
        return {"source": self.SOURCE_NAME, "inputs": public_inputs, "data": rows, "meta": {}}


# ---------------------------------------------------------------------------
# transport selection
# ---------------------------------------------------------------------------


async def test_default_mode_selects_v3_transport() -> None:
    client = _TestClient(api_key="k", resource_id="gd_x")
    assert client.api_mode == "v3"
    assert isinstance(client._transport, V3Transport)
    assert client._apicore == DEFAULT_APIcore


async def test_api_mode_dca_selects_dca_transport() -> None:
    client = _TestClient(api_key="k", resource_id="c_x", api_mode="dca")
    assert client.api_mode == "dca"
    assert isinstance(client._transport, DCATransport)
    assert client._apicore == DEFAULT_DCA_APIcore


async def test_class_level_api_mode_override_picks_dca() -> None:
    class DCADefaultedClient(_TestClient):
        API_MODE = "dca"

    client = DCADefaultedClient(api_key="k", resource_id="c_x")
    assert client.api_mode == "dca"
    assert isinstance(client._transport, DCATransport)


async def test_unknown_api_mode_rejected_at_construction() -> None:
    with pytest.raises(ValueError):
        _TestClient(api_key="k", resource_id="x", api_mode="rest")  # type: ignore[arg-type]


async def test_dataset_id_alias_maps_to_resource_id() -> None:
    """``dataset_id=`` is a silent alias of ``resource_id=``."""
    client = _TestClient(api_key="k", dataset_id="gd_legacy")
    assert client.resource_id == "gd_legacy"
    assert client.api_mode == "v3"


async def test_explicit_resource_id_wins_over_dataset_id_alias() -> None:
    client = _TestClient(api_key="k", resource_id="gd_new", dataset_id="gd_old")
    assert client.resource_id == "gd_new"


# ---------------------------------------------------------------------------
# error mapping — transport → ScraperError
# ---------------------------------------------------------------------------


class _ForcedCodeTransport(BaseTransport):
    """Transport that raises a preset code on every call — for error mapping."""

    MODE = "_forced"

    def __init__(self, code: str, message: str = "forced", details: dict | None = None) -> None:
        from gli_scrapers.core.transports import TransportError as _TE

        self._exc = _TE(code, message, details=details)

    async def trigger(self, **_: Any) -> str:
        raise self._exc

    async def poll(self, **_: Any) -> dict[str, Any]:
        raise self._exc

    async def download(self, **_: Any) -> list[dict[str, Any]]:
        raise self._exc


async def test_transport_error_preserved_as_scraper_error() -> None:
    client = _TestClient(api_key="k", resource_id="x")
    client._transport = _ForcedCodeTransport(
        "BRIGHTDATA_ERROR", "boom", details={"body": "err"}
    )
    with pytest.raises(ScraperError) as exc_info:
        await client._trigger_brightdata([{"seed": 1}])
    assert exc_info.value.code == "BRIGHTDATA_ERROR"
    assert exc_info.value.message == "boom"
    assert exc_info.value.details == {"body": "err"}


@pytest.mark.parametrize(
    "code",
    ["BRIGHTDATA_ERROR", "INVALID_INPUTS", "SITE_BLOCKED"],
)
async def test_transport_error_codes_round_trip(code: str) -> None:
    client = _TestClient(api_key="k", resource_id="x")
    client._transport = _ForcedCodeTransport(code)
    with pytest.raises(ScraperError) as exc_info:
        await client._get_progress("job-xyz")
    assert exc_info.value.code == code


# ---------------------------------------------------------------------------
# resource id required at trigger time
# ---------------------------------------------------------------------------


async def test_resource_id_required_at_trigger_time() -> None:
    """Without a resource id, trigger raises INVALID_INPUTS (not at import)."""
    client = _TestClient(api_key="k")  # no resource_id
    with pytest.raises(ScraperError) as exc_info:
        await client._trigger_brightdata([{"seed": 1}])
    assert exc_info.value.code == "INVALID_INPUTS"


async def test_credential_hint_surfaces_both_env_vars() -> None:
    """Subclasses that set ``CREDENTIAL_HINT`` see that text in the error."""

    class _HintedClient(_TestClient):
        CREDENTIAL_HINT = (
            "Set one of:\n"
            "  FOO_DATASET_ID   (v3, gd_...)\n"
            "  FOO_COLLECTOR_ID (dca, c_...)"
        )

    client = _HintedClient(api_key="k")  # no resource_id
    with pytest.raises(ScraperError) as exc_info:
        await client._trigger_brightdata([{"seed": 1}])
    assert "FOO_DATASET_ID" in exc_info.value.message
    assert "FOO_COLLECTOR_ID" in exc_info.value.message


async def test_api_key_required_at_trigger_time(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BRIGHTDATA_API_KEY", raising=False)
    client = _TestClient(api_key=None, resource_id="x")
    with pytest.raises(ScraperError) as exc_info:
        await client._trigger_brightdata([{"seed": 1}])
    assert exc_info.value.code == "INVALID_INPUTS"
    assert "BRIGHTDATA_API_KEY" in exc_info.value.message


# ---------------------------------------------------------------------------
# end-to-end: custom transport inspected via ``_client()``
# ---------------------------------------------------------------------------


class _SpyTransport(BaseTransport):
    """Records the (apicore, resource_id, job_id) it saw on each call."""

    MODE = "_spy"

    def __init__(self) -> None:
        self.trigger_calls: list[dict] = []
        self.poll_calls: list[dict] = []
        self.download_calls: list[dict] = []

    async def trigger(self, **kwargs: Any) -> str:
        self.trigger_calls.append(kwargs)
        return "spy-job"

    async def poll(self, **kwargs: Any) -> dict[str, Any]:
        self.poll_calls.append(kwargs)
        return {"status": "ready"}

    async def download(self, **kwargs: Any) -> list[dict[str, Any]]:
        self.download_calls.append(kwargs)
        return [{"row": 1}]


async def testcore_client_threads_apicore_and_resource_id_to_transport() -> None:
    spy = _SpyTransport()
    client = _TestClient(api_key="k", resource_id="gd_x", api_mode="v3")
    client._transport = spy  # swap in the spy
    job_id = await client._trigger_brightdata([{"seed": 1}])
    assert job_id == "spy-job"
    assert spy.trigger_calls[0]["apicore"] == DEFAULT_APIcore
    assert spy.trigger_calls[0]["resource_id"] == "gd_x"
    assert spy.trigger_calls[0]["api_key"] == "k"
    rows = await client._fetch_snapshot(job_id)
    assert rows == [{"row": 1}]
    assert spy.download_calls[0]["job_id"] == "spy-job"


async def testcore_client_dca_mode_uses_dca_apicore() -> None:
    spy = _SpyTransport()
    client = _TestClient(api_key="k", resource_id="c_x", api_mode="dca")
    client._transport = spy
    await client._trigger_brightdata([{"seed": 1}])
    assert spy.trigger_calls[0]["apicore"] == DEFAULT_DCA_APIcore


async def testcore_client_external_http_client_not_closed() -> None:
    """If the caller passed in an ``http_client``, ``aclose`` must not close it."""
    async with httpx.AsyncClient() as external:
        client = _TestClient(api_key="k", resource_id="x", http_client=external)
        await client.aclose()
        # external is still usable (not closed).
        assert not external.is_closed
