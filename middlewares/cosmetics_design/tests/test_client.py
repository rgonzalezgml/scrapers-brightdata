"""Unit + fixture tests for the cosmetics_design middleware.

Coverage map (handoff §7):
    - test_trigger_happy_path                — @brightdata, real call (skipped w/o env)
    - test_get_result_done_from_fixture     — parses the canonical fixture
    - test_invalid_inputs_window_days       — INVALID_INPUTS, no API call
    - test_invalid_inputs_region_filter     — INVALID_INPUTS, no API call
    - test_envelope_shape                    — exact top-level keys, no extras
    - test_article_keys_complete            — every spec §2/§4 key present
    - test_max_articles_cap                 — emitted ≤ max_articles
    - test_window_filter_drops_old           — incremental drops out-of-window
    - test_full_refresh_keeps_old            — full-refresh keeps everything
    - test_region_filter_applied            — region_filter narrows envelope
    - test_paywall_saturation_threshold     — surfaces PAYWALL_SATURATION
    - test_input_translation                — public→JS-scraper input mapping
    - test_credentials_required_at_trigger  — missing env => INVALID_INPUTS
"""

from __future__ import annotations

import os
from typing import Any

import pytest

from middlewares.core.envelope import Envelope
from middlewares.core.errors import NORMALIZED_CODES
from middlewares.cosmetics_design import (
    TOOL_SCHEMA,
    Article,
    CosmeticsDesignClient,
    CosmeticsDesignInputs,
    trigger,
)
from middlewares.cosmetics_design.client import (
    COSMETICS_DESIGN_ERROR_CODES,
    _coerce_article,
)
from middlewares.cosmetics_design.config import (
    ARTICLES_PER_PAGE,
    DEFAULT_SUPPLIER,
    SOURCE_LANDING_URL,
)
from middlewares.cosmetics_design.models import ARTICLE_FIELDS, ARTICLE_LIST_FIELDS

pytestmark = pytest.mark.asyncio


# ----------------------------------------------------------------------------
# Live BrightData (skipped unless env vars set, see conftest.py)
# ----------------------------------------------------------------------------


@pytest.mark.brightdata
@pytest.mark.parametrize(
    "api_mode,resource_env",
    [
        ("v3", "BRIGHTDATA_DATASET_ID_COSMETICS_DESIGN"),
        ("dca", "BRIGHTDATA_COLLECTOR_ID_COSMETICS_DESIGN"),
    ],
)
async def test_trigger_happy_path(api_mode: str, resource_env: str) -> None:
    """Default inputs against the real BrightData API → returns a job_id.

    Parametrized over both transports. Each case is skipped individually when
    its env var is missing so a partial config (e.g. only DCA populated) still
    exercises the runnable mode.
    """
    resource_id = os.getenv(resource_env)
    if not resource_id:
        pytest.skip(f"{resource_env} not set — skipping {api_mode} live case")

    client = CosmeticsDesignClient(api_mode=api_mode, resource_id=resource_id)
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
    client = CosmeticsDesignClient()
    res = client.build_envelope_for_rows(
        snapshot_rows,
        public_inputs={"window_days": 365, "max_articles": 1000, "mode": "full-refresh"},
    )
    assert res["status"] == "done"
    env = res["data"]
    assert env["source"] == "cosmetics-design"
    assert isinstance(env["data"], list) and len(env["data"]) == len(snapshot_rows)
    # Validate via pydantic Envelope so we catch any extra/missing top keys.
    Envelope(**env)


async def test_envelope_shape(snapshot_rows: list[dict]) -> None:
    """Top-level envelope keys are EXACTLY the contracted set (no extras)."""
    client = CosmeticsDesignClient()
    res = client.build_envelope_for_rows(snapshot_rows, public_inputs={"mode": "full-refresh"})
    env = res["data"]
    assert set(env.keys()) == {"source", "scraped_at", "inputs", "data", "meta"}
    # ``scraped_at`` must look like an ISO8601 UTC string.
    assert env["scraped_at"].endswith("Z")
    # meta has the keys handoff §2.4 promised.
    for key in ("rows", "emitted", "skipped_by_reason", "paywalled", "blocked",
                "errors", "started_at", "ended_at"):
        assert key in env["meta"], f"meta missing {key!r}"


