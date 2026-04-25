"""Unit + fixture tests for the ``impi`` middleware.

These tests never hit the real IMPI portal — the ``IMPIClient.search`` call
is mocked via ``client_factory`` injection (see
``IMPIMiddlewareClient.__init__``).

NOTE on imports: we do NOT ``from impi_scraper_mx import ...`` at module
top-level. The ``gli_scrapers/impi/conftest.py`` mirrors the production
package-path guard before tests import the standalone package.

Coverage map:
    - test_trigger_happy_path            — mock scraper returns rows; envelope populated
    - test_get_result_unknown_job_id     — unknown id → INVALID_INPUTS
    - test_get_result_empty_job_id       — empty string job_id → INVALID_INPUTS
    - test_trigger_xsrf_missing          — scraper raises XSRFMissingError → BRIGHTDATA_ERROR
    - test_trigger_unexpected_exception  — scraper raises RuntimeError → BRIGHTDATA_ERROR
    - test_trigger_validates_inputs      — owner="" → INVALID_INPUTS (no scraper call)
    - test_trigger_unknown_input_key     — extra="forbid" → INVALID_INPUTS
    - test_envelope_shape                — canonical Envelope keys + meta extras
    - test_envelope_shape_via_fixture    — build_envelope_for_rows from snapshot
    - test_tool_schema                    — two tools with expected names/fields
    - test_build_envelope_for_rows_empty — empty list → envelope with meta.rows=0
    - test_module_level_trigger_and_get  — trigger/get_result convenience helpers
    - test_harness_discovery             — TOOL_SCHEMA, trigger, get_result exported
"""

from __future__ import annotations

from typing import Any

import pytest

from gli_scrapers.core.envelope import Envelope
from gli_scrapers.impi import (
    TOOL_SCHEMA,
    IMPIInputs,
    IMPIMiddlewareClient,
    get_result,
    trigger,
)


# ----------------------------------------------------------------------------
# Lazy accessors for the standalone ``impi_scraper_mx`` package.
# ----------------------------------------------------------------------------


def _ensure_impi_scraper_mx_path() -> None:
    """Delegate to the middleware's own package-path guard.

    Defined in ``gli_scrapers.impi.client`` — kept there so the production
    code path is self-healing without needing test fixtures.
    """
    from gli_scrapers.impi.client import (
        _ensure_impi_scraper_mx_path as _fix,
    )

    _fix()


def _Marca() -> type:
    _ensure_impi_scraper_mx_path()
    from impi_scraper_mx import Marca

    return Marca


def _SearchResult() -> type:
    _ensure_impi_scraper_mx_path()
    from impi_scraper_mx import SearchResult

    return SearchResult


def _XSRFMissingError() -> type[BaseException]:
    _ensure_impi_scraper_mx_path()
    from impi_scraper_mx.errors import XSRFMissingError

    return XSRFMissingError


pytestmark = pytest.mark.asyncio


# ----------------------------------------------------------------------------
# Helpers: build a fake IMPIClient factory for the middleware
# ----------------------------------------------------------------------------


def _build_fake_factory(
    rows: list[Any] | None = None,
    *,
    total: int | None = None,
    search_id: str = "search-fake-123",
    paginated: bool = False,
    raise_on_search: Exception | None = None,
) -> Any:
    """Return a ``client_factory`` callable suitable for
    ``IMPIMiddlewareClient(client_factory=...)``.

    The factory yields a minimal stub with just a ``search`` method that
    returns a pre-canned ``SearchResult`` (or raises).
    """
    rows = rows or []
    SearchResult = _SearchResult()

    class _Fake:
        def search(self, inputs):  # type: ignore[no-untyped-def]
            if raise_on_search is not None:
                raise raise_on_search
            return SearchResult(
                rows=rows,
                total=total if total is not None else len(rows),
                search_id=search_id,
                fetched=len(rows),
                pages=2 if paginated else 1,
            )

    def _factory() -> _Fake:
        return _Fake()

    return _factory


