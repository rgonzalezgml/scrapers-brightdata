"""Unit + fixture tests for the alibaba middleware.

Coverage map:
    - test_trigger_happy_path               — @brightdata live (skipped w/o env)
    - test_get_result_done_from_fixture     — parses canonical fixture
    - test_envelope_shape                    — exact top-level keys, no extras
    - test_product_keys_complete             — spec §2+§5 keys present on every row
    - test_aliases_applied                    — cleaned_product_name → product_name_clean
    - test_country_iso2_passthrough           — already-ISO-2 value preserved
    - test_country_iso2_mapped                — "United States" → "US"
    - test_country_iso2_unmapped_flag        — "Narnia" → null + country_unmapped
    - test_country_iso2_none_no_flag         — None input does NOT set flag
    - test_site_injected                      — every row carries site="alibaba"
    - test_entity_injected                    — every row carries entity="product"
    - test_max_products_cap                   — emitted product ≤ max_products
    - test_input_translation_default          — defaults → 5 canonical seeds
    - test_input_translation_custom_terms     — custom terms → N seeds
    - test_input_translation_supplier_country — filter forwarded only when asked
    - test_invalid_inputs_*                   — INVALID_INPUTS paths
    - test_resolve_mode_*                     — dual-mode selection
    - test_block_saturation_threshold         — BLOCK_SATURATION code
    - test_price_missing_saturation_threshold — PRICE_MISSING_SATURATION code
    - test_tool_schema_shape                  — 2 tools, correct names
    - test_per_scraper_error_codes_extendcore — no base-code collision
"""

from __future__ import annotations

import os
from typing import Any

import pytest

from middlewares.core.envelope import Envelope
from middlewares.core.errors import NORMALIZED_CODES
from middlewares.alibaba import (
    TOOL_SCHEMA,
    AlibabaClient,
    AlibabaInputs,
    ProductRow,
    trigger,
)
from middlewares.alibaba.client import (
    ALIBABA_ERROR_CODES,
    _classify_entity,
    _coerce_product,
    _maybe_block_saturation,
    _maybe_price_missing_saturation,
)
from middlewares.alibaba.config import (
    COUNTRY_TO_ISO2,
    DEFAULT_SEARCH_TERMS,
    country_to_iso2,
    search_url,
)
from middlewares.alibaba.models import (
    PRODUCT_FIELDS,
    PRODUCT_LIST_FIELDS,
)

pytestmark = pytest.mark.asyncio


# ----------------------------------------------------------------------------
# Live BrightData (skipped unless env vars set, see conftest.py)
# ----------------------------------------------------------------------------


