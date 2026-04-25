"""Unit + fixture tests for the made_in_china middleware.

Coverage map:
    - test_trigger_happy_path                 — @brightdata live (skipped w/o env)
    - test_get_result_done_from_fixture       — parses canonical fixture
    - test_envelope_shape                      — exact top-level keys
    - test_multi_entity_data_split             — product/supplier counts
    - test_product_keys_complete               — spec §2 keys present
    - test_supplier_keys_complete              — spec §2 keys present
    - test_aliases_applied                     — url → product_url, etc.
    - test_site_code_defaulted                 — spec §4 fixed value
    - test_fixture_obligatorio_iefutrgocdrz    — spec §11 regression
    - test_max_products_cap                    — emitted product ≤ max_products
    - test_max_suppliers_cap                   — emitted supplier ≤ max_suppliers
    - test_include_suppliers_false             — drops supplier rows
    - test_require_price_drops_rows            — skip rows without prices
    - test_country_normalization               — Vietnam → VN
    - test_country_unmapped_flag               — unknown country flagged
    - test_input_translation                    — public → JS-scraper input
    - test_invalid_inputs_*                     — INVALID_INPUTS paths
    - test_resolve_mode_*                       — dual-mode selection
    - test_block_saturation_threshold          — BOT_BLOCK_SATURATION code
    - test_structure_degraded_threshold        — STRUCTURE_CHANGED code
"""

from __future__ import annotations

import os
from typing import Any

import pytest

from gli_scrapers.core.envelope import Envelope
from gli_scrapers.core.errors import NORMALIZED_CODES
from gli_scrapers.made_in_china import (
    TOOL_SCHEMA,
    MadeInChinaClient,
    MadeInChinaInputs,
    ProductRow,
    SupplierRow,
    trigger,
)
from gli_scrapers.made_in_china.client import (
    MADE_IN_CHINA_ERROR_CODES,
    _classify_entity,
    _coerce_product,
    _coerce_supplier,
    _maybe_block_saturation,
    _maybe_structure_degraded,
    _normalize_country_inplace,
)
from gli_scrapers.made_in_china.config import (
    DEFAULT_LISTING_URL,
    DEFAULT_MAX_PAGES,
    iso2_for_country,
)
from gli_scrapers.made_in_china.models import (
    PRODUCT_FIELDS,
    PRODUCT_LIST_FIELDS,
    SUPPLIER_FIELDS,
    SUPPLIER_LIST_FIELDS,
)

pytestmark = pytest.mark.asyncio


# ----------------------------------------------------------------------------
# Live BrightData (skipped unless env vars set, see conftest.py)
# ----------------------------------------------------------------------------


