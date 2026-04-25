"""Unit + fixture tests for the cosme middleware.

Coverage map:
    - test_trigger_happy_path               — @brightdata live (skipped w/o env)
    - test_get_result_done_from_fixture     — parses canonical fixture
    - test_envelope_shape                    — exact top-level keys
    - test_multi_entity_data_split           — product/ranking/brand counts
    - test_product_keys_complete             — spec §2+§4 keys present
    - test_ranking_keys_complete             — spec §2+§4 keys present
    - test_brand_keys_complete               — spec §2+§5 keys present
    - test_aliases_applied                    — product_url → url, etc.
    - test_max_products_cap                   — emitted product ≤ max_products
    - test_include_rankings_false             — drops ranking rows
    - test_include_brands_false               — drops brand rows
    - test_input_translation                  — public → JS-scraper input
    - test_invalid_inputs_*                   — INVALID_INPUTS paths
    - test_resolve_mode_*                     — dual-mode selection
    - test_block_saturation_threshold         — BLOCK_SATURATION code
"""

from __future__ import annotations

import os
from typing import Any

import pytest

from gli_scrapers.core.envelope import Envelope
from gli_scrapers.core.errors import NORMALIZED_CODES
from gli_scrapers.cosme import (
    TOOL_SCHEMA,
    BrandRow,
    CosmeClient,
    CosmeInputs,
    ProductRow,
    RankingRow,
    trigger,
)
from gli_scrapers.cosme.client import (
    COSME_ERROR_CODES,
    _classify_entity,
    _coerce_brand,
    _coerce_product,
    _coerce_ranking,
    _maybe_block_saturation,
)
from gli_scrapers.cosme.config import (
    DEFAULT_YEAR,
    archive_root_url,
)
from gli_scrapers.cosme.models import (
    BRAND_FIELDS,
    PRODUCT_FIELDS,
    PRODUCT_LIST_FIELDS,
    RANKING_FIELDS,
)

pytestmark = pytest.mark.asyncio


# ----------------------------------------------------------------------------
# Live BrightData (skipped unless env vars set, see conftest.py)
# ----------------------------------------------------------------------------


@pytest.mark.brightdata
@pytest.mark.parametrize(
    "api_mode,resource_env",
    [
        ("v3", "BRIGHTDATA_DATASET_ID_COSME"),
        ("dca", "BRIGHTDATA_COLLECTOR_ID_COSME"),
    ],
)
async def test_trigger_happy_path(api_mode: str, resource_env: str) -> None:
    """Default inputs against the real BrightData API → returns a job_id.

    Parametrized over both transports. Each case is skipped individually when
    its env var is missing so a partial config still exercises the runnable
    mode.
    """
    resource_id = os.getenv(resource_env)
    if not resource_id:
        pytest.skip(f"{resource_env} not set — skipping {api_mode} live case")

    client = CosmeClient(api_mode=api_mode, resource_id=resource_id)
    try:
        res = await client.trigger({})
    finally:
        await client.aclose()
    assert "job_id" in res, res
    assert isinstance(res["job_id"], str) and res["job_id"]
    assert isinstance(res.get("eta_seconds"), int)


# ----------------------------------------------------------------------------
# Fixture-driven tests
# ----------------------------------------------------------------------------


async def test_get_result_done_from_fixture(snapshot_rows: list[dict]) -> None:
    """Hand the fixture to ``build_envelope_for_rows`` → valid envelope."""
    client = CosmeClient()
    res = client.build_envelope_for_rows(
        snapshot_rows,
        public_inputs={"max_products": 100},
    )
    assert res["status"] == "done"
    env = res["data"]
    assert env["source"] == "cosme"
    assert isinstance(env["data"], list)
    assert len(env["data"]) == len(snapshot_rows)
    Envelope(**env)


async def test_envelope_shape(snapshot_rows: list[dict]) -> None:
    """Top-level envelope keys are EXACTLY the contracted set (no extras)."""
    client = CosmeClient()
    res = client.build_envelope_for_rows(snapshot_rows, public_inputs={})
    env = res["data"]
    assert set(env.keys()) == {"source", "scraped_at", "inputs", "data", "meta"}
    assert env["scraped_at"].endswith("Z")
    for key in (
        "rows",
        "emitted",
        "emitted_by_entity",
        "skipped_by_reason",
        "blocked",
        "errors",
        "started_at",
        "ended_at",
    ):
        assert key in env["meta"], f"meta missing {key!r}"