def _make_marca(denominacion: str = "TAFIROL", **overrides: Any) -> Any:
    """Build a Marca with sensible defaults — override any field via kwargs."""
    Marca = _Marca()
    base: dict[str, Any] = dict(
        denominacion=denominacion,
        expediente="1234567",
        registro="REG-2020-001",
        titular="GENOMMA LAB INTERNACIONAL S.A.B. DE C.V.",
        fecha_terminacion="2026-06-15",
        fecha_cancelacion=None,
        fecha_solicitud="2016-06-15",
        imagen=None,
        scraped_date="2026-04-22",
        scraper_flags=[],
    )
    base.update(overrides)
    return Marca(**base)


# ----------------------------------------------------------------------------
# Happy path
# ----------------------------------------------------------------------------


async def test_trigger_happy_path() -> None:
    """Mock scraper returns 3 Marcas → envelope stored, get_result returns it."""
    rows = [
        _make_marca("TAFIROL"),
        _make_marca("SUERO-BEBE", expediente="2222"),
        _make_marca("OXISEPT", expediente="3333"),
    ]
    factory = _build_fake_factory(rows, total=3, search_id="search-abc")
    client = IMPIMiddlewareClient(client_factory=factory)

    job = await client.trigger({"owner": "Genomma", "expires_within_days": 90})

    assert isinstance(job, dict)
    assert job["eta_seconds"] == 0
    assert job["job_id"].startswith("local_impi_")
    assert len(job["job_id"]) > len("local_impi_")  # uuid suffix present.

    res = await client.get_result(job["job_id"])
    assert res["status"] == "done"
    env = res["data"]
    assert env["source"] == "impi"
    assert len(env["data"]) == 3
    # Inputs echoed back with defaults applied.
    assert env["inputs"]["owner"] == "Genomma"
    assert env["inputs"]["expires_within_days"] == 90
    assert env["inputs"]["page_size"] == 50  # default
    assert env["inputs"]["mode"] == "incremental"  # default
    # meta has the extra impi-specific keys.
    assert env["meta"]["rows"] == 3
    assert env["meta"]["emitted"] == 3
    assert env["meta"]["total_in_portal"] == 3
    assert env["meta"]["search_id"] == "search-abc"
    assert env["meta"]["paginated"] is False
    assert env["meta"]["errors"] == 0


# ----------------------------------------------------------------------------
# get_result failure paths
# ----------------------------------------------------------------------------


async def test_get_result_unknown_job_id() -> None:
    """Unknown job_id → INVALID_INPUTS failure (never raises)."""
    client = IMPIMiddlewareClient(client_factory=_build_fake_factory())
    res = await client.get_result("no-existe")
    assert res["status"] == "failed"
    assert res["error"]["code"] == "INVALID_INPUTS"
    assert res["error"]["retriable"] is False
    assert "no-existe" in res["error"]["message"]


async def test_get_result_empty_job_id() -> None:
    """Empty string job_id → INVALID_INPUTS (never raises)."""
    client = IMPIMiddlewareClient(client_factory=_build_fake_factory())
    res = await client.get_result("")
    assert res["status"] == "failed"
    assert res["error"]["code"] == "INVALID_INPUTS"


# ----------------------------------------------------------------------------
# Error paths from the underlying scraper
# ----------------------------------------------------------------------------


async def test_trigger_xsrf_missing() -> None:
    """``XSRFMissingError`` surfaces as BRIGHTDATA_ERROR (retriable=True).

    trigger still returns a job_id so the caller polls uniformly; get_result
    reveals the failure.
    """
    XSRFMissingError = _XSRFMissingError()
    factory = _build_fake_factory(
        raise_on_search=XSRFMissingError("cookie missing"),
    )
    client = IMPIMiddlewareClient(client_factory=factory)
    job = await client.trigger({"owner": "Genomma"})

    assert "job_id" in job
    assert job["eta_seconds"] == 0

    res = await client.get_result(job["job_id"])
    assert res["status"] == "failed"
    assert res["error"]["code"] == "BRIGHTDATA_ERROR"
    assert res["error"]["retriable"] is True
    assert "XSRFMissingError" in res["error"]["message"]