async def test_article_keys_complete(snapshot_rows: list[dict]) -> None:
    """Every emitted row has all §2/§4 keys (null/[] allowed, never absent)."""
    client = CosmeticsDesignClient()
    res = client.build_envelope_for_rows(snapshot_rows, public_inputs={"mode": "full-refresh"})
    for row in res["data"]["data"]:
        for key in ARTICLE_FIELDS:
            assert key in row, f"missing key {key!r} in row {row.get('article_id')}"
        for key in ARTICLE_LIST_FIELDS:
            assert isinstance(row[key], list), (
                f"key {key!r} in row {row.get('article_id')} must be a list, "
                f"got {type(row[key]).__name__}"
            )


async def test_max_articles_cap(snapshot_rows: list[dict]) -> None:
    """``max_articles`` caps emitted rows even if BrightData returns more."""
    client = CosmeticsDesignClient()
    res = client.build_envelope_for_rows(
        snapshot_rows,
        public_inputs={"max_articles": 2, "mode": "full-refresh"},
    )
    env = res["data"]
    assert len(env["data"]) == 2
    assert env["meta"]["emitted"] == 2
    assert env["meta"]["skipped_by_reason"].get("max_articles_cap") == 1


async def test_window_filter_drops_old(snapshot_rows: list[dict]) -> None:
    """Incremental mode + small window drops the 2025 row."""
    client = CosmeticsDesignClient()
    res = client.build_envelope_for_rows(
        snapshot_rows,
        public_inputs={"window_days": 30, "max_articles": 1000, "mode": "incremental"},
    )
    env = res["data"]
    ids = [row["article_id"] for row in env["data"]]
    assert "FAKE_ID_delta_no_region" not in ids, (
        "Old article should be filtered out by window_days=30"
    )
    assert env["meta"]["skipped_by_reason"].get("out_of_window", 0) >= 1


async def test_full_refresh_keeps_old(snapshot_rows: list[dict]) -> None:
    """``mode='full-refresh'`` ignores window_days even when it's tiny."""
    client = CosmeticsDesignClient()
    res = client.build_envelope_for_rows(
        snapshot_rows,
        public_inputs={"window_days": 1, "max_articles": 1000, "mode": "full-refresh"},
    )
    ids = [row["article_id"] for row in res["data"]["data"]]
    assert "FAKE_ID_delta_no_region" in ids


async def test_region_filter_applied(snapshot_rows: list[dict]) -> None:
    """``region_filter='Europe'`` narrows the envelope's data[]."""
    client = CosmeticsDesignClient()
    res = client.build_envelope_for_rows(
        snapshot_rows,
        public_inputs={
            "region_filter": "Europe",
            "max_articles": 1000,
            "mode": "full-refresh",
        },
    )
    rows = res["data"]["data"]
    assert all("Europe" in row["region_tags"] for row in rows)
    assert len(rows) == 1  # only the alpha row carries Europe.


# ----------------------------------------------------------------------------
# Invalid-inputs paths (no BrightData call)
# ----------------------------------------------------------------------------


async def test_invalid_inputs_window_days() -> None:
    """``window_days=9999`` => INVALID_INPUTS, BrightData NOT called."""
    res = await trigger({"window_days": 9999})
    assert res["status"] == "failed"
    assert res["error"]["code"] == "INVALID_INPUTS"
    assert res["error"]["retriable"] is False


async def test_invalid_inputs_region_filter() -> None:
    """``region_filter='Antarctica'`` (out of enum) => INVALID_INPUTS."""
    res = await trigger({"region_filter": "Antarctica"})
    assert res["status"] == "failed"
    assert res["error"]["code"] == "INVALID_INPUTS"


async def test_invalid_inputs_unknown_key() -> None:
    """Unknown public input key => INVALID_INPUTS (extra='forbid')."""
    res = await trigger({"definitely_not_a_real_input": True})
    assert res["status"] == "failed"
    assert res["error"]["code"] == "INVALID_INPUTS"


# ----------------------------------------------------------------------------
# Translation: public inputs → JS scraper inputs
# ----------------------------------------------------------------------------


async def test_input_translation_default() -> None:
    """Middleware sends only ``url`` — vendor schema compatibility (spec §10)."""
    client = CosmeticsDesignClient()
    seeds = client._build_brightdata_inputs(CosmeticsDesignInputs())
    assert len(seeds) == 1
    seed = seeds[0]
    assert seed == {"url": SOURCE_LANDING_URL}


