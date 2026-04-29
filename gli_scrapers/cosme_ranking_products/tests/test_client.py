"""Unit + fixture tests for the cosme_ranking_products middleware.

Coverage map (handoff §7):
    - test_trigger_happy_path                 — @brightdata, real call (skipped w/o env)
    - test_get_result_done_from_fixture       — parses the canonical fixture
    - test_envelope_shape                     — exact top-level keys, no extras
    - test_entry_keys_complete               — every spec field key present
    - test_all_images_is_list                — all_images never null
    - test_all_images_null_coerced_to_list   — null in raw → [] in output
    - test_non_dict_row_counted_as_error     — non-dict rows → errors counter
    - test_invalid_inputs_max_pages_over_cap — max_pages=11 => INVALID_INPUTS
    - test_invalid_inputs_unknown_key        — extra key => INVALID_INPUTS (extra=forbid)
    - test_tool_schema_shape                  — TOOL_SCHEMA is the right dict shape
    - test_trigger_missing_credentials       — no env vars => INVALID_INPUTS at trigger time
    - test_resolve_mode_v3_wins_over_dca     — precedence rule
    - test_resolve_mode_dca_only             — DCA picked when only DCA set
    - test_resolve_mode_v3_only              — v3 picked when only v3 set
    - test_input_translation_default         — default inputs → correct seed
    - test_input_translation_partial_pages   — max_pages=5 → "5" in seed
    - test_coerce_entry_fills_missing_keys   — minimal row gets all keys
"""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from gli_scrapers.core.envelope import Envelope
from gli_scrapers.cosme_ranking_products import (
    TOOL_SCHEMA,
    CosmeRankingClient,
    CosmeRankingInputs,
    RankingEntry,
    trigger,
)
from gli_scrapers.cosme_ranking_products.client import _coerce_entry
from gli_scrapers.cosme_ranking_products.models import (
    RANKING_ENTRY_FIELDS,
    RANKING_LIST_FIELDS,
)

pytestmark = pytest.mark.asyncio


# ----------------------------------------------------------------------------
# Live BrightData (skipped unless env vars set, see conftest.py)
# ----------------------------------------------------------------------------


@pytest.mark.brightdata
@pytest.mark.parametrize(
    "api_mode,resource_env",
    [
        ("v3", "BRIGHTDATA_DATASET_ID_COSME_RANKING"),
        ("dca", "BRIGHTDATA_COLLECTOR_ID_COSME_RANKING"),
    ],
)
async def test_trigger_happy_path(api_mode: str, resource_env: str) -> None:
    """Default inputs against the real BrightData API → returns a job_id."""
    resource_id = os.getenv(resource_env)
    if not resource_id:
        pytest.skip(f"{resource_env} not set — skipping {api_mode} live case")

    client = CosmeRankingClient(api_mode=api_mode, resource_id=resource_id)
    try:
        res = await client.trigger({})
    finally:
        await client.aclose()
    assert "job_id" in res, res
    assert isinstance(res["job_id"], str) and res["job_id"]
    assert isinstance(res.get("eta_seconds"), int)


# ----------------------------------------------------------------------------
# Fixture-driven tests (always run)
# ----------------------------------------------------------------------------


async def test_get_result_done_from_fixture(snapshot_rows: list[dict]) -> None:
    """Hand the fixture to ``build_envelope_for_rows`` → valid envelope."""
    client = CosmeRankingClient()
    res = client.build_envelope_for_rows(
        snapshot_rows,
        public_inputs={"max_pages": 10, "mode": "full-refresh"},
    )
    assert res["status"] == "done"
    env = res["data"]
    assert env["source"] == "cosme_ranking_products"
    assert isinstance(env["data"], list) and len(env["data"]) == len(snapshot_rows)
    # Validate via pydantic Envelope so we catch any extra/missing top keys.
    Envelope(**env)