@pytest.mark.brightdata
@pytest.mark.parametrize(
    "api_mode,resource_env",
    [
        ("v3", "BRIGHTDATA_DATASET_ID_ALIBABA"),
        ("dca", "BRIGHTDATA_COLLECTOR_ID_ALIBABA"),
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

    client = AlibabaClient(api_mode=api_mode, resource_id=resource_id)
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
    client = AlibabaClient()
    res = client.build_envelope_for_rows(
        snapshot_rows,
        public_inputs={"max_products": 100},
    )
    assert res["status"] == "done"
    env = res["data"]
    assert env["source"] == "alibaba"
    assert isinstance(env["data"], list)
    assert len(env["data"]) == len(snapshot_rows)
    # Envelope validates cleanly.
    Envelope(**env)


async def test_envelope_shape(snapshot_rows: list[dict]) -> None:
    """Top-level envelope keys are EXACTLY the contracted set (no extras)."""
    client = AlibabaClient()
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
        "missing_price",
        "unmapped_country",
        "errors",
        "started_at",
        "ended_at",
    ):
        assert key in env["meta"], f"meta missing {key!r}"


async def test_product_keys_complete(snapshot_rows: list[dict]) -> None:
    """Every emitted product row has all §2/§5 keys (null/[] allowed)."""
    client = AlibabaClient()
    res = client.build_envelope_for_rows(snapshot_rows, public_inputs={})
    products = res["data"]["data"]
    assert products, "fixture should contain product rows"
    for row in products:
        assert row["entity"] == "product"
        for key in PRODUCT_FIELDS:
            assert key in row, (
                f"missing key {key!r} in product row {row.get('product_url')}"
            )
        for key in PRODUCT_LIST_FIELDS:
            assert isinstance(row[key], list), (
                f"key {key!r} must be a list in row {row.get('product_url')}, "
                f"got {type(row[key]).__name__}"
            )


async def test_aliases_applied(snapshot_rows: list[dict]) -> None:
    """Vendor-native keys renamed to spec §2 short forms on the wire."""
    client = AlibabaClient()
    res = client.build_envelope_for_rows(snapshot_rows, public_inputs={})
    data = res["data"]["data"]
    # Pick the Glycerin row (has vendor-native ``cleaned_product_name`` key).
    glycerin = next(
        row for row in data
        if row.get("product_url", "").endswith("Glycerin-99-5_123456.html")
    )
    # Alias target present, populated from scraper's cleaned_product_name.
    assert glycerin["product_name_clean"] == "Glycerin Industrial Grade Liquid"
    # `minimum_order_quantity` → `moq_quantity`.
    assert glycerin["moq_quantity"] == 500
    # Spec §2 keys straight through.
    assert glycerin["price_min_usd"] == 1.20
    assert glycerin["price_max_usd"] == 2.50
    assert glycerin["price_unit"] == "kg"


async def test_site_injected(snapshot_rows: list[dict]) -> None:
    """Every row carries site='alibaba' (spec §1 'Campo site fijo')."""
    client = AlibabaClient()
    res = client.build_envelope_for_rows(snapshot_rows, public_inputs={})
    for row in res["data"]["data"]:
        assert row["site"] == "alibaba"


async def test_entity_injected(snapshot_rows: list[dict]) -> None:
    """Every row carries entity='product' (single-entity scraper today)."""
    client = AlibabaClient()
    res = client.build_envelope_for_rows(snapshot_rows, public_inputs={})
    for row in res["data"]["data"]:
        assert row["entity"] == "product"


# ----------------------------------------------------------------------------
# Country → ISO-2 normalization
# ----------------------------------------------------------------------------


async def test_country_iso2_passthrough() -> None:
    """Already-ISO-2 value is preserved verbatim."""
    iso, unmapped = country_to_iso2("CN")
    assert iso == "CN" and unmapped is False


async def test_country_iso2_mapped() -> None:
    """Free-text names get mapped to ISO-2."""
    for text, expected in [
        ("China", "CN"),
        ("United States", "US"),
        ("united states", "US"),
        ("  Germany  ", "DE"),
        ("USA", "US"),
    ]:
        iso, unmapped = country_to_iso2(text)
        assert iso == expected, f"{text!r} → {iso!r}, expected {expected!r}"
        assert unmapped is False


async def test_country_iso2_unmapped() -> None:
    """Unknown country label → (null, True)."""
    iso, unmapped = country_to_iso2("Narnia")
    assert iso is None and unmapped is True


async def test_country_iso2_none_no_flag() -> None:
    """None / empty → (null, False) (missing data is NOT an unmapped flag)."""
    for val in [None, "", "   "]:
        iso, unmapped = country_to_iso2(val)
        assert iso is None
        assert unmapped is False, f"{val!r} should not be flagged unmapped"


async def test_country_iso2_table_values_are_iso2() -> None:
    """Guard against typos in COUNTRY_TO_ISO2: every value is a 2-letter upper string."""
    for key, val in COUNTRY_TO_ISO2.items():
        assert isinstance(val, str) and len(val) == 2 and val.isupper(), (
            f"COUNTRY_TO_ISO2[{key!r}] = {val!r} is not a 2-letter ISO-2 code"
        )


async def test_country_unmapped_flag_added_to_row(snapshot_rows: list[dict]) -> None:
    """A fixture row with supplier_country='Narnia' lands with country_unmapped."""
    client = AlibabaClient()
    res = client.build_envelope_for_rows(snapshot_rows, public_inputs={})
    narnia = next(
        row for row in res["data"]["data"]
        if row.get("product_url", "").endswith("Mysterious-Potion_999009.html")
    )
    assert narnia["supplier_country"] is None
    assert "country_unmapped" in narnia["scraper_flags"]


async def test_country_mapped_row_no_flag(snapshot_rows: list[dict]) -> None:
    """A fixture row with supplier_country='United States' lands as 'US' and no flag."""
    client = AlibabaClient()
    res = client.build_envelope_for_rows(snapshot_rows, public_inputs={})
    hdpe = next(
        row for row in res["data"]["data"]
        if row.get("product_url", "").endswith("HDPE-Drum-200L_777001.html")
    )
    assert hdpe["supplier_country"] == "US"
    assert "country_unmapped" not in hdpe["scraper_flags"]


async def test_meta_unmapped_country_counter(snapshot_rows: list[dict]) -> None:
    """Exactly one row in the fixture has an unmapped country (Narnia)."""
    client = AlibabaClient()
    res = client.build_envelope_for_rows(snapshot_rows, public_inputs={})
    assert res["data"]["meta"]["unmapped_country"] == 1


# ----------------------------------------------------------------------------
# Filters / caps
# ----------------------------------------------------------------------------


async def test_max_products_cap(snapshot_rows: list[dict]) -> None:
    """``max_products`` caps emitted product rows."""
    client = AlibabaClient()
    res = client.build_envelope_for_rows(
        snapshot_rows,
        public_inputs={"max_products": 2},
    )
    assert len(res["data"]["data"]) == 2
    assert res["data"]["meta"]["emitted_by_entity"]["product"] == 2
    assert res["data"]["meta"]["skipped_by_reason"].get("max_products_cap") == 4


# ----------------------------------------------------------------------------
# Invalid-inputs paths (no BrightData call)
# ----------------------------------------------------------------------------


async def test_invalid_inputs_max_pages_too_high() -> None:
    """``max_pages=11`` (above cap) => INVALID_INPUTS, BrightData NOT called."""
    res = await trigger({"max_pages": 11})
    assert res["status"] == "failed"
    assert res["error"]["code"] == "INVALID_INPUTS"
    assert res["error"]["retriable"] is False


async def test_invalid_inputs_max_products_too_high() -> None:
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


async def test_invalid_inputs_min_price_negative() -> None:
    """``min_price=-1`` => INVALID_INPUTS (ge=0)."""
    res = await trigger({"min_price": -1})
    assert res["status"] == "failed"
    assert res["error"]["code"] == "INVALID_INPUTS"


# ----------------------------------------------------------------------------
# Translation: public inputs → JS scraper inputs
# ----------------------------------------------------------------------------


async def test_input_translation_default() -> None:
    """Default inputs → 5 canonical seeds (one per default term)."""
    client = AlibabaClient()
    seeds = client._build_brightdata_inputs(AlibabaInputs())
    assert len(seeds) == len(DEFAULT_SEARCH_TERMS)
    for seed, term in zip(seeds, DEFAULT_SEARCH_TERMS):
        assert seed["url"] == search_url(term)
        assert seed["search_keyword"] == term
        assert seed["max_pages"] == 5
        assert seed["min_price"] == 1.0
        assert seed["max_price"] == 10000.0
        assert "supplier_country" not in seed  # no filter by default


async def test_input_translation_custom_terms() -> None:
    """Custom term list → one seed per term."""
    client = AlibabaClient()
    seeds = client._build_brightdata_inputs(
        AlibabaInputs(
            search_terms=["sodium benzoate", "potassium sorbate"],
            max_pages=3,
            supplier_country="CN",
        )
    )
    assert len(seeds) == 2
    assert seeds[0]["search_keyword"] == "sodium benzoate"
    assert seeds[0]["url"] == search_url("sodium benzoate")
    # URL uses '+' for spaces, matching alibaba's own encoding convention.
    assert "SearchText=sodium+benzoate" in seeds[0]["url"]
    assert seeds[0]["max_pages"] == 3
    assert seeds[0]["supplier_country"] == "CN"
    assert seeds[1]["search_keyword"] == "potassium sorbate"


async def test_input_translation_empty_terms_uses_defaults() -> None:
    """Empty list is treated like ``None`` — use the 5 canonical defaults."""
    client = AlibabaClient()
    seeds = client._build_brightdata_inputs(AlibabaInputs(search_terms=[]))
    assert len(seeds) == len(DEFAULT_SEARCH_TERMS)


async def test_input_translation_max_products_not_in_seed() -> None:
    """``max_products`` is post-download; never in the trigger seed."""
    client = AlibabaClient()
    seeds = client._build_brightdata_inputs(AlibabaInputs(max_products=50))
    for seed in seeds:
        assert "max_products" not in seed


async def test_search_url_encoding() -> None:
    """Spaces → '+' (alibaba's own convention); round-trips on the scraper side."""
    assert search_url("industrial chemicals").endswith(
        "SearchText=industrial+chemicals&has4Tab=true"
    )


# ----------------------------------------------------------------------------
# Row coercion & classification
# ----------------------------------------------------------------------------


async def test_coerce_product_fills_missing_keys() -> None:
    """A sparse product row still emits every §2/§5 key."""
    raw = {
        "product_url": "https://www.alibaba.com/product-detail/X_1.html",
        "product_name_clean": "minimal",
    }
    out = _coerce_product(raw)
    for key in PRODUCT_FIELDS:
        assert key in out
    assert out["entity"] == "product"
    assert out["site"] == "alibaba"
    assert out["product_url"] == "https://www.alibaba.com/product-detail/X_1.html"
    assert out["scraper_flags"] == []
    assert out["supplier_name"] is None
    assert out["price_min_usd"] is None


async def test_coerce_product_alias_moq() -> None:
    """``minimum_order_quantity`` is aliased to ``moq_quantity``."""
    raw = {
        "product_url": "u",
        "product_name_clean": "x",
        "minimum_order_quantity": 250,
    }
    out = _coerce_product(raw)
    assert out["moq_quantity"] == 250


async def test_coerce_product_preserves_existing_scraper_flags() -> None:
    """Scraper-emitted flags are preserved when middleware adds country_unmapped."""
    raw = {
        "product_url": "u",
        "product_name_clean": "x",
        "supplier_country": "Narnia",
        "scraper_flags": ["captcha_detected"],
    }
    out = _coerce_product(raw)
    assert "captcha_detected" in out["scraper_flags"]
    assert "country_unmapped" in out["scraper_flags"]
    # No duplicates.
    assert out["scraper_flags"].count("country_unmapped") == 1


async def test_coerce_product_site_cannot_be_overridden() -> None:
    """site='alibaba' is fixed by spec §1 — scraper cannot override it."""
    raw = {
        "product_url": "u",
        "product_name_clean": "x",
        "site": "evil.com",
    }
    out = _coerce_product(raw)
    assert out["site"] == "alibaba"


async def test_classify_entity_explicit() -> None:
    """Explicit ``entity`` / ``type`` discriminator works."""
    assert _classify_entity({"entity": "product", "foo": 1}) == "product"
    assert _classify_entity({"type": "product"}) == "product"
    # §9 ``type`` values (chemical / packaging) are NOT discriminators; the
    # row still classifies as product via the product_url / name signal.
    assert _classify_entity({"type": "chemical", "product_url": "u"}) == "product"


async def test_classify_entity_heuristic_product() -> None:
    """Any product-name or URL signal => product."""
    assert _classify_entity({"product_url": "u"}) == "product"
    assert _classify_entity({"url": "u"}) == "product"
    assert _classify_entity({"product_name_clean": "x"}) == "product"
    assert _classify_entity({"cleaned_product_name": "x"}) == "product"


async def test_classify_entity_unknown() -> None:
    """Row without any signal => None."""
    assert _classify_entity({"foo": "bar"}) is None


async def test_unknown_entity_counted(snapshot_rows: list[dict]) -> None:
    """An un-classifiable row lands in ``skipped_by_reason['unknown_entity']``."""
    rows = list(snapshot_rows) + [{"foo": "bar"}]
    client = AlibabaClient()
    res = client.build_envelope_for_rows(rows, public_inputs={})
    assert res["data"]["meta"]["skipped_by_reason"].get("unknown_entity") == 1


async def test_non_dict_row_counted() -> None:
    """Non-dict row => counted under ``errors`` and ``non_dict_row``."""
    rows: list[Any] = [
        {"product_url": "u", "product_name_clean": "x"},
        "not-a-dict",
        42,
    ]
    client = AlibabaClient()
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
            "product_url": f"https://www.alibaba.com/product-detail/p_{i}.html",
            "product_name_clean": f"p_{i}",
            "scraper_flags": ["rate_limit_blocked"] if i < 6 else [],
        })
    client = AlibabaClient()
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
            "product_url": f"https://www.alibaba.com/product-detail/p_{i}.html",
            "product_name_clean": f"p_{i}",
            "price_min_usd": 1.0,
            "scraper_flags": ["rate_limit_blocked"] if i < 3 else [],
        })
    client = AlibabaClient()
    res = client.build_envelope_for_rows(rows, public_inputs={"max_products": 100})
    final = _maybe_block_saturation(res)
    assert final["status"] == "done"


