"""Unit + fixture tests for the indiamart middleware.

Coverage map:
    - test_trigger_happy_path               — @brightdata live (skipped w/o env)
    - test_get_result_done_from_fixture     — parses canonical fixture
    - test_envelope_shape                    — exact top-level keys
    - test_multi_entity_data_split           — product/supplier counts
    - test_product_keys_complete             — spec §2+§4+§5 keys present
    - test_supplier_keys_complete            — spec §2+§6 keys present
    - test_fixture_obligatorio_spec11        — product_id 22408594448 values
    - test_product_aliases_applied            — product_url → url
    - test_supplier_aliases_applied           — supplier_url/name/city → short forms
    - test_country_iso2_coerced               — "India" → "IN"
    - test_country_already_iso2               — "IN" untouched
    - test_max_products_cap                   — emitted product ≤ max_products
    - test_max_suppliers_cap                  — emitted supplier ≤ max_suppliers
    - test_include_suppliers_false            — drops supplier rows
    - test_input_translation_*                — public → seed URL mapping
    - test_invalid_inputs_*                   — INVALID_INPUTS paths
    - test_resolve_mode_*                     — dual-mode selection
    - test_region_blocked_threshold           — REGION_BLOCKED code
    - test_structure_changed_threshold        — STRUCTURE_CHANGED code
    - test_classify_entity_*                  — entity discriminator heuristics
    - test_tool_schema_shape                  — TOOL_SCHEMA contract
"""

from __future__ import annotations

import os
from typing import Any

import pytest

from gli_scrapers.core.envelope import Envelope
from gli_scrapers.core.errors import NORMALIZED_CODES
from gli_scrapers.indiamart import (
    TOOL_SCHEMA,
    IndiamartClient,
    IndiamartInputs,
    ProductRow,
    SupplierRow,
    trigger,
)
from gli_scrapers.indiamart.client import (
    INDIAMART_ERROR_CODES,
    _classify_entity,
    _coerce_product,
    _coerce_supplier,
    _maybe_region_blocked,
    _maybe_structure_changed,
    _normalize_supplier_country,
)
from gli_scrapers.indiamart.config import (
    DEFAULT_INDUSTRY_HUBS,
    DEFAULT_MCAT_SLUGS,
    industry_hub_url,
    mcat_listing_url,
)
from gli_scrapers.indiamart.models import (
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
        ("v3", "BRIGHTDATA_DATASET_ID_INDIAMART"),
        ("dca", "BRIGHTDATA_COLLECTOR_ID_INDIAMART"),
    ],
)
async def test_trigger_happy_path(api_mode: str, resource_env: str) -> None:
    """Default inputs against the real BrightData API → returns a job_id.

    Parametrized over both transports. Each case is skipped individually
    when its env var is missing so a partial config still exercises the
    runnable mode.
    """
    resource_id = os.getenv(resource_env)
    if not resource_id:
        pytest.skip(f"{resource_env} not set — skipping {api_mode} live case")

    client = IndiamartClient(api_mode=api_mode, resource_id=resource_id)
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
    client = IndiamartClient()
    res = client.build_envelope_for_rows(
        snapshot_rows,
        public_inputs={"max_products": 100, "max_suppliers": 100},
    )
    assert res["status"] == "done"
    env = res["data"]
    assert env["source"] == "indiamart"
    assert isinstance(env["data"], list)
    assert len(env["data"]) == len(snapshot_rows)
    Envelope(**env)


async def test_envelope_shape(snapshot_rows: list[dict]) -> None:
    """Top-level envelope keys are EXACTLY the contracted set (no extras)."""
    client = IndiamartClient()
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
        "structure_failed",
        "errors",
        "started_at",
        "ended_at",
    ):
        assert key in env["meta"], f"meta missing {key!r}"


async def test_multi_entity_data_split(snapshot_rows: list[dict]) -> None:
    """Each row classified under the correct entity discriminator."""
    client = IndiamartClient()
    res = client.build_envelope_for_rows(snapshot_rows, public_inputs={})
    counts = res["data"]["meta"]["emitted_by_entity"]
    # Fixture layout: 3 products + 2 suppliers.
    assert counts["product"] == 3
    assert counts["supplier"] == 2
    entities = [row["entity"] for row in res["data"]["data"]]
    assert entities.count("product") == 3
    assert entities.count("supplier") == 2