async def test_input_translation_full_refresh_same_shape() -> None:
    """``mode='full-refresh'`` does not change the seed shape — the scraper
    runs to exhaustion on its own (vendor ignores extras)."""
    client = CosmeticsDesignClient()
    seeds = client._build_brightdata_inputs(
        CosmeticsDesignInputs(mode="full-refresh", max_articles=5000)
    )
    assert seeds == [{"url": SOURCE_LANDING_URL}]


async def test_input_translation_small_max_articles_same_shape() -> None:
    """``max_articles`` is applied post-download, never in the trigger seed."""
    client = CosmeticsDesignClient()
    seeds = client._build_brightdata_inputs(
        CosmeticsDesignInputs(max_articles=1, mode="incremental")
    )
    assert seeds == [{"url": SOURCE_LANDING_URL}]


# ----------------------------------------------------------------------------
# PAYWALL_SATURATION
# ----------------------------------------------------------------------------


async def test_paywall_saturation_threshold() -> None:
    """>50% paywalled rows => PAYWALL_SATURATION error."""
    rows: list[dict[str, Any]] = []
    for i in range(10):
        rows.append({
            "article_id": f"FAKE_paywalled_{i}",
            "url": f"https://example.com/{i}",
            "headline": f"Article {i}",
            "display_date": "2026-04-20T00:00:00.000Z",
            "paywalled": i < 6,  # 6 of 10 paywalled = 60%
            "region_tags": ["Europe"],
        })
    client = CosmeticsDesignClient()
    res = client.build_envelope_for_rows(
        rows,
        public_inputs={"max_articles": 100, "mode": "full-refresh"},
    )
    # build_envelope_for_rows itself returns "done"; the saturation check
    # happens inside get_result. Re-run that gate:
    from middlewares.cosmetics_design.client import _maybe_paywall_saturation

    final = _maybe_paywall_saturation(res)
    assert final["status"] == "failed"
    assert final["error"]["code"] == "PAYWALL_SATURATION"
    assert final["error"]["retriable"] is False
    assert final["error"]["details"]["paywalled"] == 6
    assert final["error"]["details"]["emitted"] == 10


# ----------------------------------------------------------------------------
# Misc / coverage
# ----------------------------------------------------------------------------