async def test_captcha_detected_also_counts_as_blocked() -> None:
    """``captcha_detected`` flag feeds the same blocked counter."""
    rows: list[dict[str, Any]] = []
    for i in range(4):
        rows.append({
            "product_url": f"u{i}",
            "product_name_clean": "x",
            "scraper_flags": ["captcha_detected"] if i < 3 else [],
        })
    client = AlibabaClient()
    res = client.build_envelope_for_rows(rows, public_inputs={})
    assert res["data"]["meta"]["blocked"] == 3


# ----------------------------------------------------------------------------
# PRICE_MISSING_SATURATION
# ----------------------------------------------------------------------------


async def test_price_missing_saturation_threshold() -> None:
    """>70% of product rows with null price_min_usd => PRICE_MISSING_SATURATION."""
    rows: list[dict[str, Any]] = []
    for i in range(10):
        rows.append({
            "product_url": f"https://www.alibaba.com/product-detail/p_{i}.html",
            "product_name_clean": f"p_{i}",
            # 8/10 (80%) have no price.
            "price_min_usd": None if i < 8 else 1.0,
        })
    client = AlibabaClient()
    res = client.build_envelope_for_rows(rows, public_inputs={"max_products": 100})
    final = _maybe_price_missing_saturation(res)
    assert final["status"] == "failed"
    assert final["error"]["code"] == "PRICE_MISSING_SATURATION"
    assert final["error"]["details"]["missing_price"] == 8