async def test_product_keys_complete(snapshot_rows: list[dict]) -> None:
    """Every emitted product row has all §2/§4/§5 keys (null/[] allowed)."""
    client = IndiamartClient()
    res = client.build_envelope_for_rows(snapshot_rows, public_inputs={})
    products = [
        row for row in res["data"]["data"] if row["entity"] == "product"
    ]
    assert products, "fixture should contain at least one product"
    for row in products:
        for key in PRODUCT_FIELDS:
            assert key in row, (
                f"missing key {key!r} in product row "
                f"{row.get('product_id')}"
            )
        for key in PRODUCT_LIST_FIELDS:
            assert isinstance(row[key], list), (
                f"key {key!r} in product row {row.get('product_id')} "
                f"must be a list, got {type(row[key]).__name__}"
            )


async def test_supplier_keys_complete(snapshot_rows: list[dict]) -> None:
    """Every supplier row has all §2/§6 keys."""
    client = IndiamartClient()
    res = client.build_envelope_for_rows(snapshot_rows, public_inputs={})
    suppliers = [
        row for row in res["data"]["data"] if row["entity"] == "supplier"
    ]
    assert suppliers
    for row in suppliers:
        for key in SUPPLIER_FIELDS:
            assert key in row, f"missing key {key!r} in supplier row"
        for key in SUPPLIER_LIST_FIELDS:
            assert isinstance(row[key], list), (
                f"key {key!r} in supplier row must be a list"
            )


async def test_fixture_obligatorio_spec11(snapshot_rows: list[dict]) -> None:
    """Spec §11: product_id 22408594448 must emit specific field values.

    Regression fixture: Caustic Soda Flakes, Vats International, New Delhi.
    """
    client = IndiamartClient()
    res = client.build_envelope_for_rows(snapshot_rows, public_inputs={})
    prod = next(
        row for row in res["data"]["data"]
        if row.get("product_id") == "22408594448"
    )
    assert prod["entity"] == "product"
    assert prod["product_name_original"] == "Caustic Soda Flakes"
    assert prod["price_currency"] == "INR"
    assert prod["price_value_raw"] == "50"
    assert prod["price_unit"] == "kg"
    assert prod["moq_quantity"] == 20000
    assert prod["moq_unit"] == "kg"
    assert prod["supplier_id"] == "vatsinternational"
    assert prod["supplier_name"] == "Vats International"
    assert prod["supplier_city"] == "New Delhi"
    assert prod["supplier_state"] is None
    assert prod["supplier_country"] == "IN"
    assert "supplier_state_from_home_needed" in prod["scraper_flags"]
    assert prod["type"] == "chemical"
    assert prod["category_mic"] == "Caustic Soda"
    assert prod["category_path"] == [
        "Industrial Chemicals & Supplies",
        "Chemical Compound",
        "Caustic Soda",
    ]
    assert prod["industry_slug"] == "chem"


async def test_product_aliases_applied(snapshot_rows: list[dict]) -> None:
    """``product_url`` renamed to ``url`` on the wire."""
    client = IndiamartClient()
    res = client.build_envelope_for_rows(snapshot_rows, public_inputs={})
    prod = next(
        row for row in res["data"]["data"]
        if row.get("product_id") == "22408594448"
    )
    assert prod["url"] == (
        "https://www.indiamart.com/proddetail/"
        "caustic-soda-flakes-22408594448.html"
    )
    # Product rows must NOT rename supplier_* to the short forms; those
    # are foreign-key copies and distinct from the supplier entity's own
    # identity fields.
    assert prod["supplier_name"] == "Vats International"
    assert prod["supplier_city"] == "New Delhi"