async def test_multi_entity_data_split(snapshot_rows: list[dict]) -> None:
    """Each row classified under the correct entity discriminator."""
    client = CosmeClient()
    res = client.build_envelope_for_rows(snapshot_rows, public_inputs={})
    counts = res["data"]["meta"]["emitted_by_entity"]
    # Fixture layout: 3 products + 2 rankings + 1 brand.
    assert counts["product"] == 3
    assert counts["ranking"] == 2
    assert counts["brand"] == 1
    entities = [row["entity"] for row in res["data"]["data"]]
    assert entities.count("product") == 3
    assert entities.count("ranking") == 2
    assert entities.count("brand") == 1


async def test_product_keys_complete(snapshot_rows: list[dict]) -> None:
    """Every emitted product row has all §2/§4 keys (null/[] allowed)."""
    client = CosmeClient()
    res = client.build_envelope_for_rows(snapshot_rows, public_inputs={})
    products = [row for row in res["data"]["data"] if row["entity"] == "product"]
    assert products, "fixture should contain at least one product"
    for row in products:
        for key in PRODUCT_FIELDS:
            assert key in row, f"missing key {key!r} in product row {row.get('product_id')}"
        for key in PRODUCT_LIST_FIELDS:
            assert isinstance(row[key], list), (
                f"key {key!r} in product row {row.get('product_id')} must be a list, "
                f"got {type(row[key]).__name__}"
            )


async def test_ranking_keys_complete(snapshot_rows: list[dict]) -> None:
    """Every ranking row has all §2/§4 keys."""
    client = CosmeClient()
    res = client.build_envelope_for_rows(snapshot_rows, public_inputs={})
    rankings = [row for row in res["data"]["data"] if row["entity"] == "ranking"]
    assert rankings
    for row in rankings:
        for key in RANKING_FIELDS:
            assert key in row, f"missing key {key!r} in ranking row"


async def test_brand_keys_complete(snapshot_rows: list[dict]) -> None:
    """Every brand row has all §2/§5 keys."""
    client = CosmeClient()
    res = client.build_envelope_for_rows(snapshot_rows, public_inputs={})
    brands = [row for row in res["data"]["data"] if row["entity"] == "brand"]
    assert brands
    for row in brands:
        for key in BRAND_FIELDS:
            assert key in row, f"missing key {key!r} in brand row"


async def test_aliases_applied(snapshot_rows: list[dict]) -> None:
    """Scraper-native keys renamed to §2 short forms on the wire."""
    client = CosmeClient()
    res = client.build_envelope_for_rows(snapshot_rows, public_inputs={})
    data = res["data"]["data"]
    # Pick the first product row: should have ``url`` (not product_url).
    prod_alpha = next(
        row for row in data if row["entity"] == "product" and row.get("product_id") == "10248076"
    )
    # Alias target present, populated from scraper's product_url.
    assert prod_alpha["url"] == "https://www.cosme.net/products/10248076/"
    assert prod_alpha["name_raw"] == "ルース パウダー"
    # Brand row aliases
    brand = next(row for row in data if row["entity"] == "brand")
    assert brand["url"] == "https://www.cosme.net/brands/73/?nt=1"
    assert brand["name"] == "SK-II"
    assert brand["total_products"] == 145
    assert brand["total_reviews"] == 45678
    # Ranking row aliases
    ranking = next(row for row in data if row["entity"] == "ranking")
    assert ranking["year"] == 2025
    assert ranking["group"] in ("grand", "category")


async def test_max_products_cap(snapshot_rows: list[dict]) -> None:
    """``max_products`` caps emitted product rows (rankings/brands unaffected)."""
    client = CosmeClient()
    res = client.build_envelope_for_rows(
        snapshot_rows,
        public_inputs={"max_products": 2},
    )
    counts = res["data"]["meta"]["emitted_by_entity"]
    assert counts["product"] == 2
    # Rankings (2) and brands (1) are untouched by max_products.
    assert counts["ranking"] == 2
    assert counts["brand"] == 1
    assert res["data"]["meta"]["skipped_by_reason"].get("max_products_cap") == 1


async def test_include_rankings_false(snapshot_rows: list[dict]) -> None:
    """``include_rankings=False`` drops every ranking row."""
    client = CosmeClient()
    res = client.build_envelope_for_rows(
        snapshot_rows,
        public_inputs={"include_rankings": False},
    )
    counts = res["data"]["meta"]["emitted_by_entity"]
    assert counts["ranking"] == 0
    assert counts["product"] == 3
    assert counts["brand"] == 1
    assert res["data"]["meta"]["skipped_by_reason"].get("rankings_disabled") == 2