async def test_price_missing_saturation_below_threshold() -> None:
    """≤70% missing price => envelope returned as-is."""
    rows: list[dict[str, Any]] = []
    for i in range(10):
        rows.append({
            "product_url": f"https://www.alibaba.com/product-detail/p_{i}.html",
            "product_name_clean": f"p_{i}",
            # 5/10 (50%) have no price.
            "price_min_usd": None if i < 5 else 1.0,
        })
    client = AlibabaClient()
    res = client.build_envelope_for_rows(rows, public_inputs={"max_products": 100})
    final = _maybe_price_missing_saturation(res)
    assert final["status"] == "done"


# ----------------------------------------------------------------------------
# Credentials / dual-mode selection
# ----------------------------------------------------------------------------


async def test_credentials_required_at_trigger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing credentials surface as INVALID_INPUTS at trigger time."""
    monkeypatch.delenv("BRIGHTDATA_API_KEY", raising=False)
    monkeypatch.delenv("BRIGHTDATA_DATASET_ID_ALIBABA", raising=False)
    monkeypatch.delenv("BRIGHTDATA_COLLECTOR_ID_ALIBABA", raising=False)
    res = await trigger({})
    assert res["status"] == "failed"
    assert res["error"]["code"] == "INVALID_INPUTS"


async def test_resolve_mode_v3_wins_over_dca(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When both env vars are set, v3 wins."""
    monkeypatch.setenv("BRIGHTDATA_DATASET_ID_ALIBABA", "gd_test_v3")
    monkeypatch.setenv("BRIGHTDATA_COLLECTOR_ID_ALIBABA", "c_test_dca")
    client = AlibabaClient()
    assert client.api_mode == "v3"
    assert client.resource_id == "gd_test_v3"