async def test_supplier_aliases_applied(snapshot_rows: list[dict]) -> None:
    """Supplier rows rename ``supplier_*`` to §2 short forms."""
    client = IndiamartClient()
    res = client.build_envelope_for_rows(snapshot_rows, public_inputs={})
    sup = next(
        row for row in res["data"]["data"]
        if row["entity"] == "supplier"
        and row.get("supplier_id") == "vats-international"
    )
    assert sup["url"] == "https://www.indiamart.com/vats-international/"
    assert sup["name"] == "Vats International"
    assert sup["city"] == "New Delhi"
    assert sup["state"] == "Delhi"
    assert sup["verified"] is True
    assert sup["trustseal"] is True


async def test_country_iso2_coerced(snapshot_rows: list[dict]) -> None:
    """``supplier_country='India'`` coerced to ``'IN'`` on supplier row."""
    client = IndiamartClient()
    res = client.build_envelope_for_rows(snapshot_rows, public_inputs={})
    sup = next(
        row for row in res["data"]["data"]
        if row["entity"] == "supplier"
        and row.get("supplier_id") == "vats-international"
    )
    assert sup["country"] == "IN"
    # Coercion is silent; no flag added when mapping is known.
    assert "country_not_iso2" not in sup.get("scraper_flags", [])


async def test_country_already_iso2(snapshot_rows: list[dict]) -> None:
    """``supplier_country='IN'`` passes through untouched."""
    client = IndiamartClient()
    res = client.build_envelope_for_rows(snapshot_rows, public_inputs={})
    sup = next(
        row for row in res["data"]["data"]
        if row["entity"] == "supplier"
        and row.get("supplier_id") == "rohan-chemicals-mumbai"
    )
    assert sup["country"] == "IN"


async def test_country_unknown_string_flagged() -> None:
    """Unknown free-text country keeps original value + adds flag."""
    row = {
        "entity": "supplier",
        "supplier_id": "x",
        "country": "Ruritania",
        "scraper_flags": [],
    }
    normalized = _normalize_supplier_country(row)
    assert normalized["country"] == "Ruritania"
    assert "country_not_iso2" in normalized["scraper_flags"]


async def test_max_products_cap(snapshot_rows: list[dict]) -> None:
    """``max_products`` caps emitted product rows (suppliers unaffected)."""
    client = IndiamartClient()
    res = client.build_envelope_for_rows(
        snapshot_rows,
        public_inputs={"max_products": 2, "max_suppliers": 100},
    )
    counts = res["data"]["meta"]["emitted_by_entity"]
    assert counts["product"] == 2
    assert counts["supplier"] == 2
    assert res["data"]["meta"]["skipped_by_reason"].get("max_products_cap") == 1


async def test_max_suppliers_cap(snapshot_rows: list[dict]) -> None:
    """``max_suppliers`` caps emitted supplier rows (products unaffected)."""
    client = IndiamartClient()
    res = client.build_envelope_for_rows(
        snapshot_rows,
        public_inputs={"max_products": 100, "max_suppliers": 1},
    )
    counts = res["data"]["meta"]["emitted_by_entity"]
    assert counts["supplier"] == 1
    assert counts["product"] == 3
    assert res["data"]["meta"]["skipped_by_reason"].get("max_suppliers_cap") == 1


async def test_include_suppliers_false(snapshot_rows: list[dict]) -> None:
    """``include_suppliers=False`` drops every supplier row."""
    client = IndiamartClient()
    res = client.build_envelope_for_rows(
        snapshot_rows,
        public_inputs={"include_suppliers": False},
    )
    counts = res["data"]["meta"]["emitted_by_entity"]
    assert counts["supplier"] == 0
    assert counts["product"] == 3
    assert (
        res["data"]["meta"]["skipped_by_reason"].get("suppliers_disabled") == 2
    )


# ----------------------------------------------------------------------------
# Invalid-inputs paths (no BrightData call)
# ----------------------------------------------------------------------------


async def test_invalid_inputs_max_products_too_high() -> None:
    """``max_products=99999`` (above 1500 cap) => INVALID_INPUTS."""
    res = await trigger({"max_products": 99999})
    assert res["status"] == "failed"
    assert res["error"]["code"] == "INVALID_INPUTS"
    assert res["error"]["retriable"] is False


async def test_invalid_inputs_max_suppliers_negative() -> None:
    """``max_suppliers=-1`` (below 0) => INVALID_INPUTS."""
    res = await trigger({"max_suppliers": -1})
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