async def test_credentials_required_at_trigger(monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing credentials surface as INVALID_INPUTS at trigger time, not import time."""
    # Wipe every env var so both missing-credential branches fire.
    monkeypatch.delenv("BRIGHTDATA_API_KEY", raising=False)
    monkeypatch.delenv("BRIGHTDATA_DATASET_ID_COSMETICS_DESIGN", raising=False)
    monkeypatch.delenv("BRIGHTDATA_COLLECTOR_ID_COSMETICS_DESIGN", raising=False)
    res = await trigger({})  # default valid inputs
    assert res["status"] == "failed"
    assert res["error"]["code"] == "INVALID_INPUTS"
    # Never raised — the public API never throws (handoff §2.1).


# ----------------------------------------------------------------------------
# Dual-mode transport selection (unit, no live calls)
# ----------------------------------------------------------------------------


async def test_resolve_mode_v3_wins_over_dca(monkeypatch: pytest.MonkeyPatch) -> None:
    """When both env vars are set, v3 wins (spec §3.3)."""
    monkeypatch.setenv("BRIGHTDATA_DATASET_ID_COSMETICS_DESIGN", "gd_test_v3")
    monkeypatch.setenv("BRIGHTDATA_COLLECTOR_ID_COSMETICS_DESIGN", "c_test_dca")
    client = CosmeticsDesignClient()
    assert client.api_mode == "v3"
    assert client.resource_id == "gd_test_v3"


async def test_resolve_mode_dca_when_only_dca_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With only the DCA env var populated, the client picks DCA mode."""
    monkeypatch.delenv("BRIGHTDATA_DATASET_ID_COSMETICS_DESIGN", raising=False)
    monkeypatch.setenv("BRIGHTDATA_COLLECTOR_ID_COSMETICS_DESIGN", "c_test_dca")
    client = CosmeticsDesignClient()
    assert client.api_mode == "dca"
    assert client.resource_id == "c_test_dca"


async def test_resolve_mode_v3_when_only_v3_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With only the v3 env var populated, the client picks v3 mode."""
    monkeypatch.setenv("BRIGHTDATA_DATASET_ID_COSMETICS_DESIGN", "gd_test_v3")
    monkeypatch.delenv("BRIGHTDATA_COLLECTOR_ID_COSMETICS_DESIGN", raising=False)
    client = CosmeticsDesignClient()
    assert client.api_mode == "v3"
    assert client.resource_id == "gd_test_v3"


async def test_resolve_mode_none_when_neither_set_surfaces_invalid_inputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No env vars populated → ``INVALID_INPUTS`` at trigger time.

    The error message must mention BOTH env vars so the user knows which one
    to populate (spec §3.4 / §7 criterion 7).
    """
    monkeypatch.setenv("BRIGHTDATA_API_KEY", "fake_key_for_test")
    monkeypatch.delenv("BRIGHTDATA_DATASET_ID_COSMETICS_DESIGN", raising=False)
    monkeypatch.delenv("BRIGHTDATA_COLLECTOR_ID_COSMETICS_DESIGN", raising=False)
    res = await trigger({})
    assert res["status"] == "failed"
    assert res["error"]["code"] == "INVALID_INPUTS"
    msg = res["error"]["message"]
    assert "BRIGHTDATA_DATASET_ID_COSMETICS_DESIGN" in msg
    assert "BRIGHTDATA_COLLECTOR_ID_COSMETICS_DESIGN" in msg


async def test_explicit_api_mode_overrides_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Explicit ``api_mode=`` and ``resource_id=`` beat env vars."""
    monkeypatch.setenv("BRIGHTDATA_DATASET_ID_COSMETICS_DESIGN", "gd_env")
    monkeypatch.setenv("BRIGHTDATA_COLLECTOR_ID_COSMETICS_DESIGN", "c_env")
    client = CosmeticsDesignClient(api_mode="dca", resource_id="c_override")
    assert client.api_mode == "dca"
    assert client.resource_id == "c_override"


async def test_dataset_id_alias_silent_backwards_compat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``dataset_id=`` kwarg aliases ``resource_id=`` silently (no warning)."""
    import warnings

    monkeypatch.delenv("BRIGHTDATA_DATASET_ID_COSMETICS_DESIGN", raising=False)
    monkeypatch.delenv("BRIGHTDATA_COLLECTOR_ID_COSMETICS_DESIGN", raising=False)
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        client = CosmeticsDesignClient(dataset_id="gd_from_alias")
    assert client.resource_id == "gd_from_alias"
    # Default mode stays v3 when only dataset_id alias is used.
    assert client.api_mode == "v3"
    # No DeprecationWarning (silent alias per apéndice A §3).
    assert not any(
        issubclass(w.category, DeprecationWarning) for w in captured
    ), [str(w.message) for w in captured]


async def test_tool_schema_shape() -> None:
    """TOOL_SCHEMA is the exact dict shape Anthropic API expects."""
    assert isinstance(TOOL_SCHEMA, list) and len(TOOL_SCHEMA) == 2
    names = {t["name"] for t in TOOL_SCHEMA}
    assert names == {"cosmetics_design_trigger", "cosmetics_design_get_result"}
    for tool in TOOL_SCHEMA:
        assert "description" in tool
        assert "input_schema" in tool
        assert tool["input_schema"]["type"] == "object"


async def test_per_scraper_error_codes_extendcore() -> None:
    """The cosmetics_design error code extension does not redefine base codes."""
    for code in COSMETICS_DESIGN_ERROR_CODES:
        assert code not in NORMALIZED_CODES, (
            f"Per-scraper code {code!r} collides with base catalog."
        )


async def test_coerce_article_fills_missing_keys() -> None:
    """A row missing most keys still emits all §2/§4 keys (null / [])."""
    raw = {"article_id": "minimal", "url": "https://example.com/x"}
    out = _coerce_article(raw)
    for key in ARTICLE_FIELDS:
        assert key in out
    assert out["author_names"] == []
    assert out["headline"] is None
    # extra keys forwarded verbatim.
    raw2 = {**raw, "future_field_we_dont_know_about": "v"}
    out2 = _coerce_article(raw2)
    assert out2.get("future_field_we_dont_know_about") == "v"


async def test_pydantic_article_model_smoke(snapshot_rows: list[dict]) -> None:
    """Every fixture row round-trips through the ``Article`` model cleanly."""
    for raw in snapshot_rows:
        assert Article(**raw)