async def test_trigger_unexpected_exception() -> None:
    """Non-IMPI exceptions bucket into BRIGHTDATA_ERROR (retriable=False)."""
    factory = _build_fake_factory(
        raise_on_search=RuntimeError("totally unexpected"),
    )
    client = IMPIMiddlewareClient(client_factory=factory)
    job = await client.trigger({"owner": "Genomma"})
    res = await client.get_result(job["job_id"])
    assert res["status"] == "failed"
    assert res["error"]["code"] == "BRIGHTDATA_ERROR"
    assert res["error"]["retriable"] is False
    assert "RuntimeError" in res["error"]["message"]


# ----------------------------------------------------------------------------
# Input validation paths (never calls the scraper)
# ----------------------------------------------------------------------------


async def test_trigger_validates_inputs() -> None:
    """``owner=""`` fails pydantic validation (min_length=1) → INVALID_INPUTS.

    The scraper is NOT called — we assert this by giving a factory that would
    raise if invoked.
    """
    calls = {"n": 0}

    class _Spy:
        def search(self, inputs):  # type: ignore[no-untyped-def]
            calls["n"] += 1
            raise AssertionError("scraper should not be called on invalid inputs")

    client = IMPIMiddlewareClient(client_factory=lambda: _Spy())
    job = await client.trigger({"owner": ""})
    assert job["eta_seconds"] == 0

    res = await client.get_result(job["job_id"])
    assert res["status"] == "failed"
    assert res["error"]["code"] == "INVALID_INPUTS"
    assert calls["n"] == 0


async def test_trigger_unknown_input_key() -> None:
    """``extra='forbid'`` rejects unknown keys → INVALID_INPUTS."""
    client = IMPIMiddlewareClient(client_factory=_build_fake_factory())
    job = await client.trigger({"not_a_real_input": True})
    res = await client.get_result(job["job_id"])
    assert res["status"] == "failed"
    assert res["error"]["code"] == "INVALID_INPUTS"


async def test_trigger_none_inputs_uses_defaults() -> None:
    """``trigger(None)`` applies the pydantic defaults."""
    factory = _build_fake_factory([_make_marca()], total=1)
    client = IMPIMiddlewareClient(client_factory=factory)
    job = await client.trigger(None)
    res = await client.get_result(job["job_id"])
    assert res["status"] == "done"
    assert res["data"]["inputs"]["owner"] == "Genomma"


# ----------------------------------------------------------------------------
# Envelope shape
# ----------------------------------------------------------------------------


async def test_envelope_shape() -> None:
    """Envelope has the five canonical top-level keys, nothing else."""
    factory = _build_fake_factory([_make_marca()], total=1, search_id="sid-001")
    client = IMPIMiddlewareClient(client_factory=factory)
    job = await client.trigger({})
    res = await client.get_result(job["job_id"])

    env = res["data"]
    assert set(env.keys()) == {"source", "scraped_at", "inputs", "data", "meta"}
    assert env["scraped_at"].endswith("Z")
    # Meta extras specific to impi (no BrightData fields).
    for key in (
        "rows",
        "emitted",
        "skipped_by_reason",
        "errors",
        "total_in_portal",
        "paginated",
        "search_id",
        "started_at",
        "ended_at",
    ):
        assert key in env["meta"], f"meta missing {key!r}"
    # Validates via pydantic Envelope so extra/missing top keys would fail.
    Envelope(**env)


async def test_envelope_shape_via_fixture(snapshot_rows: list[dict]) -> None:
    """Hand-crafted fixture round-trips through build_envelope_for_rows.

    ``build_envelope_for_rows`` returns ``{"status": "done", "data": envelope}``
    — matching the canonical contract the agents harness expects from
    ``get_result``.
    """
    client = IMPIMiddlewareClient()
    res = client.build_envelope_for_rows(
        snapshot_rows,
        public_inputs={},
        search_id="search-fixture",
        total_in_portal=len(snapshot_rows),
    )
    assert res["status"] == "done"
    env = res["data"]
    assert env["source"] == "impi"
    assert len(env["data"]) == len(snapshot_rows)
    # The fixture's `paginated` scraper_flag is carried verbatim in the row,
    # not in meta.paginated (meta is the portal-wide flag, not per-row).
    assert env["meta"]["paginated"] is False
    assert env["meta"]["search_id"] == "search-fixture"
    Envelope(**env)