async def test_include_brands_false(snapshot_rows: list[dict]) -> None:
    """``include_brands=False`` drops every brand row."""
    client = CosmeClient()
    res = client.build_envelope_for_rows(
        snapshot_rows,
        public_inputs={"include_brands": False},
    )
    counts = res["data"]["meta"]["emitted_by_entity"]
    assert counts["brand"] == 0
    assert res["data"]["meta"]["skipped_by_reason"].get("brands_disabled") == 1


# ----------------------------------------------------------------------------
# Invalid-inputs paths (no BrightData call)
# ----------------------------------------------------------------------------


async def test_invalid_inputs_year() -> None:
    """``year=1999`` (below min) => INVALID_INPUTS, BrightData NOT called."""
    res = await trigger({"year": 1999})
    assert res["status"] == "failed"
    assert res["error"]["code"] == "INVALID_INPUTS"
    assert res["error"]["retriable"] is False


async def test_invalid_inputs_max_products() -> None:
    """``max_products=99999`` (above max) => INVALID_INPUTS."""
    res = await trigger({"max_products": 99999})
    assert res["status"] == "failed"
    assert res["error"]["code"] == "INVALID_INPUTS"


async def test_invalid_inputs_mode() -> None:
    """``mode='daily'`` (not in enum) => INVALID_INPUTS."""
    res = await trigger({"mode": "daily"})
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
    """Default inputs → single seed targeting the current year archive."""
    client = CosmeClient()
    seeds = client._build_brightdata_inputs(CosmeInputs())
    assert len(seeds) == 1
    seed = seeds[0]
    assert "grand" in seed["url"]
    assert seed["crawl_limit"] == 1000
    # No category filter by default.
    assert "category" not in seed


async def test_input_translation_with_year_and_category() -> None:
    """Explicit year + category → URL + filter forwarded to Stage 1."""
    client = CosmeClient()
    seeds = client._build_brightdata_inputs(
        CosmeInputs(year=2025, category="serum", max_categories=5)
    )
    assert seeds == [
        {
            "url": "https://www.cosme.net/bestcosme/archive/2025/grand/",
            "crawl_limit": 5,
            "category": "serum",
        }
    ]


async def test_input_translation_max_products_not_in_seed() -> None:
    """``max_products`` is post-download; never in the trigger seed."""
    client = CosmeClient()
    seeds = client._build_brightdata_inputs(
        CosmeInputs(max_products=1, mode="incremental")
    )
    assert "max_products" not in seeds[0]


# ----------------------------------------------------------------------------
# Row coercion & classification
# ----------------------------------------------------------------------------


async def test_coerce_product_fills_missing_keys() -> None:
    """A sparse product row still emits every §2/§4 key."""
    raw = {"product_id": "minimal", "product_url": "https://www.cosme.net/products/minimal/"}
    out = _coerce_product(raw)
    for key in PRODUCT_FIELDS:
        assert key in out
    assert out["entity"] == "product"
    assert out["url"] == "https://www.cosme.net/products/minimal/"
    assert out["variants"] == []
    assert out["scraper_flags"] == []
    assert out["brand_id"] is None


async def test_coerce_ranking_fills_missing_keys() -> None:
    raw = {"source_type": "bestcosme", "rank": 1, "award_year": 2025}
    out = _coerce_ranking(raw)
    for key in RANKING_FIELDS:
        assert key in out
    assert out["entity"] == "ranking"
    assert out["year"] == 2025
    assert out["ai_highlights"] == []


async def test_coerce_brand_fills_missing_keys() -> None:
    raw = {"brand_id": "73", "brand_name": "SK-II"}
    out = _coerce_brand(raw)
    for key in BRAND_FIELDS:
        assert key in out
    assert out["entity"] == "brand"
    assert out["name"] == "SK-II"
    assert out["country"] is None


async def test_classify_entity_explicit() -> None:
    """Explicit ``entity`` key wins over heuristic."""
    assert _classify_entity({"entity": "brand", "product_id": "x"}) == "brand"
    assert _classify_entity({"_entity": "ranking"}) == "ranking"


async def test_classify_entity_heuristic_ranking() -> None:
    """``source_type`` + ``rank`` => ranking."""
    assert _classify_entity({"source_type": "bestcosme", "rank": 1}) == "ranking"


async def test_classify_entity_heuristic_product() -> None:
    """``product_id`` => product (when no ranking signal)."""
    assert _classify_entity({"product_id": "10248076"}) == "product"