async def test_invalid_inputs_empty_seeds(monkeypatch: pytest.MonkeyPatch) -> None:
    """Empty mcat_slugs + include_industry_hubs=False => INVALID_INPUTS."""
    # Credentials present so we bypass the missing-creds guard and exercise
    # the empty-seeds branch.
    monkeypatch.setenv("BRIGHTDATA_API_KEY", "fake")
    monkeypatch.setenv("BRIGHTDATA_DATASET_ID_INDIAMART", "gd_fake")
    res = await trigger({
        "mcat_slugs": [],
        "include_industry_hubs": False,
    })
    assert res["status"] == "failed"
    assert res["error"]["code"] == "INVALID_INPUTS"
    assert "seed" in res["error"]["message"].lower()


# ----------------------------------------------------------------------------
# Translation: public inputs → JS scraper inputs (seed URLs)
# ----------------------------------------------------------------------------


async def test_input_translation_default() -> None:
    """Default inputs → 12 MCAT seeds + 2 industry hub seeds.

    Contract post-refactor 2026-04-23 (híbrido): seeds llevan
    ``{category_slug, kind}`` en lugar de ``{url}``. El scraper JS arma
    la URL con su plantilla interna.
    """
    client = IndiamartClient()
    seeds = client._build_brightdata_inputs(IndiamartInputs())
    assert len(seeds) == len(DEFAULT_MCAT_SLUGS) + len(DEFAULT_INDUSTRY_HUBS)
    mcat_seeds = [s for s in seeds if s["kind"] == "mcat"]
    hub_seeds = [s for s in seeds if s["kind"] == "hub"]
    # Every default MCAT present.
    mcat_urls = [s["url"] for s in mcat_seeds]
    for slug in DEFAULT_MCAT_SLUGS:
        assert any(slug in u for u in mcat_urls)
    assert all(s["category_slug"] == "" for s in mcat_seeds)
    # Every default industry hub present.
    hub_urls = [s["url"] for s in hub_seeds]
    for hub in DEFAULT_INDUSTRY_HUBS:
        assert any(hub in u for u in hub_urls)
    assert all(s["category_slug"] == "" for s in hub_seeds)


async def test_input_translation_explicit_mcats() -> None:
    """Explicit ``mcat_slugs`` replaces the default list."""
    client = IndiamartClient()
    seeds = client._build_brightdata_inputs(
        IndiamartInputs(
            mcat_slugs=["caustic-soda"],
            include_industry_hubs=False,
        )
    )
    assert len(seeds) == 1
    assert seeds[0]["kind"] == "mcat"
    assert seeds[0]["category_slug"] == ""
    assert "caustic-soda" in seeds[0]["url"]


async def test_input_translation_explicit_hubs() -> None:
    """Explicit ``industry_hubs`` replaces the default list."""
    client = IndiamartClient()
    seeds = client._build_brightdata_inputs(
        IndiamartInputs(
            mcat_slugs=["caustic-soda"],
            industry_hubs=["chem"],
            include_industry_hubs=True,
        )
    )
    assert any("caustic-soda" in s["url"] and s["kind"] == "mcat" for s in seeds)
    assert any("chem" in s["url"] and s["kind"] == "hub" for s in seeds)
    assert len(seeds) == 2


async def test_input_translation_hubs_disabled() -> None:
    """``include_industry_hubs=False`` drops hub seeds even if list is set."""
    client = IndiamartClient()
    seeds = client._build_brightdata_inputs(
        IndiamartInputs(
            mcat_slugs=["caustic-soda"],
            industry_hubs=["chem", "packaging"],
            include_industry_hubs=False,
        )
    )
    assert all(s["kind"] != "hub" for s in seeds)
    assert len(seeds) == 1
    assert seeds[0]["kind"] == "mcat"
    assert seeds[0]["category_slug"] == ""
    assert "caustic-soda" in seeds[0]["url"]


async def test_input_translation_max_products_not_in_seed() -> None:
    """``max_products`` is post-download; never in the trigger seed."""
    client = IndiamartClient()
    seeds = client._build_brightdata_inputs(
        IndiamartInputs(mcat_slugs=["caustic-soda"], max_products=5)
    )
    for seed in seeds:
        assert "max_products" not in seed