async def test_resolve_mode_dca_when_only_dca_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("BRIGHTDATA_DATASET_ID_ALIBABA", raising=False)
    monkeypatch.setenv("BRIGHTDATA_COLLECTOR_ID_ALIBABA", "c_test_dca")
    client = AlibabaClient()
    assert client.api_mode == "dca"
    assert client.resource_id == "c_test_dca"


async def test_resolve_mode_v3_when_only_v3_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BRIGHTDATA_DATASET_ID_ALIBABA", "gd_test_v3")
    monkeypatch.delenv("BRIGHTDATA_COLLECTOR_ID_ALIBABA", raising=False)
    client = AlibabaClient()
    assert client.api_mode == "v3"
    assert client.resource_id == "gd_test_v3"


async def test_resolve_mode_none_surfaces_invalid_inputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No env vars populated → ``INVALID_INPUTS`` naming both env vars in msg."""
    monkeypatch.setenv("BRIGHTDATA_API_KEY", "fake_key_for_test")
    monkeypatch.delenv("BRIGHTDATA_DATASET_ID_ALIBABA", raising=False)
    monkeypatch.delenv("BRIGHTDATA_COLLECTOR_ID_ALIBABA", raising=False)
    res = await trigger({})
    assert res["status"] == "failed"
    assert res["error"]["code"] == "INVALID_INPUTS"
    msg = res["error"]["message"]
    assert "BRIGHTDATA_DATASET_ID_ALIBABA" in msg
    assert "BRIGHTDATA_COLLECTOR_ID_ALIBABA" in msg


async def test_explicit_api_mode_overrides_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Explicit ``api_mode=`` and ``resource_id=`` beat env vars."""
    monkeypatch.setenv("BRIGHTDATA_DATASET_ID_ALIBABA", "gd_env")
    monkeypatch.setenv("BRIGHTDATA_COLLECTOR_ID_ALIBABA", "c_env")
    client = AlibabaClient(api_mode="dca", resource_id="c_override")
    assert client.api_mode == "dca"
    assert client.resource_id == "c_override"