async def test_build_envelope_for_rows_empty() -> None:
    """Empty list → valid envelope with meta.rows=0, meta.emitted=0."""
    client = IMPIMiddlewareClient()
    res = client.build_envelope_for_rows([], public_inputs={})
    assert res["status"] == "done"
    env = res["data"]
    assert env["data"] == []
    assert env["meta"]["rows"] == 0
    assert env["meta"]["emitted"] == 0
    assert env["meta"]["errors"] == 0
    Envelope(**env)


async def test_build_envelope_for_rows_applies_pydantic_defaults() -> None:
    """``public_inputs={}`` gets pydantic defaults applied in the envelope."""
    client = IMPIMiddlewareClient()
    res = client.build_envelope_for_rows([], public_inputs={})
    env = res["data"]
    assert env["inputs"]["owner"] == "Genomma"
    assert env["inputs"]["expires_within_days"] == 90
    assert env["inputs"]["page_size"] == 50
    assert env["inputs"]["mode"] == "incremental"


# ----------------------------------------------------------------------------
# TOOL_SCHEMA
# ----------------------------------------------------------------------------


async def test_tool_schema() -> None:
    """TOOL_SCHEMA is a list of 2 dicts with the required keys/names."""
    assert isinstance(TOOL_SCHEMA, list)
    assert len(TOOL_SCHEMA) == 2
    names = {t["name"] for t in TOOL_SCHEMA}
    assert names == {"impi_trigger", "impi_get_result"}
    for tool in TOOL_SCHEMA:
        assert isinstance(tool["description"], str) and tool["description"]
        assert isinstance(tool["input_schema"], dict)
        assert tool["input_schema"]["type"] == "object"

    # Spot-check trigger input schema advertises the 4 public inputs.
    trigger_tool = next(t for t in TOOL_SCHEMA if t["name"] == "impi_trigger")
    props = trigger_tool["input_schema"]["properties"]
    assert set(props.keys()) == {"owner", "expires_within_days", "page_size", "mode"}

    # get_result requires job_id.
    get_tool = next(t for t in TOOL_SCHEMA if t["name"] == "impi_get_result")
    assert get_tool["input_schema"]["required"] == ["job_id"]


# ----------------------------------------------------------------------------
# Module-level entry points + harness discovery
# ----------------------------------------------------------------------------


async def test_module_level_trigger_and_get(monkeypatch: pytest.MonkeyPatch) -> None:
    """``from gli_scrapers.impi import trigger, get_result`` works end-to-end.

    We monkeypatch the default client factory so the module-level ``trigger``
    does not attempt to hit the real portal.
    """
    rows = [_make_marca("TAFIROL")]
    factory = _build_fake_factory(rows, total=1)

    from gli_scrapers.impi import client as client_mod

    monkeypatch.setattr(client_mod, "_default_client_factory", factory)

    job = await trigger({"owner": "Genomma"})
    assert job["eta_seconds"] == 0
    res = await get_result(job["job_id"])
    assert res["status"] == "done"
    assert len(res["data"]["data"]) == 1


async def test_harness_discovery_contract() -> None:
    """The three symbols the harness expects are exported at the pkg level.

    Mirrors ``agent_harness/registry.py::_discover_middlewares`` — the
    middleware must expose ``TOOL_SCHEMA``, ``trigger``, ``get_result``.
    """
    import gli_scrapers.impi as pkg

    for attr in ("TOOL_SCHEMA", "trigger", "get_result"):
        assert hasattr(pkg, attr), f"impi must export {attr} for harness auto-discovery"


async def test_inputs_model_has_sensible_defaults() -> None:
    """Defaults match what IMPI calls prefer (Genomma / 90d / 50 / incremental)."""
    defaults = IMPIInputs().model_dump()
    assert defaults == {
        "owner": "Genomma",
        "expires_within_days": 90,
        "page_size": 50,
        "mode": "incremental",
    }