# ----------------------------------------------------------------------------
# Row coercion & classification
# ----------------------------------------------------------------------------


async def test_coerce_product_fills_missing_keys() -> None:
    """A sparse product row still emits every §2/§4/§5 key."""
    raw = {
        "product_id": "minimal",
        "product_url": "https://www.indiamart.com/proddetail/x-minimal.html",
    }
    out = _coerce_product(raw)
    for key in PRODUCT_FIELDS:
        assert key in out
    assert out["entity"] == "product"
    assert out["url"] == "https://www.indiamart.com/proddetail/x-minimal.html"
    assert out["category_path"] == []
    assert out["scraper_flags"] == []
    assert out["supplier_name"] is None


async def test_coerce_supplier_fills_missing_keys() -> None:
    raw = {
        "supplier_id": "test",
        "supplier_name": "Test Supplier",
        "business_type": "Manufacturer",
    }
    out = _coerce_supplier(raw)
    for key in SUPPLIER_FIELDS:
        assert key in out
    assert out["entity"] == "supplier"
    assert out["name"] == "Test Supplier"
    assert out["verified"] is None
    assert out["certifications"] == []


async def test_classify_entity_explicit() -> None:
    """Explicit ``entity`` key wins over heuristic."""
    assert _classify_entity({"entity": "supplier", "product_id": "x"}) == (
        "supplier"
    )
    assert _classify_entity({"_entity": "product"}) == "product"


async def test_classify_entity_type_field_not_entity() -> None:
    """``type='chemical'`` (product field) must NOT be read as discriminator."""
    row = {"type": "chemical", "product_id": "123"}
    # Should classify as product via product_id, not as unknown.
    assert _classify_entity(row) == "product"


async def test_classify_entity_type_field_as_entity() -> None:
    """``type='supplier'`` IS accepted as discriminator (legal value)."""
    row = {"type": "supplier", "supplier_id": "x"}
    assert _classify_entity(row) == "supplier"


async def test_classify_entity_heuristic_product_by_price() -> None:
    """A row with ``price_currency`` is a product (supplier never has price)."""
    assert _classify_entity({"price_currency": "INR"}) == "product"


async def test_classify_entity_heuristic_supplier() -> None:
    """supplier_id + business_type => supplier."""
    assert (
        _classify_entity(
            {"supplier_id": "x", "business_type": "Manufacturer"}
        )
        == "supplier"
    )


async def test_classify_entity_orphan_supplier_id_unknown() -> None:
    """Bare ``supplier_id`` without a supplier-specific field => None.

    This guards against accidentally classifying a product row that omits
    product_id/price but carries supplier_id as a foreign key.
    """
    assert _classify_entity({"supplier_id": "x"}) is None


async def test_classify_entity_unknown() -> None:
    """Row without any signal => None."""
    assert _classify_entity({"foo": "bar"}) is None


async def test_unknown_entity_counted(snapshot_rows: list[dict]) -> None:
    """An un-classifiable row lands in ``skipped_by_reason['unknown_entity']``."""
    rows = snapshot_rows + [{"foo": "bar"}]
    client = IndiamartClient()
    res = client.build_envelope_for_rows(rows, public_inputs={})
    assert res["data"]["meta"]["skipped_by_reason"].get("unknown_entity") == 1


async def test_non_dict_row_counted() -> None:
    """Non-dict row => counted under ``errors`` and ``non_dict_row``."""
    rows: list[Any] = [
        {"product_id": "1", "product_url": "u"},
        "not-a-dict",
        42,
    ]
    client = IndiamartClient()
    res = client.build_envelope_for_rows(rows, public_inputs={})
    meta = res["data"]["meta"]
    assert meta["errors"] == 2
    assert meta["skipped_by_reason"].get("non_dict_row") == 2


# ----------------------------------------------------------------------------
# REGION_BLOCKED and STRUCTURE_CHANGED gates
# ----------------------------------------------------------------------------