async def test_classify_entity_heuristic_brand() -> None:
    """``brand_id`` + total_products => brand."""
    row = {"brand_id": "73", "brand_total_products": 10}
    assert _classify_entity(row) == "brand"


async def test_classify_entity_unknown() -> None:
    """Row without any signal => None (counted under skipped_by_reason)."""
    assert _classify_entity({"foo": "bar"}) is None


async def test_unknown_entity_counted(snapshot_rows: list[dict]) -> None:
    """An un-classifiable row lands in ``skipped_by_reason['unknown_entity']``."""
    rows = snapshot_rows + [{"foo": "bar"}]
    client = CosmeClient()
    res = client.build_envelope_for_rows(rows, public_inputs={})
    assert res["data"]["meta"]["skipped_by_reason"].get("unknown_entity") == 1


async def test_non_dict_row_counted() -> None:
    """Non-dict row => counted under ``errors`` and ``non_dict_row``."""
    rows: list[Any] = [{"product_id": "1", "product_url": "u"}, "not-a-dict", 42]
    client = CosmeClient()
    res = client.build_envelope_for_rows(rows, public_inputs={})
    meta = res["data"]["meta"]
    assert meta["errors"] == 2
    assert meta["skipped_by_reason"].get("non_dict_row") == 2


# ----------------------------------------------------------------------------
# BLOCK_SATURATION
# ----------------------------------------------------------------------------


async def test_block_saturation_threshold() -> None:
    """>50% of product rows carrying rate_limit_blocked => BLOCK_SATURATION."""
    rows: list[dict[str, Any]] = []
    for i in range(10):
        rows.append({
            "product_id": f"blocked_{i}",
            "product_url": f"https://www.cosme.net/products/blocked_{i}/",
            "product_name_raw": None,
            "scraper_flags": ["rate_limit_blocked"] if i < 6 else [],
            "variants": [],
            "category_ids": [],
            "effect_ids": [],
            "ingredient_tag_ids": [],
        })
    client = CosmeClient()
    res = client.build_envelope_for_rows(rows, public_inputs={"max_products": 100})
    final = _maybe_block_saturation(res)
    assert final["status"] == "failed"
    assert final["error"]["code"] == "BLOCK_SATURATION"
    assert final["error"]["retriable"] is False
    assert final["error"]["details"]["products"] == 10
    assert final["error"]["details"]["blocked"] == 6


async def test_block_saturation_below_threshold() -> None:
    """≤50% blocked => envelope returned as-is."""
    rows: list[dict[str, Any]] = []
    for i in range(10):
        rows.append({
            "product_id": f"p_{i}",
            "product_url": f"https://www.cosme.net/products/p_{i}/",
            "scraper_flags": ["rate_limit_blocked"] if i < 3 else [],
            "variants": [],
            "category_ids": [],
            "effect_ids": [],
            "ingredient_tag_ids": [],
        })
    client = CosmeClient()
    res = client.build_envelope_for_rows(rows, public_inputs={"max_products": 100})
    final = _maybe_block_saturation(res)
    assert final["status"] == "done"


# ----------------------------------------------------------------------------
# Credentials / dual-mode selection
# ----------------------------------------------------------------------------