async def test_envelope_shape(snapshot_rows: list[dict]) -> None:
    """Top-level envelope keys are EXACTLY the contracted set (no extras)."""
    client = CosmeRankingClient()
    res = client.build_envelope_for_rows(snapshot_rows, public_inputs={})
    env = res["data"]
    assert set(env.keys()) == {"source", "scraped_at", "inputs", "data", "meta"}
    assert env["scraped_at"].endswith("Z")
    for key in ("rows", "emitted", "errors", "started_at", "ended_at"):
        assert key in env["meta"], f"meta missing {key!r}"


async def test_entry_keys_complete(snapshot_rows: list[dict]) -> None:
    """Every emitted row has all spec field keys (null/[] allowed, never absent)."""
    client = CosmeRankingClient()
    res = client.build_envelope_for_rows(snapshot_rows, public_inputs={})
    for row in res["data"]["data"]:
        for key in RANKING_ENTRY_FIELDS:
            assert key in row, f"missing key {key!r} in row {row.get('product_id')}"
        for key in RANKING_LIST_FIELDS:
            assert isinstance(row[key], list), (
                f"key {key!r} in row {row.get('product_id')} must be a list, "
                f"got {type(row[key]).__name__}"
            )


async def test_all_images_is_list(snapshot_rows: list[dict]) -> None:
    """``all_images`` is always a list, never None, across all fixture rows."""
    client = CosmeRankingClient()
    res = client.build_envelope_for_rows(snapshot_rows, public_inputs={})
    for row in res["data"]["data"]:
        assert isinstance(row["all_images"], list), (
            f"all_images is {type(row['all_images']).__name__} for "
            f"product_id={row.get('product_id')}"
        )


async def test_all_images_null_coerced_to_list() -> None:
    """A row with ``all_images: null`` is coerced to ``[]``, not left as None."""
    raw = {
        "rank": 5,
        "product_id": "TEST001",
        "product_name": "テスト",
        "all_images": None,
    }
    out = _coerce_entry(raw)
    assert out["all_images"] == []


async def test_non_dict_row_counted_as_error() -> None:
    """Non-dict rows increment ``meta.errors`` and are excluded from ``data``."""
    rows: list[Any] = [
        {"rank": 1, "product_id": "VALID", "all_images": []},
        "this is not a dict",
        None,
    ]
    client = CosmeRankingClient()
    res = client.build_envelope_for_rows(rows, public_inputs={})
    env = res["data"]
    assert env["meta"]["errors"] == 2
    assert env["meta"]["emitted"] == 1
    assert len(env["data"]) == 1


# ----------------------------------------------------------------------------
# Invalid-inputs paths (no BrightData call)
# ----------------------------------------------------------------------------


async def test_invalid_inputs_max_pages_over_cap() -> None:
    """``max_pages=11`` (> 10) => INVALID_INPUTS, BrightData NOT called."""
    res = await trigger({"max_pages": 11})
    assert res["status"] == "failed"
    assert res["error"]["code"] == "INVALID_INPUTS"
    assert res["error"]["retriable"] is False


async def test_invalid_inputs_max_pages_zero() -> None:
    """``max_pages=0`` (< 1) => INVALID_INPUTS."""
    res = await trigger({"max_pages": 0})
    assert res["status"] == "failed"
    assert res["error"]["code"] == "INVALID_INPUTS"


async def test_invalid_inputs_unknown_key() -> None:
    """Unknown public input key => INVALID_INPUTS (extra='forbid')."""
    res = await trigger({"definitely_not_a_real_input": True})
    assert res["status"] == "failed"
    assert res["error"]["code"] == "INVALID_INPUTS"


async def test_invalid_inputs_bad_mode() -> None:
    """``mode='invalid'`` => INVALID_INPUTS."""
    res = await trigger({"mode": "invalid"})
    assert res["status"] == "failed"
    assert res["error"]["code"] == "INVALID_INPUTS"


# ----------------------------------------------------------------------------
# Input translation tests
# ----------------------------------------------------------------------------