@pytest.mark.brightdata
@pytest.mark.parametrize(
    "api_mode,resource_env",
    [
        ("v3", "BRIGHTDATA_DATASET_ID_MADE_IN_CHINA"),
        ("dca", "BRIGHTDATA_COLLECTOR_ID_MADE_IN_CHINA"),
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

    client = MadeInChinaClient(api_mode=api_mode, resource_id=resource_id)
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
    client = MadeInChinaClient()
    res = client.build_envelope_for_rows(
        snapshot_rows,
        public_inputs={"max_products": 100, "max_suppliers": 100},
    )
    assert res["status"] == "done"
    env = res["data"]
    assert env["source"] == "made-in-china"
    assert isinstance(env["data"], list)
    assert len(env["data"]) == len(snapshot_rows)
    Envelope(**env)


async def test_envelope_shape(snapshot_rows: list[dict]) -> None:
    """Top-level envelope keys are EXACTLY the contracted set (no extras)."""
    client = MadeInChinaClient()
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
        "structural_degraded",
        "errors",
        "started_at",
        "ended_at",
    ):
        assert key in env["meta"], f"meta missing {key!r}"


async def test_multi_entity_data_split(snapshot_rows: list[dict]) -> None:
    """Each row classified under the correct entity discriminator."""
    client = MadeInChinaClient()
    res = client.build_envelope_for_rows(snapshot_rows, public_inputs={})
    counts = res["data"]["meta"]["emitted_by_entity"]
    # Fixture layout: 4 products + 2 suppliers.
    assert counts["product"] == 4
    assert counts["supplier"] == 2
    entities = [row["entity"] for row in res["data"]["data"]]
    assert entities.count("product") == 4
    assert entities.count("supplier") == 2


async def test_product_keys_complete(snapshot_rows: list[dict]) -> None:
    """Every emitted product row has all §2 keys (null/[] allowed)."""
    client = MadeInChinaClient()
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


async def test_supplier_keys_complete(snapshot_rows: list[dict]) -> None:
    """Every supplier row has all §2 / §6 keys."""
    client = MadeInChinaClient()
    res = client.build_envelope_for_rows(snapshot_rows, public_inputs={})
    suppliers = [row for row in res["data"]["data"] if row["entity"] == "supplier"]
    assert suppliers
    for row in suppliers:
        for key in SUPPLIER_FIELDS:
            assert key in row, f"missing key {key!r} in supplier row"
        for key in SUPPLIER_LIST_FIELDS:
            assert isinstance(row[key], list), (
                f"key {key!r} in supplier row {row.get('supplier_id')} must be a list, "
                f"got {type(row[key]).__name__}"
            )


async def test_aliases_applied(snapshot_rows: list[dict]) -> None:
    """Legacy parser keys renamed to §2 canonical names on the wire."""
    client = MadeInChinaClient()
    res = client.build_envelope_for_rows(snapshot_rows, public_inputs={})
    data = res["data"]["data"]
    # Row 3 (product_id=AbCdEfGhIjK1) uses ``url`` and ``name_original`` /
    # ``name_clean`` — legacy v1 names aliased to §2 by the middleware.
    packtech = next(
        row for row in data
        if row["entity"] == "product" and row.get("product_id") == "AbCdEfGhIjK1"
    )
    assert packtech["product_url"] == (
        "https://packtech.en.made-in-china.com/product/AbCdEfGhIjK1/"
        "PE-Stretch-Film-Wrapping-Plastic.html"
    )
    assert packtech["product_name_original"] == "PE Stretch Film Wrapping Plastic"
    assert packtech["product_name_clean"] == "PE Stretch Film Wrapping Plastic"


async def test_site_code_defaulted() -> None:
    """spec §4 fixes ``site_code = 'made-in-china'``; middleware enforces."""
    raw = {"product_id": "x", "product_url": "https://x.en.made-in-china.com/product/x/"}
    out = _coerce_product(raw)
    assert out["site_code"] == "made-in-china"


async def test_fixture_obligatorio_iefutrgocdrz(snapshot_rows: list[dict]) -> None:
    """spec §11 regression — product IEFUtrGOCdRZ must survive normalization.

    Guards against any middleware regression that might drop / rename the
    canonical fields of the fixture product.
    """
    client = MadeInChinaClient()
    res = client.build_envelope_for_rows(snapshot_rows, public_inputs={})
    data = res["data"]["data"]
    row = next(
        r for r in data
        if r["entity"] == "product" and r.get("product_id") == "IEFUtrGOCdRZ"
    )
    assert row["product_name_original"].startswith("CAS No. 123-86-4")
    assert row["price_min_usd"] == 800.0
    assert row["price_max_usd"] == 2000.0
    assert row["price_unit"] == "Ton"
    assert row["moq_quantity"] == 1
    assert row["moq_unit"] == "Ton"
    assert row["cas_no"] == "123-86-4"
    assert row["grade"] == "Industrial"
    assert row["supplier_id"] == "whjindo"
    assert row["type"] == "chemical"
    assert row["category_mic"] == "Organic Intermediate"
    assert row["site_code"] == "made-in-china"


async def test_max_products_cap(snapshot_rows: list[dict]) -> None:
    """``max_products`` caps emitted product rows (suppliers unaffected)."""
    client = MadeInChinaClient()
    res = client.build_envelope_for_rows(
        snapshot_rows,
        public_inputs={"max_products": 2, "max_suppliers": 100},
    )
    counts = res["data"]["meta"]["emitted_by_entity"]
    assert counts["product"] == 2
    # Suppliers (2) are untouched by max_products.
    assert counts["supplier"] == 2
    # Fixture has 4 products; 2 dropped via cap.
    assert res["data"]["meta"]["skipped_by_reason"].get("max_products_cap") == 2


async def test_max_suppliers_cap(snapshot_rows: list[dict]) -> None:
    """``max_suppliers`` caps emitted supplier rows (products unaffected)."""
    client = MadeInChinaClient()
    res = client.build_envelope_for_rows(
        snapshot_rows,
        public_inputs={"max_products": 100, "max_suppliers": 1},
    )
    counts = res["data"]["meta"]["emitted_by_entity"]
    assert counts["supplier"] == 1
    assert counts["product"] == 4
    assert res["data"]["meta"]["skipped_by_reason"].get("max_suppliers_cap") == 1


async def test_include_suppliers_false(snapshot_rows: list[dict]) -> None:
    """``include_suppliers=False`` drops every supplier row."""
    client = MadeInChinaClient()
    res = client.build_envelope_for_rows(
        snapshot_rows,
        public_inputs={"include_suppliers": False},
    )
    counts = res["data"]["meta"]["emitted_by_entity"]
    assert counts["supplier"] == 0
    assert counts["product"] == 4
    assert res["data"]["meta"]["skipped_by_reason"].get("suppliers_disabled") == 2


async def test_require_price_drops_rows(snapshot_rows: list[dict]) -> None:
    """``require_price=True`` drops product rows with both price fields null."""
    client = MadeInChinaClient()
    res = client.build_envelope_for_rows(
        snapshot_rows,
        public_inputs={"require_price": True, "max_products": 100},
    )
    counts = res["data"]["meta"]["emitted_by_entity"]
    # The bot-blocked row (BlkDnyBot001) has both prices null → drop.
    assert counts["product"] == 3
    assert res["data"]["meta"]["skipped_by_reason"].get("price_missing") == 1


# ----------------------------------------------------------------------------
# Country normalization
# ----------------------------------------------------------------------------


async def test_country_normalization(snapshot_rows: list[dict]) -> None:
    """Supplier row with free-text country ``"Vietnam"`` → ``"VN"``."""
    client = MadeInChinaClient()
    res = client.build_envelope_for_rows(snapshot_rows, public_inputs={})
    data = res["data"]["data"]
    supplier_vn = next(
        r for r in data
        if r["entity"] == "supplier" and r.get("supplier_id") == "phatphatvn"
    )
    assert supplier_vn["supplier_country"] == "VN"
    # The already-ISO supplier stays ISO.
    supplier_cn = next(
        r for r in data
        if r["entity"] == "supplier" and r.get("supplier_id") == "whjindo"
    )
    assert supplier_cn["supplier_country"] == "CN"


async def test_country_unmapped_flag() -> None:
    """Unknown country name → ``supplier_country = None`` + flag."""
    row = {
        "entity": "supplier",
        "supplier_id": "xx",
        "supplier_url": "https://xx.en.made-in-china.com/",
        "supplier_name": "XX",
        "supplier_country": "Atlantis",
        "business_type": "Manufacturer",
        "scraper_flags": [],
    }
    _normalize_country_inplace(row, "supplier")
    assert row["supplier_country"] is None
    assert "country_unmapped" in row["scraper_flags"]


async def test_iso2_lookup_case_insensitive() -> None:
    """``iso2_for_country`` is case-insensitive as a fallback."""
    assert iso2_for_country("china") == "CN"
    assert iso2_for_country("CHINA") == "CN"
    assert iso2_for_country(" Vietnam ") == "VN"
    assert iso2_for_country("Unknownland") is None
    assert iso2_for_country(None) is None
    assert iso2_for_country("") is None


async def test_country_normalization_skips_product_rows() -> None:
    """``origin_country`` on product rows is free text, NOT normalized."""
    row = {
        "entity": "product",
        "product_id": "x",
        "origin_country": "China",
        "scraper_flags": [],
    }
    _normalize_country_inplace(row, "product")
    # origin_country preserved verbatim (spec §5).
    assert row.get("origin_country") == "China"


# ----------------------------------------------------------------------------
# Invalid-inputs paths (no BrightData call)
# ----------------------------------------------------------------------------


async def test_invalid_inputs_max_pages_low() -> None:
    """``max_pages=-2`` (below min) => INVALID_INPUTS, BrightData NOT called."""
    res = await trigger({"max_pages": -2})
    assert res["status"] == "failed"
    assert res["error"]["code"] == "INVALID_INPUTS"
    assert res["error"]["retriable"] is False


async def test_invalid_inputs_max_products_high() -> None:
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


async def test_invalid_inputs_urls_too_many() -> None:
    """``urls`` above MAX_SEED_URLS => INVALID_INPUTS."""
    res = await trigger({"urls": ["https://example.com/x"] * 100})
    assert res["status"] == "failed"
    assert res["error"]["code"] == "INVALID_INPUTS"


# ----------------------------------------------------------------------------
# Translation: public inputs → JS scraper inputs
# ----------------------------------------------------------------------------


async def test_input_translation_default() -> None:
    """Default inputs → single seed with default listing URL + max_pages=3."""
    client = MadeInChinaClient()
    seeds = client._build_brightdata_inputs(MadeInChinaInputs())
    assert len(seeds) == 1
    seed = seeds[0]
    assert seed["url"] == DEFAULT_LISTING_URL
    assert "max_pages" not in seed
    assert "is_rerun" not in seed


async def test_input_translation_multi_url() -> None:
    """Multiple URLs → one seed per URL, all sharing the same max_pages."""
    urls = [
        "https://www.made-in-china.com/products-search/hot-china-products/Industrial_Chemicals.html",
        "https://www.made-in-china.com/Chemicals-Catalog/Alkali.html",
    ]
    client = MadeInChinaClient()
    seeds = client._build_brightdata_inputs(
        MadeInChinaInputs(urls=urls, max_pages=5)
    )
    assert len(seeds) == 2
    assert [s["url"] for s in seeds] == urls
    for s in seeds:
        assert "max_pages" not in s
        assert "is_rerun" not in s


async def test_input_translation_max_pages_minus_one() -> None:
    """``max_pages=-1`` is forwarded verbatim (spec §9 v5: crawl all pages)."""
    client = MadeInChinaClient()
    seeds = client._build_brightdata_inputs(
        MadeInChinaInputs(urls=["https://example.com/x"], max_pages=-1)
    )
    assert list(seeds[0].keys()) == ["url"]


async def test_input_translation_max_products_not_in_seed() -> None:
    """``max_products`` is post-download; never in the trigger seed."""
    client = MadeInChinaClient()
    seeds = client._build_brightdata_inputs(
        MadeInChinaInputs(max_products=10, mode="incremental")
    )
    assert "max_products" not in seeds[0]
    assert "mode" not in seeds[0]


# ----------------------------------------------------------------------------
# Row coercion & classification
# ----------------------------------------------------------------------------


async def test_coerce_product_fills_missing_keys() -> None:
    """A sparse product row still emits every §2 key."""
    raw = {"product_id": "minimal", "product_url": "https://x.en.made-in-china.com/product/minimal/"}
    out = _coerce_product(raw)
    for key in PRODUCT_FIELDS:
        assert key in out
    assert out["entity"] == "product"
    assert out["category_path"] == []
    assert out["scraper_flags"] == []
    assert out["cas_no"] is None
    assert out["site_code"] == "made-in-china"


async def test_coerce_supplier_fills_missing_keys() -> None:
    raw = {"supplier_id": "whjindo", "supplier_name": "WEIHAI JINDO"}
    out = _coerce_supplier(raw)
    for key in SUPPLIER_FIELDS:
        assert key in out
    assert out["entity"] == "supplier"
    assert out["management_certifications"] == []
    assert out["audited_supplier"] is None


async def test_classify_entity_explicit() -> None:
    """Explicit ``entity`` key wins over heuristic."""
    assert _classify_entity({"entity": "supplier", "product_id": "x"}) == "supplier"
    assert _classify_entity({"_entity": "product"}) == "product"
    # ``type`` column only taken as discriminator when literally product/supplier,
    # NOT when it holds the category enum (``chemical``, ``empaque``, ``other``).
    assert _classify_entity({"type": "chemical", "product_id": "x"}) == "product"
    assert _classify_entity({"type": "product"}) == "product"


async def test_classify_entity_heuristic_product() -> None:
    """``product_id`` / ``product_url`` / ``price_raw`` => product."""
    assert _classify_entity({"product_id": "x"}) == "product"
    assert _classify_entity({"product_url": "https://x.en.made-in-china.com/product/x/"}) == "product"
    assert _classify_entity({"price_raw": "US$10/kg"}) == "product"


async def test_classify_entity_heuristic_supplier() -> None:
    """``supplier_id`` + supplier-specific key without product signal => supplier."""
    assert _classify_entity({"supplier_id": "x", "business_type": "Manufacturer"}) == "supplier"
    assert _classify_entity({"supplier_id": "x", "member_level": "Gold"}) == "supplier"


async def test_classify_entity_supplier_alone_not_enough() -> None:
    """``supplier_id`` alone (no supplier-specific key, no product signal) is ambiguous."""
    # Keeps the behavior conservative: we demand an extra supplier signal so
    # a product row carrying only supplier_id (as every MIC product does) is
    # not misclassified as supplier.
    assert _classify_entity({"supplier_id": "whjindo"}) is None


async def test_classify_entity_unknown() -> None:
    """Row without any signal => None (counted under skipped_by_reason)."""
    assert _classify_entity({"foo": "bar"}) is None


async def test_unknown_entity_counted(snapshot_rows: list[dict]) -> None:
    """An un-classifiable row lands in ``skipped_by_reason['unknown_entity']``."""
    rows = snapshot_rows + [{"foo": "bar"}]
    client = MadeInChinaClient()
    res = client.build_envelope_for_rows(rows, public_inputs={})
    assert res["data"]["meta"]["skipped_by_reason"].get("unknown_entity") == 1


async def test_non_dict_row_counted() -> None:
    """Non-dict row => counted under ``errors`` and ``non_dict_row``."""
    rows: list[Any] = [
        {"product_id": "1", "product_url": "https://x.en.made-in-china.com/product/1/"},
        "not-a-dict",
        42,
    ]
    client = MadeInChinaClient()
    res = client.build_envelope_for_rows(rows, public_inputs={})
    meta = res["data"]["meta"]
    assert meta["errors"] == 2
    assert meta["skipped_by_reason"].get("non_dict_row") == 2


async def test_price_unit_unknown_flag() -> None:
    """Unknown price_unit string → ``price_unit_unknown`` flag added."""
    raw = {
        "product_id": "x",
        "product_url": "https://x.en.made-in-china.com/product/x/",
        "price_unit": "Trebuchet",  # not in KNOWN_PRICE_UNITS
        "scraper_flags": [],
    }
    out = _coerce_product(raw)
    assert "price_unit_unknown" in out["scraper_flags"]


async def test_price_unit_known_no_flag() -> None:
    """Known price_unit leaves flags untouched."""
    raw = {
        "product_id": "x",
        "product_url": "https://x.en.made-in-china.com/product/x/",
        "price_unit": "Kg",
        "scraper_flags": [],
    }
    out = _coerce_product(raw)
    assert "price_unit_unknown" not in out["scraper_flags"]


# ----------------------------------------------------------------------------
# BOT_BLOCK_SATURATION / STRUCTURE_CHANGED
# ----------------------------------------------------------------------------


async def test_block_saturation_threshold() -> None:
    """>50% of emitted rows carrying ``blocked`` => BOT_BLOCK_SATURATION."""
    rows: list[dict[str, Any]] = []
    for i in range(10):
        rows.append({
            "product_id": f"blocked_{i}",
            "product_url": f"https://x.en.made-in-china.com/product/blocked_{i}/",
            "product_name_original": None,
            "scraper_flags": ["blocked"] if i < 6 else [],
            "category_path": [],
        })
    client = MadeInChinaClient()
    res = client.build_envelope_for_rows(rows, public_inputs={"max_products": 100})
    final = _maybe_block_saturation(res)
    assert final["status"] == "failed"
    assert final["error"]["code"] == "BOT_BLOCK_SATURATION"
    assert final["error"]["retriable"] is False
    assert final["error"]["details"]["emitted"] == 10
    assert final["error"]["details"]["blocked"] == 6


async def test_block_saturation_below_threshold() -> None:
    """≤50% blocked => envelope returned as-is."""
    rows: list[dict[str, Any]] = []
    for i in range(10):
        rows.append({
            "product_id": f"p_{i}",
            "product_url": f"https://x.en.made-in-china.com/product/p_{i}/",
            "scraper_flags": ["blocked"] if i < 3 else [],
            "category_path": [],
        })
    client = MadeInChinaClient()
    res = client.build_envelope_for_rows(rows, public_inputs={"max_products": 100})
    final = _maybe_block_saturation(res)
    assert final["status"] == "done"


async def test_structure_degraded_threshold() -> None:
    """>50% of product rows carrying ``jsonld_parse_fallback`` => STRUCTURE_CHANGED."""
    rows: list[dict[str, Any]] = []
    for i in range(10):
        rows.append({
            "product_id": f"p_{i}",
            "product_url": f"https://x.en.made-in-china.com/product/p_{i}/",
            "scraper_flags": ["jsonld_parse_fallback"] if i < 6 else [],
            "category_path": [],
        })
    client = MadeInChinaClient()
    res = client.build_envelope_for_rows(rows, public_inputs={"max_products": 100})
    final = _maybe_structure_degraded(res)
    assert final["status"] == "failed"
    assert final["error"]["code"] == "STRUCTURE_CHANGED"
    assert final["error"]["retriable"] is False
    assert final["error"]["details"]["products"] == 10
    assert final["error"]["details"]["degraded"] == 6


async def test_structure_degraded_below_threshold() -> None:
    """Suppliers do NOT count toward ``structural_degraded`` (only products)."""
    rows: list[dict[str, Any]] = []
    for i in range(10):
        rows.append({
            "product_id": f"p_{i}",
            "product_url": f"https://x.en.made-in-china.com/product/p_{i}/",
            "scraper_flags": ["jsonld_parse_fallback"] if i < 3 else [],
            "category_path": [],
        })
    client = MadeInChinaClient()
    res = client.build_envelope_for_rows(rows, public_inputs={"max_products": 100})
    final = _maybe_structure_degraded(res)
    assert final["status"] == "done"


# ----------------------------------------------------------------------------
# Credentials / dual-mode selection
# ----------------------------------------------------------------------------


async def test_credentials_required_at_trigger(monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing credentials surface as INVALID_INPUTS at trigger time."""
    monkeypatch.delenv("BRIGHTDATA_API_KEY", raising=False)
    monkeypatch.delenv("BRIGHTDATA_DATASET_ID_MADE_IN_CHINA", raising=False)
    monkeypatch.delenv("BRIGHTDATA_COLLECTOR_ID_MADE_IN_CHINA", raising=False)
    res = await trigger({})
    assert res["status"] == "failed"
    assert res["error"]["code"] == "INVALID_INPUTS"


async def test_resolve_mode_v3_wins_over_dca(monkeypatch: pytest.MonkeyPatch) -> None:
    """When both env vars are set, v3 wins."""
    monkeypatch.setenv("BRIGHTDATA_DATASET_ID_MADE_IN_CHINA", "gd_test_v3")
    monkeypatch.setenv("BRIGHTDATA_COLLECTOR_ID_MADE_IN_CHINA", "c_test_dca")
    client = MadeInChinaClient()
    assert client.api_mode == "v3"
    assert client.resource_id == "gd_test_v3"


async def test_resolve_mode_dca_when_only_dca_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("BRIGHTDATA_DATASET_ID_MADE_IN_CHINA", raising=False)
    monkeypatch.setenv("BRIGHTDATA_COLLECTOR_ID_MADE_IN_CHINA", "c_test_dca")
    client = MadeInChinaClient()
    assert client.api_mode == "dca"
    assert client.resource_id == "c_test_dca"


async def test_resolve_mode_v3_when_only_v3_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BRIGHTDATA_DATASET_ID_MADE_IN_CHINA", "gd_test_v3")
    monkeypatch.delenv("BRIGHTDATA_COLLECTOR_ID_MADE_IN_CHINA", raising=False)
    client = MadeInChinaClient()
    assert client.api_mode == "v3"
    assert client.resource_id == "gd_test_v3"


async def test_resolve_mode_none_surfaces_invalid_inputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No env vars populated → ``INVALID_INPUTS`` naming both env vars in msg."""
    monkeypatch.setenv("BRIGHTDATA_API_KEY", "fake_key_for_test")
    monkeypatch.delenv("BRIGHTDATA_DATASET_ID_MADE_IN_CHINA", raising=False)
    monkeypatch.delenv("BRIGHTDATA_COLLECTOR_ID_MADE_IN_CHINA", raising=False)
    res = await trigger({})
    assert res["status"] == "failed"
    assert res["error"]["code"] == "INVALID_INPUTS"
    msg = res["error"]["message"]
    assert "BRIGHTDATA_DATASET_ID_MADE_IN_CHINA" in msg
    assert "BRIGHTDATA_COLLECTOR_ID_MADE_IN_CHINA" in msg


async def test_explicit_api_mode_overrides_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Explicit ``api_mode=`` and ``resource_id=`` beat env vars."""
    monkeypatch.setenv("BRIGHTDATA_DATASET_ID_MADE_IN_CHINA", "gd_env")
    monkeypatch.setenv("BRIGHTDATA_COLLECTOR_ID_MADE_IN_CHINA", "c_env")
    client = MadeInChinaClient(api_mode="dca", resource_id="c_override")
    assert client.api_mode == "dca"
    assert client.resource_id == "c_override"


async def test_dataset_id_alias_silent_backwards_compat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``dataset_id=`` kwarg aliases ``resource_id=`` silently (no warning)."""
    import warnings

    monkeypatch.delenv("BRIGHTDATA_DATASET_ID_MADE_IN_CHINA", raising=False)
    monkeypatch.delenv("BRIGHTDATA_COLLECTOR_ID_MADE_IN_CHINA", raising=False)
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        client = MadeInChinaClient(dataset_id="gd_from_alias")
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
    assert names == {"made_in_china_trigger", "made_in_china_get_result"}
    for tool in TOOL_SCHEMA:
        assert "description" in tool
        assert "input_schema" in tool
        assert tool["input_schema"]["type"] == "object"
        assert tool["input_schema"].get("additionalProperties") is False


async def test_per_scraper_error_codes_extendcore() -> None:
    """The made-in-china error code extension does not redefine base codes."""
    for code in MADE_IN_CHINA_ERROR_CODES:
        assert code not in NORMALIZED_CODES, (
            f"Per-scraper code {code!r} collides with base catalog."
        )


async def test_pydantic_row_models_smoke(snapshot_rows: list[dict]) -> None:
    """Every fixture row round-trips through its entity model cleanly."""
    for raw in snapshot_rows:
        if raw.get("supplier_id") and not raw.get("product_id"):
            # Supplier row — apply aliases the middleware would apply.
            row = dict(raw)
            # No aliases to apply on the current fixture (already canonical).
            assert SupplierRow(**row)
        else:
            # Product row.
            row = dict(raw)
            # Apply the two legacy aliases present in row 3 of the fixture.
            for src, dst in [
                ("url", "product_url"),
                ("name_original", "product_name_original"),
                ("name_clean", "product_name_clean"),
            ]:
                if src in row:
                    row[dst] = row.pop(src)
            assert ProductRow(**row)