async def test_credentials_required_at_trigger(monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing credentials surface as INVALID_INPUTS at trigger time."""
    monkeypatch.delenv("BRIGHTDATA_API_KEY", raising=False)
    monkeypatch.delenv("BRIGHTDATA_DATASET_ID_COSME", raising=False)
    monkeypatch.delenv("BRIGHTDATA_COLLECTOR_ID_COSME", raising=False)
    res = await trigger({})
    assert res["status"] == "failed"
    assert res["error"]["code"] == "INVALID_INPUTS"


async def test_resolve_mode_v3_wins_over_dca(monkeypatch: pytest.MonkeyPatch) -> None:
    """When both env vars are set, v3 wins."""
    monkeypatch.setenv("BRIGHTDATA_DATASET_ID_COSME", "gd_test_v3")
    monkeypatch.setenv("BRIGHTDATA_COLLECTOR_ID_COSME", "c_test_dca")
    client = CosmeClient()
    assert client.api_mode == "v3"
    assert client.resource_id == "gd_test_v3"


async def test_resolve_mode_dca_when_only_dca_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("BRIGHTDATA_DATASET_ID_COSME", raising=False)
    monkeypatch.setenv("BRIGHTDATA_COLLECTOR_ID_COSME", "c_test_dca")
    client = CosmeClient()
    assert client.api_mode == "dca"
    assert client.resource_id == "c_test_dca"


async def test_resolve_mode_v3_when_only_v3_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BRIGHTDATA_DATASET_ID_COSME", "gd_test_v3")
    monkeypatch.delenv("BRIGHTDATA_COLLECTOR_ID_COSME", raising=False)
    client = CosmeClient()
    assert client.api_mode == "v3"
    assert client.resource_id == "gd_test_v3"


async def test_resolve_mode_none_surfaces_invalid_inputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No env vars populated → ``INVALID_INPUTS`` naming both env vars in msg."""
    monkeypatch.setenv("BRIGHTDATA_API_KEY", "fake_key_for_test")
    monkeypatch.delenv("BRIGHTDATA_DATASET_ID_COSME", raising=False)
    monkeypatch.delenv("BRIGHTDATA_COLLECTOR_ID_COSME", raising=False)
    res = await trigger({})
    assert res["status"] == "failed"
    assert res["error"]["code"] == "INVALID_INPUTS"
    msg = res["error"]["message"]
    assert "BRIGHTDATA_DATASET_ID_COSME" in msg
    assert "BRIGHTDATA_COLLECTOR_ID_COSME" in msg


async def test_explicit_api_mode_overrides_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Explicit ``api_mode=`` and ``resource_id=`` beat env vars."""
    monkeypatch.setenv("BRIGHTDATA_DATASET_ID_COSME", "gd_env")
    monkeypatch.setenv("BRIGHTDATA_COLLECTOR_ID_COSME", "c_env")
    client = CosmeClient(api_mode="dca", resource_id="c_override")
    assert client.api_mode == "dca"
    assert client.resource_id == "c_override"


async def test_dataset_id_alias_silent_backwards_compat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``dataset_id=`` kwarg aliases ``resource_id=`` silently (no warning)."""
    import warnings

    monkeypatch.delenv("BRIGHTDATA_DATASET_ID_COSME", raising=False)
    monkeypatch.delenv("BRIGHTDATA_COLLECTOR_ID_COSME", raising=False)
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        client = CosmeClient(dataset_id="gd_from_alias")
    assert client.resource_id == "gd_from_alias"
    assert client.api_mode == "v3"
    assert not any(
        issubclass(w.category, DeprecationWarning) for w in captured
    ), [str(w.message) for w in captured]


# ----------------------------------------------------------------------------
# TOOL_SCHEMA / error catalog
# ----------------------------------------------------------------------------


async def test_tool_schema_shape() -> None:
    """TOOL_SCHEMA is the exact dict shape Anthropic API expects."""
    assert isinstance(TOOL_SCHEMA, list) and len(TOOL_SCHEMA) == 2
    names = {t["name"] for t in TOOL_SCHEMA}
    assert names == {"cosme_trigger", "cosme_get_result"}
    for tool in TOOL_SCHEMA:
        assert "description" in tool
        assert "input_schema" in tool
        assert tool["input_schema"]["type"] == "object"
        assert tool["input_schema"].get("additionalProperties") is False


async def test_per_scraper_error_codes_extendcore() -> None:
    """The cosme error code extension does not redefine base codes."""
    for code in COSME_ERROR_CODES:
        assert code not in NORMALIZED_CODES, (
            f"Per-scraper code {code!r} collides with base catalog."
        )


async def test_pydantic_row_models_smoke(snapshot_rows: list[dict]) -> None:
    """Every fixture row round-trips through its entity model cleanly."""
    for raw in snapshot_rows:
        if "source_type" in raw:
            # Apply the alias ourselves before the model validates — the
            # middleware would do this, but we want to exercise the model
            # directly here.
            row = dict(raw)
            if "award_year" in row:
                row["year"] = row.pop("award_year")
            if "award_group" in row:
                row["group"] = row.pop("award_group")
            if "award_category_slug" in row:
                row["category_slug"] = row.pop("award_category_slug")
            assert RankingRow(**row)
        elif "brand_total_products" in raw:
            row = dict(raw)
            for src, dst in [
                ("brand_name", "name"),
                ("brand_url", "url"),
                ("brand_total_products", "total_products"),
                ("brand_total_reviews", "total_reviews"),
                ("brand_official_site", "official_site"),
                ("brand_country", "country"),
            ]:
                if src in row:
                    row[dst] = row.pop(src)
            assert BrandRow(**row)
        else:
            # Product.
            row = dict(raw)
            for src, dst in [
                ("product_url", "url"),
                ("product_name_raw", "name_raw"),
                ("product_name_clean", "name_clean"),
            ]:
                if src in row:
                    row[dst] = row.pop(src)
            assert ProductRow(**row)