async def test_dataset_id_alias_silent_backwards_compat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``dataset_id=`` kwarg aliases ``resource_id=`` silently (no warning)."""
    import warnings

    monkeypatch.delenv("BRIGHTDATA_DATASET_ID_ALIBABA", raising=False)
    monkeypatch.delenv("BRIGHTDATA_COLLECTOR_ID_ALIBABA", raising=False)
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        client = AlibabaClient(dataset_id="gd_from_alias")
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
    assert names == {"alibaba_trigger", "alibaba_get_result"}
    for tool in TOOL_SCHEMA:
        assert "description" in tool
        assert "input_schema" in tool
        assert tool["input_schema"]["type"] == "object"
        assert tool["input_schema"].get("additionalProperties") is False


async def test_per_scraper_error_codes_extendcore() -> None:
    """The alibaba error code extension does not redefine base codes."""
    for code in ALIBABA_ERROR_CODES:
        assert code not in NORMALIZED_CODES, (
            f"Per-scraper code {code!r} collides with base catalog."
        )


async def test_pydantic_row_model_smoke(snapshot_rows: list[dict]) -> None:
    """Every fixture row round-trips through the product model cleanly (after aliasing)."""
    from middlewares.alibaba.client import _apply_aliases
    from middlewares.alibaba.models import PRODUCT_ALIASES

    for raw in snapshot_rows:
        aliased = _apply_aliases(raw, PRODUCT_ALIASES)
        # Pydantic must accept the aliased shape.
        ProductRow(**aliased)