async def test_region_blocked_threshold() -> None:
    """>50% of product rows carrying 'blocked' => REGION_BLOCKED."""
    rows: list[dict[str, Any]] = []
    for i in range(10):
        rows.append(
            {
                "product_id": f"p_{i}",
                "product_url": f"https://www.indiamart.com/proddetail/x-{i}.html",
                "scraper_flags": ["blocked"] if i < 6 else [],
                "category_path": [],
            }
        )
    client = IndiamartClient()
    res = client.build_envelope_for_rows(
        rows, public_inputs={"max_products": 100}
    )
    final = _maybe_region_blocked(res)
    assert final["status"] == "failed"
    assert final["error"]["code"] == "REGION_BLOCKED"
    assert final["error"]["retriable"] is False
    assert final["error"]["details"]["products"] == 10
    assert final["error"]["details"]["blocked"] == 6


async def test_region_blocked_below_threshold() -> None:
    """≤50% blocked => envelope returned as-is."""
    rows: list[dict[str, Any]] = []
    for i in range(10):
        rows.append(
            {
                "product_id": f"p_{i}",
                "product_url": f"https://www.indiamart.com/proddetail/x-{i}.html",
                "scraper_flags": ["blocked"] if i < 3 else [],
                "category_path": [],
            }
        )
    client = IndiamartClient()
    res = client.build_envelope_for_rows(
        rows, public_inputs={"max_products": 100}
    )
    final = _maybe_region_blocked(res)
    assert final["status"] == "done"


async def test_structure_changed_threshold() -> None:
    """>50% of product rows with parse-failure flags => STRUCTURE_CHANGED."""
    rows: list[dict[str, Any]] = []
    for i in range(10):
        rows.append(
            {
                "product_id": f"p_{i}",
                "product_url": f"https://www.indiamart.com/proddetail/x-{i}.html",
                "scraper_flags": (
                    ["jsonld_parse_fallback"] if i < 6 else []
                ),
                "category_path": [],
            }
        )
    client = IndiamartClient()
    res = client.build_envelope_for_rows(
        rows, public_inputs={"max_products": 100}
    )
    final = _maybe_structure_changed(res)
    assert final["status"] == "failed"
    assert final["error"]["code"] == "STRUCTURE_CHANGED"
    assert final["error"]["retriable"] is False
    assert final["error"]["details"]["products"] == 10
    assert final["error"]["details"]["structure_failed"] == 6


async def test_structure_changed_missing_product_id_counts() -> None:
    """A product row without product_id counts as structure_failed."""
    rows: list[dict[str, Any]] = []
    for i in range(10):
        rows.append(
            {
                # Missing product_id on 6 of 10 — classifier still picks
                # them up by product_url.
                "product_id": None if i < 6 else f"p_{i}",
                "product_url": (
                    f"https://www.indiamart.com/proddetail/x-{i}.html"
                ),
                "scraper_flags": [],
                "category_path": [],
            }
        )
    client = IndiamartClient()
    res = client.build_envelope_for_rows(
        rows, public_inputs={"max_products": 100}
    )
    final = _maybe_structure_changed(res)
    assert final["status"] == "failed"
    assert final["error"]["code"] == "STRUCTURE_CHANGED"


# ----------------------------------------------------------------------------
# Credentials / dual-mode selection
# ----------------------------------------------------------------------------


async def test_credentials_required_at_trigger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing credentials surface as INVALID_INPUTS at trigger time."""
    monkeypatch.delenv("BRIGHTDATA_API_KEY", raising=False)
    monkeypatch.delenv("BRIGHTDATA_DATASET_ID_INDIAMART", raising=False)
    monkeypatch.delenv("BRIGHTDATA_COLLECTOR_ID_INDIAMART", raising=False)
    res = await trigger({})
    assert res["status"] == "failed"
    assert res["error"]["code"] == "INVALID_INPUTS"


async def test_resolve_mode_v3_wins_over_dca(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When both env vars are set, v3 wins."""
    monkeypatch.setenv("BRIGHTDATA_DATASET_ID_INDIAMART", "gd_test_v3")
    monkeypatch.setenv("BRIGHTDATA_COLLECTOR_ID_INDIAMART", "c_test_dca")
    client = IndiamartClient()
    assert client.api_mode == "v3"
    assert client.resource_id == "gd_test_v3"