async def test_input_translation_default() -> None:
    """Default inputs (max_pages=10) → seed with empty max_pages string."""
    client = CosmeRankingClient()
    seeds = client._build_brightdata_inputs(CosmeRankingInputs())
    assert len(seeds) == 1
    seed = seeds[0]
    assert seed["page"] == ""
    assert seed["url"] == ""
    # max_pages=10 is the default/max, so we send empty string.
    assert seed["max_pages"] == ""


async def test_input_translation_partial_pages() -> None:
    """``max_pages=5`` sends ``"5"`` to the JS scraper."""
    client = CosmeRankingClient()
    seeds = client._build_brightdata_inputs(CosmeRankingInputs(max_pages=5))
    assert len(seeds) == 1
    assert seeds[0]["max_pages"] == "5"


async def test_input_translation_one_page() -> None:
    """``max_pages=1`` sends ``"1"`` to the JS scraper."""
    client = CosmeRankingClient()
    seeds = client._build_brightdata_inputs(CosmeRankingInputs(max_pages=1))
    assert seeds[0]["max_pages"] == "1"


# ----------------------------------------------------------------------------
# Coerce entry (unit, no BrightData)
# ----------------------------------------------------------------------------


async def test_coerce_entry_fills_missing_keys() -> None:
    """A minimal row still emits all spec field keys (null / [])."""
    raw = {"product_id": "minimal", "rank": 42}
    out = _coerce_entry(raw)
    for key in RANKING_ENTRY_FIELDS:
        assert key in out, f"missing key {key!r}"
    assert out["all_images"] == []
    assert out["product_name"] is None
    # Extra keys forwarded verbatim.
    raw2 = {**raw, "future_field": "v"}
    out2 = _coerce_entry(raw2)
    assert out2.get("future_field") == "v"


async def test_coerce_entry_wraps_scalar_all_images() -> None:
    """If ``all_images`` is a string, it's wrapped in a list."""
    raw = {"product_id": "x", "all_images": "https://example.com/img.jpg"}
    out = _coerce_entry(raw)
    assert out["all_images"] == ["https://example.com/img.jpg"]


async def test_pydantic_entry_model_smoke(snapshot_rows: list[dict]) -> None:
    """Every fixture row round-trips through the ``RankingEntry`` model cleanly."""
    for raw in snapshot_rows:
        entry = RankingEntry(**raw)
        assert entry is not None


# ----------------------------------------------------------------------------
# TOOL_SCHEMA shape
# ----------------------------------------------------------------------------


async def test_tool_schema_shape() -> None:
    """TOOL_SCHEMA is the exact dict shape Anthropic API expects."""
    assert isinstance(TOOL_SCHEMA, list) and len(TOOL_SCHEMA) == 2
    names = {t["name"] for t in TOOL_SCHEMA}
    assert names == {"cosme_ranking_trigger", "cosme_ranking_get_result"}
    for tool in TOOL_SCHEMA:
        assert "description" in tool
        assert "input_schema" in tool
        schema = tool["input_schema"]
        assert schema["type"] == "object"
        assert schema.get("additionalProperties") is False


# ----------------------------------------------------------------------------
# Credentials check
# ----------------------------------------------------------------------------


