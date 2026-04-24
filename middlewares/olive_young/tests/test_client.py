"""Unit + fixture tests for the olive_young middleware.

Coverage map:
    - test_trigger_happy_path               — @brightdata live (skipped w/o env)
    - test_get_result_done_from_fixture     — parses canonical fixture
    - test_envelope_shape                    — exact top-level keys
    - test_multi_entity_data_split           — ranking/product/brand counts
    - test_ranking_keys_complete             — spec §2+§4 keys present
    - test_product_keys_complete             — spec §2+§5 keys present
    - test_brand_keys_complete               — spec §2+§6 keys present
    - test_aliases_applied                    — region_code→region, etc.
    - test_max_products_cap                   — emitted product ≤ max_products
    - test_include_*_false                    — drops respective entity
    - test_input_translation                  — public → JS-scraper input
    - test_invalid_inputs_*                   — INVALID_INPUTS paths
    - test_resolve_mode_*                     — dual-mode selection
    - test_block_saturation_threshold         — BLOCK_SATURATION code
"""

from __future__ import annotations

import os
from typing import Any

import pytest

from middlewares.core.envelope import Envelope
from middlewares.core.errors import NORMALIZED_CODES
from middlewares.olive_young import (
    TOOL_SCHEMA,
    BrandRow,
    OliveYoungClient,
    OliveYoungInputs,
    ProductRow,
    RankingRow,
    trigger,
)
from middlewares.olive_young.client import (
    OLIVE_YOUNG_ERROR_CODES,
    _classify_entity,
    _coerce_brand,
    _coerce_product,
    _coerce_ranking,
    _maybe_block_saturation,
)
from middlewares.olive_young.config import (
    RANKINGS_API_HOST,
)
from middlewares.olive_young.models import (
    BRAND_FIELDS,
    BRAND_LIST_FIELDS,
    PRODUCT_FIELDS,
    PRODUCT_LIST_FIELDS,
    RANKING_FIELDS,
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
        ("v3", "BRIGHTDATA_DATASET_ID_OLIVE_YOUNG"),
        ("dca", "BRIGHTDATA_COLLECTOR_ID_OLIVE_YOUNG"),
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

    client = OliveYoungClient(api_mode=api_mode, resource_id=resource_id)
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
    client = OliveYoungClient()
    res = client.build_envelope_for_rows(
        snapshot_rows,
        public_inputs={"max_products": 100},
    )
    assert res["status"] == "done"
    env = res["data"]
    assert env["source"] == "olive-young"
    assert isinstance(env["data"], list)
    assert len(env["data"]) == len(snapshot_rows)
    # Also pydantic-validates
    Envelope(**env)


async def test_envelope_shape(snapshot_rows: list[dict]) -> None:
    """Top-level envelope keys are EXACTLY the contracted set (no extras)."""
    client = OliveYoungClient()
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
    client = OliveYoungClient()
    res = client.build_envelope_for_rows(snapshot_rows, public_inputs={})
    counts = res["data"]["meta"]["emitted_by_entity"]
    # Fixture layout: 4 rankings + 3 products + 2 brands.
    assert counts["ranking"] == 4
    assert counts["product"] == 3
    assert counts["brand"] == 2
    entities = [row["entity"] for row in res["data"]["data"]]
    assert entities.count("ranking") == 4
    assert entities.count("product") == 3
    assert entities.count("brand") == 2


async def test_ranking_keys_complete(snapshot_rows: list[dict]) -> None:
    """Every emitted ranking row has all §2/§4 keys (null/[] allowed)."""
    client = OliveYoungClient()
    res = client.build_envelope_for_rows(snapshot_rows, public_inputs={})
    rankings = [row for row in res["data"]["data"] if row["entity"] == "ranking"]
    assert rankings, "fixture should contain at least one ranking"
    for row in rankings:
        for key in RANKING_FIELDS:
            assert key in row, f"missing key {key!r} in ranking row {row.get('ranking_id')}"
        for key in RANKING_LIST_FIELDS:
            assert isinstance(row[key], list), (
                f"key {key!r} in ranking row must be a list, "
                f"got {type(row[key]).__name__}"
            )


async def test_product_keys_complete(snapshot_rows: list[dict]) -> None:
    """Every product row has all §2/§5 keys."""
    client = OliveYoungClient()
    res = client.build_envelope_for_rows(snapshot_rows, public_inputs={})
    products = [row for row in res["data"]["data"] if row["entity"] == "product"]
    assert products
    for row in products:
        for key in PRODUCT_FIELDS:
            assert key in row, f"missing key {key!r} in product row {row.get('prdt_no')}"
        for key in PRODUCT_LIST_FIELDS:
            assert isinstance(row[key], list), (
                f"key {key!r} in product row must be a list, "
                f"got {type(row[key]).__name__}"
            )


async def test_brand_keys_complete(snapshot_rows: list[dict]) -> None:
    """Every brand row has all §2/§6 keys."""
    client = OliveYoungClient()
    res = client.build_envelope_for_rows(snapshot_rows, public_inputs={})
    brands = [row for row in res["data"]["data"] if row["entity"] == "brand"]
    assert brands
    for row in brands:
        for key in BRAND_FIELDS:
            assert key in row, f"missing key {key!r} in brand row {row.get('brand_no')}"
        for key in BRAND_LIST_FIELDS:
            assert isinstance(row[key], list), (
                f"key {key!r} in brand row must be a list, "
                f"got {type(row[key]).__name__}"
            )


async def test_aliases_applied(snapshot_rows: list[dict]) -> None:
    """Scraper-native keys renamed to §2 short forms on the wire."""
    client = OliveYoungClient()
    res = client.build_envelope_for_rows(snapshot_rows, public_inputs={})
    data = res["data"]["data"]
    # Ranking row (pick the first KR/All one): region_code→region,
    # category_id→cat_id, product_name_en→name_en, promotion_name→promo.
    ranking = next(
        row
        for row in data
        if row["entity"] == "ranking"
        and row.get("ranking_id") == "oliveyoung-global_KR_1000000001_1_2026-04-21"
    )
    assert ranking["region"] == "KR"
    assert ranking["cat_id"] == "1000000001"
    assert ranking["name_en"] == "Anua Heartleaf 77% Soothing Toner"
    assert ranking["promo"] == "Bundle Deal -15%"
    assert ranking["brand_no"] == "B00051"

    # Product row: product_url→url, product_name_clean_*→name_clean_*.
    prod = next(
        row for row in data if row["entity"] == "product" and row.get("prdt_no") == "GA240824996"
    )
    assert prod["url"] == "https://global.oliveyoung.com/product/detail?prdtNo=GA240824996"
    assert prod["name_clean_en"] == "Anua Heartleaf 77% Soothing Toner"
    assert prod["name_clean_kr"] == "아누아 어성초 77% 수딩 토너"
    assert prod["best_regions"] == ["KR", "USA"]
    assert prod["claim_tags"] == ["Vegan", "Clean Beauty"]

    # Brand row: brand_url→url, brand_name_en→name_en, brand_name_kr→name_kr,
    # brand_total_products_in_rankings→total_in_rankings, brand_avg_rank→avg_rank.
    brand = next(
        row for row in data if row["entity"] == "brand" and row.get("brand_no") == "B00051"
    )
    assert brand["name_en"] == "Anua"
    assert brand["name_kr"] == "아누아"
    assert brand["url"] == "https://global.oliveyoung.com/display/page/brand-page?brandNo=B00051"
    assert brand["total_in_rankings"] == 6
    assert brand["avg_rank"] == 4.5


async def test_max_products_cap(snapshot_rows: list[dict]) -> None:
    """``max_products`` caps emitted product rows (rankings/brands unaffected)."""
    client = OliveYoungClient()
    res = client.build_envelope_for_rows(
        snapshot_rows,
        public_inputs={"max_products": 2},
    )
    counts = res["data"]["meta"]["emitted_by_entity"]
    assert counts["product"] == 2
    # Rankings (4) and brands (2) are untouched by max_products.
    assert counts["ranking"] == 4
    assert counts["brand"] == 2
    assert res["data"]["meta"]["skipped_by_reason"].get("max_products_cap") == 1


async def test_include_rankings_false(snapshot_rows: list[dict]) -> None:
    """``include_rankings=False`` drops every ranking row."""
    client = OliveYoungClient()
    res = client.build_envelope_for_rows(
        snapshot_rows,
        public_inputs={"include_rankings": False},
    )
    counts = res["data"]["meta"]["emitted_by_entity"]
    assert counts["ranking"] == 0
    assert counts["product"] == 3
    assert counts["brand"] == 2
    assert res["data"]["meta"]["skipped_by_reason"].get("rankings_disabled") == 4


async def test_include_products_false(snapshot_rows: list[dict]) -> None:
    """``include_products=False`` drops every product row."""
    client = OliveYoungClient()
    res = client.build_envelope_for_rows(
        snapshot_rows,
        public_inputs={"include_products": False},
    )
    counts = res["data"]["meta"]["emitted_by_entity"]
    assert counts["product"] == 0
    assert counts["ranking"] == 4
    assert counts["brand"] == 2
    assert res["data"]["meta"]["skipped_by_reason"].get("products_disabled") == 3


async def test_include_brands_false(snapshot_rows: list[dict]) -> None:
    """``include_brands=False`` drops every brand row."""
    client = OliveYoungClient()
    res = client.build_envelope_for_rows(
        snapshot_rows,
        public_inputs={"include_brands": False},
    )
    counts = res["data"]["meta"]["emitted_by_entity"]
    assert counts["brand"] == 0
    assert res["data"]["meta"]["skipped_by_reason"].get("brands_disabled") == 2


# ----------------------------------------------------------------------------
# Invalid-inputs paths (no BrightData call)
# ----------------------------------------------------------------------------


async def test_invalid_inputs_bad_region() -> None:
    """``regions=['EU']`` (not in enum) => INVALID_INPUTS, no BrightData call."""
    res = await trigger({"regions": ["EU"]})
    assert res["status"] == "failed"
    assert res["error"]["code"] == "INVALID_INPUTS"
    assert res["error"]["retriable"] is False


async def test_invalid_inputs_empty_regions() -> None:
    """``regions=[]`` (min_length=1) => INVALID_INPUTS."""
    res = await trigger({"regions": []})
    assert res["status"] == "failed"
    assert res["error"]["code"] == "INVALID_INPUTS"


async def test_invalid_inputs_max_products() -> None:
    """``max_products=99999`` (above max) => INVALID_INPUTS."""
    res = await trigger({"max_products": 99999})
    assert res["status"] == "failed"
    assert res["error"]["code"] == "INVALID_INPUTS"


async def test_invalid_inputs_max_brand_visits_negative() -> None:
    """``max_brand_visits=-1`` (below min) => INVALID_INPUTS."""
    res = await trigger({"max_brand_visits": -1})
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
    """Default inputs → single seed targeting the rankings API host."""
    client = OliveYoungClient()
    seeds = client._build_brightdata_inputs(OliveYoungInputs())
    assert len(seeds) == 1
    seed = seeds[0]
    assert seed["url"] == RANKINGS_API_HOST
    assert seed["regions"] == ["KR", "USA"]
    assert seed["max_brand_visits"] == 20
    # No category whitelist by default.
    assert "categories" not in seed


async def test_input_translation_with_categories_and_regions() -> None:
    """Explicit categories + regions subset → forwarded to Stage 1."""
    client = OliveYoungClient()
    seeds = client._build_brightdata_inputs(
        OliveYoungInputs(
            regions=["KR"],
            categories=["1000000008", "1000000031"],
            max_brand_visits=5,
        )
    )
    assert seeds == [
        {
            "url": RANKINGS_API_HOST,
            "regions": ["KR"],
            "max_brand_visits": 5,
            "categories": ["1000000008", "1000000031"],
        }
    ]


async def test_input_translation_max_products_not_in_seed() -> None:
    """``max_products`` is post-download; never in the trigger seed."""
    client = OliveYoungClient()
    seeds = client._build_brightdata_inputs(
        OliveYoungInputs(max_products=1, mode="incremental")
    )
    assert "max_products" not in seeds[0]


# ----------------------------------------------------------------------------
# Row coercion & classification
# ----------------------------------------------------------------------------


async def test_coerce_ranking_fills_missing_keys() -> None:
    """A sparse ranking row still emits every §2/§4 key."""
    raw = {
        "ranking_id": "oliveyoung-global_KR_1000000001_10_2026-04-21",
        "region_code": "KR",
        "category_id": "1000000001",
        "rank": 10,
        "prdt_no": "GA240000000",
    }
    out = _coerce_ranking(raw)
    for key in RANKING_FIELDS:
        assert key in out
    assert out["entity"] == "ranking"
    assert out["region"] == "KR"
    assert out["cat_id"] == "1000000001"
    assert out["scraper_flags"] == []
    assert out["name_en"] is None


async def test_coerce_product_fills_missing_keys() -> None:
    raw = {"prdt_no": "GA240000000", "product_url": "https://global.oliveyoung.com/product/detail?prdtNo=GA240000000"}
    out = _coerce_product(raw)
    for key in PRODUCT_FIELDS:
        assert key in out
    assert out["entity"] == "product"
    assert out["url"] == "https://global.oliveyoung.com/product/detail?prdtNo=GA240000000"
    assert out["category_ids"] == []
    assert out["ranks"] == []
    assert out["best_regions"] == []
    assert out["claim_tags"] == []
    assert out["scraper_flags"] == []


async def test_coerce_brand_fills_missing_keys() -> None:
    raw = {"brand_no": "B00051", "brand_name_en": "Anua"}
    out = _coerce_brand(raw)
    for key in BRAND_FIELDS:
        assert key in out
    assert out["entity"] == "brand"
    assert out["name_en"] == "Anua"
    assert out["total_in_rankings"] is None
    assert out["scraper_flags"] == []


async def test_classify_entity_explicit() -> None:
    """Explicit ``entity`` key wins over heuristic."""
    assert _classify_entity({"entity": "brand", "prdt_no": "GA240000000"}) == "brand"
    assert _classify_entity({"_entity": "ranking"}) == "ranking"


async def test_classify_entity_heuristic_ranking_by_id() -> None:
    """``ranking_id`` alone => ranking."""
    assert _classify_entity({"ranking_id": "x"}) == "ranking"


async def test_classify_entity_heuristic_ranking_by_shape() -> None:
    """``rank`` + ``prdt_no`` + ``region_code`` => ranking."""
    row = {"rank": 1, "prdt_no": "GA240000000", "region_code": "KR"}
    assert _classify_entity(row) == "ranking"


async def test_classify_entity_heuristic_product() -> None:
    """``prdt_no`` + product-only field => product (when no ranking signal)."""
    row = {"prdt_no": "GA240000000", "category_ids": ["1000000001"]}
    assert _classify_entity(row) == "product"


async def test_classify_entity_heuristic_brand() -> None:
    """``brand_no`` + total counter, no prdt_no => brand."""
    row = {"brand_no": "B00051", "brand_total_products_in_rankings": 6}
    assert _classify_entity(row) == "brand"


async def test_classify_entity_unknown() -> None:
    """Row without any signal => None (counted under skipped_by_reason)."""
    assert _classify_entity({"foo": "bar"}) is None


async def test_unknown_entity_counted(snapshot_rows: list[dict]) -> None:
    """An un-classifiable row lands in ``skipped_by_reason['unknown_entity']``."""
    rows = snapshot_rows + [{"foo": "bar"}]
    client = OliveYoungClient()
    res = client.build_envelope_for_rows(rows, public_inputs={})
    assert res["data"]["meta"]["skipped_by_reason"].get("unknown_entity") == 1


async def test_non_dict_row_counted() -> None:
    """Non-dict row => counted under ``errors`` and ``non_dict_row``."""
    rows: list[Any] = [
        {"ranking_id": "x", "region_code": "KR", "rank": 1, "prdt_no": "GA240000000"},
        "not-a-dict",
        42,
    ]
    client = OliveYoungClient()
    res = client.build_envelope_for_rows(rows, public_inputs={})
    meta = res["data"]["meta"]
    assert meta["errors"] == 2
    assert meta["skipped_by_reason"].get("non_dict_row") == 2


async def test_alias_does_not_overwrite_canonical() -> None:
    """If both the alias source and the canonical target exist, canonical wins."""
    raw = {
        "ranking_id": "x",
        "region": "KR",  # canonical (§2)
        "region_code": "USA",  # alias source (§4 prosa)
        "rank": 1,
        "prdt_no": "GA240000000",
    }
    out = _coerce_ranking(raw)
    assert out["region"] == "KR"
    # The alias-source value is preserved verbatim as an "extra" key.
    assert out.get("region_code") == "USA"


# ----------------------------------------------------------------------------
# BLOCK_SATURATION
# ----------------------------------------------------------------------------


async def test_block_saturation_threshold() -> None:
    """>50% of ranking rows carrying cloudflare_challenge => BLOCK_SATURATION."""
    rows: list[dict[str, Any]] = []
    for i in range(10):
        rows.append(
            {
                "ranking_id": f"r_{i}",
                "region_code": "KR",
                "category_id": "1000000001",
                "rank": i + 1,
                "prdt_no": f"GA2400000{i:02d}",
                "scraper_flags": ["cloudflare_challenge"] if i < 6 else [],
            }
        )
    client = OliveYoungClient()
    res = client.build_envelope_for_rows(rows, public_inputs={"max_products": 100})
    final = _maybe_block_saturation(res)
    assert final["status"] == "failed"
    assert final["error"]["code"] == "BLOCK_SATURATION"
    assert final["error"]["retriable"] is False
    assert final["error"]["details"]["rankings"] == 10
    assert final["error"]["details"]["blocked"] == 6


async def test_block_saturation_below_threshold() -> None:
    """≤50% blocked => envelope returned as-is."""
    rows: list[dict[str, Any]] = []
    for i in range(10):
        rows.append(
            {
                "ranking_id": f"r_{i}",
                "region_code": "KR",
                "category_id": "1000000001",
                "rank": i + 1,
                "prdt_no": f"GA2400000{i:02d}",
                "scraper_flags": ["cloudflare_challenge"] if i < 3 else [],
            }
        )
    client = OliveYoungClient()
    res = client.build_envelope_for_rows(rows, public_inputs={"max_products": 100})
    final = _maybe_block_saturation(res)
    assert final["status"] == "done"


async def test_block_saturation_api_400_counts() -> None:
    """``api_400`` flag also counts towards blocked (not just cloudflare_challenge)."""
    rows: list[dict[str, Any]] = [
        {
            "ranking_id": f"r_{i}",
            "region_code": "KR",
            "category_id": "1000000001",
            "rank": i + 1,
            "prdt_no": f"GA2400000{i:02d}",
            "scraper_flags": ["api_400"] if i < 7 else [],
        }
        for i in range(10)
    ]
    client = OliveYoungClient()
    res = client.build_envelope_for_rows(rows, public_inputs={"max_products": 100})
    final = _maybe_block_saturation(res)
    assert final["status"] == "failed"
    assert final["error"]["code"] == "BLOCK_SATURATION"


# ----------------------------------------------------------------------------
# Credentials / dual-mode selection
# ----------------------------------------------------------------------------


async def test_credentials_required_at_trigger(monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing credentials surface as INVALID_INPUTS at trigger time."""
    monkeypatch.delenv("BRIGHTDATA_API_KEY", raising=False)
    monkeypatch.delenv("BRIGHTDATA_DATASET_ID_OLIVE_YOUNG", raising=False)
    monkeypatch.delenv("BRIGHTDATA_COLLECTOR_ID_OLIVE_YOUNG", raising=False)
    res = await trigger({})
    assert res["status"] == "failed"
    assert res["error"]["code"] == "INVALID_INPUTS"


async def test_resolve_mode_v3_wins_over_dca(monkeypatch: pytest.MonkeyPatch) -> None:
    """When both env vars are set, v3 wins."""
    monkeypatch.setenv("BRIGHTDATA_DATASET_ID_OLIVE_YOUNG", "gd_test_v3")
    monkeypatch.setenv("BRIGHTDATA_COLLECTOR_ID_OLIVE_YOUNG", "c_test_dca")
    client = OliveYoungClient()
    assert client.api_mode == "v3"
    assert client.resource_id == "gd_test_v3"


async def test_resolve_mode_dca_when_only_dca_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("BRIGHTDATA_DATASET_ID_OLIVE_YOUNG", raising=False)
    monkeypatch.setenv("BRIGHTDATA_COLLECTOR_ID_OLIVE_YOUNG", "c_test_dca")
    client = OliveYoungClient()
    assert client.api_mode == "dca"
    assert client.resource_id == "c_test_dca"


async def test_resolve_mode_v3_when_only_v3_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BRIGHTDATA_DATASET_ID_OLIVE_YOUNG", "gd_test_v3")
    monkeypatch.delenv("BRIGHTDATA_COLLECTOR_ID_OLIVE_YOUNG", raising=False)
    client = OliveYoungClient()
    assert client.api_mode == "v3"
    assert client.resource_id == "gd_test_v3"


async def test_resolve_mode_none_surfaces_invalid_inputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No env vars populated → ``INVALID_INPUTS`` naming both env vars in msg."""
    monkeypatch.setenv("BRIGHTDATA_API_KEY", "fake_key_for_test")
    monkeypatch.delenv("BRIGHTDATA_DATASET_ID_OLIVE_YOUNG", raising=False)
    monkeypatch.delenv("BRIGHTDATA_COLLECTOR_ID_OLIVE_YOUNG", raising=False)
    res = await trigger({})
    assert res["status"] == "failed"
    assert res["error"]["code"] == "INVALID_INPUTS"
    msg = res["error"]["message"]
    assert "BRIGHTDATA_DATASET_ID_OLIVE_YOUNG" in msg
    assert "BRIGHTDATA_COLLECTOR_ID_OLIVE_YOUNG" in msg


async def test_explicit_api_mode_overrides_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Explicit ``api_mode=`` and ``resource_id=`` beat env vars."""
    monkeypatch.setenv("BRIGHTDATA_DATASET_ID_OLIVE_YOUNG", "gd_env")
    monkeypatch.setenv("BRIGHTDATA_COLLECTOR_ID_OLIVE_YOUNG", "c_env")
    client = OliveYoungClient(api_mode="dca", resource_id="c_override")
    assert client.api_mode == "dca"
    assert client.resource_id == "c_override"


async def test_dataset_id_alias_silent_backwards_compat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``dataset_id=`` kwarg aliases ``resource_id=`` silently (no warning)."""
    import warnings

    monkeypatch.delenv("BRIGHTDATA_DATASET_ID_OLIVE_YOUNG", raising=False)
    monkeypatch.delenv("BRIGHTDATA_COLLECTOR_ID_OLIVE_YOUNG", raising=False)
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        client = OliveYoungClient(dataset_id="gd_from_alias")
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
    assert names == {"olive_young_trigger", "olive_young_get_result"}
    for tool in TOOL_SCHEMA:
        assert "description" in tool
        assert "input_schema" in tool
        assert tool["input_schema"]["type"] == "object"
        assert tool["input_schema"].get("additionalProperties") is False


async def test_per_scraper_error_codes_extendcore() -> None:
    """The olive-young error code extension does not redefine base codes."""
    for code in OLIVE_YOUNG_ERROR_CODES:
        assert code not in NORMALIZED_CODES, (
            f"Per-scraper code {code!r} collides with base catalog."
        )


async def test_pydantic_row_models_smoke(snapshot_rows: list[dict]) -> None:
    """Every fixture row round-trips through its entity model cleanly."""
    for raw in snapshot_rows:
        if "ranking_id" in raw or (
            "rank" in raw and "prdt_no" in raw and "region_code" in raw
        ):
            # Apply the aliases ourselves before the model validates — the
            # middleware would do this, but we exercise the model directly here.
            row = dict(raw)
            for src, dst in [
                ("region_code", "region"),
                ("category_id", "cat_id"),
                ("product_name_en", "name_en"),
                ("promotion_name", "promo"),
            ]:
                if src in row and dst not in row:
                    row[dst] = row.pop(src)
            assert RankingRow(**row)
        elif "brand_total_products_in_rankings" in raw or (
            "brand_no" in raw and "brand_url" in raw and "prdt_no" not in raw
        ):
            row = dict(raw)
            for src, dst in [
                ("brand_name_en", "name_en"),
                ("brand_name_kr", "name_kr"),
                ("brand_url", "url"),
                ("brand_total_products_in_rankings", "total_in_rankings"),
                ("brand_avg_rank", "avg_rank"),
            ]:
                if src in row and dst not in row:
                    row[dst] = row.pop(src)
            assert BrandRow(**row)
        else:
            # Product.
            row = dict(raw)
            for src, dst in [
                ("product_url", "url"),
                ("product_name_clean_en", "name_clean_en"),
                ("product_name_clean_kr", "name_clean_kr"),
            ]:
                if src in row and dst not in row:
                    row[dst] = row.pop(src)
            assert ProductRow(**row)