async def test_resolve_mode_dca_when_only_dca_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("BRIGHTDATA_DATASET_ID_INDIAMART", raising=False)
    monkeypatch.setenv("BRIGHTDATA_COLLECTOR_ID_INDIAMART", "c_test_dca")
    client = IndiamartClient()
    assert client.api_mode == "dca"
    assert client.resource_id == "c_test_dca"


async def test_resolve_mode_v3_when_only_v3_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BRIGHTDATA_DATASET_ID_INDIAMART", "gd_test_v3")
    monkeypatch.delenv("BRIGHTDATA_COLLECTOR_ID_INDIAMART", raising=False)
    client = IndiamartClient()
    assert client.api_mode == "v3"
    assert client.resource_id == "gd_test_v3"


async def test_resolve_mode_none_surfaces_invalid_inputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No env vars populated → ``INVALID_INPUTS`` naming both env vars."""
    monkeypatch.setenv("BRIGHTDATA_API_KEY", "fake_key_for_test")
    monkeypatch.delenv("BRIGHTDATA_DATASET_ID_INDIAMART", raising=False)
    monkeypatch.delenv("BRIGHTDATA_COLLECTOR_ID_INDIAMART", raising=False)
    res = await trigger({})
    assert res["status"] == "failed"
    assert res["error"]["code"] == "INVALID_INPUTS"
    msg = res["error"]["message"]
    assert "BRIGHTDATA_DATASET_ID_INDIAMART" in msg
    assert "BRIGHTDATA_COLLECTOR_ID_INDIAMART" in msg


async def test_explicit_api_mode_overrides_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Explicit ``api_mode=`` and ``resource_id=`` beat env vars."""
    monkeypatch.setenv("BRIGHTDATA_DATASET_ID_INDIAMART", "gd_env")
    monkeypatch.setenv("BRIGHTDATA_COLLECTOR_ID_INDIAMART", "c_env")
    client = IndiamartClient(api_mode="dca", resource_id="c_override")
    assert client.api_mode == "dca"
    assert client.resource_id == "c_override"


async def test_dataset_id_alias_silent_backwards_compat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``dataset_id=`` kwarg aliases ``resource_id=`` silently."""
    import warnings

    monkeypatch.delenv("BRIGHTDATA_DATASET_ID_INDIAMART", raising=False)
    monkeypatch.delenv("BRIGHTDATA_COLLECTOR_ID_INDIAMART", raising=False)
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        client = IndiamartClient(dataset_id="gd_from_alias")
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
    assert names == {"indiamart_trigger", "indiamart_get_result"}
    for tool in TOOL_SCHEMA:
        assert "description" in tool
        assert "input_schema" in tool
        assert tool["input_schema"]["type"] == "object"
        assert tool["input_schema"].get("additionalProperties") is False


async def test_per_scraper_error_codes_extendcore() -> None:
    """The indiamart error code extension does not redefine base codes."""
    for code in INDIAMART_ERROR_CODES:
        assert code not in NORMALIZED_CODES, (
            f"Per-scraper code {code!r} collides with base catalog."
        )


async def test_pydantic_row_models_smoke(snapshot_rows: list[dict]) -> None:
    """Every fixture row round-trips through its entity model cleanly.

    Applies the same aliases the middleware applies before validation so
    we exercise the pydantic models directly.
    """
    for raw in snapshot_rows:
        # Classify.
        if "supplier_url" in raw or (
            "business_type" in raw and "supplier_id" in raw
        ):
            # Supplier — apply supplier aliases.
            row = dict(raw)
            for src, dst in [
                ("supplier_url", "url"),
                ("supplier_name", "name"),
                ("supplier_city", "city"),
                ("supplier_state", "state"),
                ("supplier_country", "country"),
                ("verified_exporter", "verified"),
            ]:
                if src in row:
                    row[dst] = row.pop(src)
            # Coerce free-text country to pass pydantic (not enforced yet).
            assert SupplierRow(**row)
        else:
            # Product — apply product aliases.
            row = dict(raw)
            if "product_url" in row:
                row["url"] = row.pop("product_url")
            assert ProductRow(**row)