async def test_trigger_missing_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing credentials surface as INVALID_INPUTS at trigger time, not import time."""
    monkeypatch.delenv("BRIGHTDATA_API_KEY", raising=False)
    monkeypatch.delenv("BRIGHTDATA_DATASET_ID_COSME_RANKING", raising=False)
    monkeypatch.delenv("BRIGHTDATA_COLLECTOR_ID_COSME_RANKING", raising=False)
    res = await trigger({})
    assert res["status"] == "failed"
    assert res["error"]["code"] == "INVALID_INPUTS"


# ----------------------------------------------------------------------------
# Dual-mode transport selection (unit, no live calls)
# ----------------------------------------------------------------------------


async def test_resolve_mode_v3_wins_over_dca(monkeypatch: pytest.MonkeyPatch) -> None:
    """When both env vars are set, v3 wins."""
    monkeypatch.setenv("BRIGHTDATA_DATASET_ID_COSME_RANKING", "gd_test_v3")
    monkeypatch.setenv("BRIGHTDATA_COLLECTOR_ID_COSME_RANKING", "c_test_dca")
    client = CosmeRankingClient()
    assert client.api_mode == "v3"
    assert client.resource_id == "gd_test_v3"


async def test_resolve_mode_dca_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """With only the DCA env var populated, the client picks DCA mode."""
    monkeypatch.delenv("BRIGHTDATA_DATASET_ID_COSME_RANKING", raising=False)
    monkeypatch.setenv("BRIGHTDATA_COLLECTOR_ID_COSME_RANKING", "c_test_dca")
    client = CosmeRankingClient()
    assert client.api_mode == "dca"
    assert client.resource_id == "c_test_dca"


async def test_resolve_mode_v3_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """With only the v3 env var populated, the client picks v3 mode."""
    monkeypatch.setenv("BRIGHTDATA_DATASET_ID_COSME_RANKING", "gd_test_v3")
    monkeypatch.delenv("BRIGHTDATA_COLLECTOR_ID_COSME_RANKING", raising=False)
    client = CosmeRankingClient()
    assert client.api_mode == "v3"
    assert client.resource_id == "gd_test_v3"


async def test_resolve_mode_none_surfaces_invalid_inputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No env vars → INVALID_INPUTS at trigger time; message names both env vars."""
    monkeypatch.setenv("BRIGHTDATA_API_KEY", "fake_key_for_test")
    monkeypatch.delenv("BRIGHTDATA_DATASET_ID_COSME_RANKING", raising=False)
    monkeypatch.delenv("BRIGHTDATA_COLLECTOR_ID_COSME_RANKING", raising=False)
    res = await trigger({})
    assert res["status"] == "failed"
    assert res["error"]["code"] == "INVALID_INPUTS"
    msg = res["error"]["message"]
    assert "BRIGHTDATA_DATASET_ID_COSME_RANKING" in msg
    assert "BRIGHTDATA_COLLECTOR_ID_COSME_RANKING" in msg


async def test_explicit_api_mode_overrides_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Explicit ``api_mode=`` and ``resource_id=`` beat env vars."""
    monkeypatch.setenv("BRIGHTDATA_DATASET_ID_COSME_RANKING", "gd_env")
    monkeypatch.setenv("BRIGHTDATA_COLLECTOR_ID_COSME_RANKING", "c_env")
    client = CosmeRankingClient(api_mode="dca", resource_id="c_override")
    assert client.api_mode == "dca"
    assert client.resource_id == "c_override"


# ----------------------------------------------------------------------------
# get_result: running / failed paths (mocked transport)
# ----------------------------------------------------------------------------


async def test_get_result_running(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_result returns running shape when BrightData reports in-progress."""
    monkeypatch.setenv("BRIGHTDATA_API_KEY", "fake")
    monkeypatch.setenv("BRIGHTDATA_DATASET_ID_COSME_RANKING", "gd_fake")

    client = CosmeRankingClient()
    client._get_progress = AsyncMock(return_value={"status": "running", "progress_pct": 42})
    res = await client.get_result("fake_job_id")
    assert res == {"status": "running", "progress_pct": 42}


async def test_get_result_failed_from_brightdata(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_result returns failed shape when BrightData reports failure."""
    monkeypatch.setenv("BRIGHTDATA_API_KEY", "fake")
    monkeypatch.setenv("BRIGHTDATA_DATASET_ID_COSME_RANKING", "gd_fake")

    client = CosmeRankingClient()
    client._get_progress = AsyncMock(
        return_value={"status": "failed", "message": "scraper blew up"}
    )
    res = await client.get_result("fake_job_id")
    assert res["status"] == "failed"
    assert res["error"]["code"] == "BRIGHTDATA_ERROR"


async def test_get_result_invalid_job_id() -> None:
    """Empty job_id => INVALID_INPUTS without calling BrightData."""
    client = CosmeRankingClient()
    res = await client.get_result("")
    assert res["status"] == "failed"
    assert res["error"]["code"] == "INVALID_INPUTS"
