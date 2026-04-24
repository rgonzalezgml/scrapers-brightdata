"""Pydantic v2 models for the ``made_in_china`` middleware.

- :class:`MadeInChinaInputs` — public inputs validated *before* calling
  BrightData. Validation failure = ``INVALID_INPUTS`` (no API call made).
- :class:`ProductRow`, :class:`SupplierRow` — per-entity schemas for items
  in ``envelope["data"]``.

made-in-china is a **multi-entity** scraper (spec §2: entities ``product`` +
``supplier``). ``data[]`` is heterogeneous, each row carrying an ``entity``
discriminator (``"product"`` | ``"supplier"``) plus the entity-specific
fields. Mirrors the pattern of ``middlewares/cosme/`` (3 entities) and
contrasts with the single-entity ``middlewares/cosmetics_design/``.

Schema authority
----------------

§2 of ``docs/specs/scrapers/made-in-china.md`` is the immutable wire shape.
The two entity key lists come straight from that §2:

    product: product_id, sku, site_code, product_url, product_name_original,
             product_name_clean, type, category_mic, category_path, price_raw,
             price_currency, price_min_usd, price_max_usd, price_unit,
             price_normalized_per_kg, moq_quantity, moq_unit, image_primary,
             cas_no, grade, appearance, formula, einecs, origin_country,
             supplier_name_raw, rating_avg, supplier_id, scraped_date,
             scraper_flags
    supplier: supplier_id, supplier_url, supplier_name, supplier_country,
              business_type, main_products, year_established, employees_raw,
              member_level, member_since_year, audited_supplier,
              management_certifications, scraped_date, scraper_flags

§4-§6 describe the field-by-field semantics. The middleware does NOT
reinterpret values — missing atomic fields come through as ``null``, missing
list fields as ``[]`` (spec §9 "claves siempre con null explicito, listas
vacias nunca null").
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# ---- Public inputs ----------------------------------------------------------


class MadeInChinaInputs(BaseModel):
    """Public inputs accepted by ``trigger()``.

    Agent-facing semantics (not the JS scraper's internal knobs). Translation
    to the JS runtime inputs (``url``, ``max_pages``, ``is_rerun``) happens
    in :meth:`MadeInChinaClient._build_brightdata_inputs`.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    urls: list[str] | None = None
    """Optional list of seed URLs (spec §3). Each may be a listing
    (via-1 ``/products-search/...`` or via-2 ``/{Chem|Packaging-Printing}-Catalog/...``),
    a detail (``.../product/{ID}/...``), or a supplier home
    (``{slug}.en.made-in-china.com/``). When ``None`` the middleware uses
    :data:`DEFAULT_LISTING_URL`. Bounded at [1, :data:`MAX_SEED_URLS`]."""

    max_pages: Annotated[int, Field(ge=-1, le=500)] = 3
    """Pagination budget forwarded to the JS scraper (spec §9 v5):

        - ``-1`` → process every page up to ``total_pages`` (the ``.page-total``
          widget on the listing).
        - ``N > 0`` → process ``min(N, total_pages)``.
        - ``0`` is normalized to ``-1`` by the interaction code and emits
          ``max_pages_invalid`` at the run level; we accept it here so that
          the wire shape is identical to the scraper's.

    Applies ONLY to listing URLs — detail and supplier-home URLs ignore it."""

    max_products: Annotated[int, Field(ge=1, le=800)] = 400
    """Hard cap on emitted product rows (spec §9: "hasta 800 unique
    PRODUCT_ID detail"). Applied post-download by the middleware; the scraper
    is not reconfigured."""

    max_suppliers: Annotated[int, Field(ge=1, le=200)] = 100
    """Hard cap on emitted supplier rows (spec §9: "hasta 200 supplier home")."""

    include_suppliers: bool = True
    """If ``False``, drop every ``supplier`` row from the envelope's ``data[]``.
    Useful when the agent only needs price comparisons and does not care
    about supplier metadata."""

    require_price: bool = False
    """If ``True``, drop product rows whose ``price_min_usd`` / ``price_max_usd``
    are both ``None`` (spec §8: "SKIP sin emitir fila cuando: price_raw
    ausente"). The scraper already skips on its side; this flag is a
    middleware-side belt-and-suspenders for the cases where the scraper
    emits a row with ``null`` price because JSON-LD offers was absent."""

    mode: Literal["incremental", "full-refresh"] = "incremental"
    """``incremental`` respects the 24h dedup cache on ``product_id`` (spec
    §9); ``full-refresh`` is a hint for the agents repo to bypass its own
    cache. The middleware forwards it into ``envelope["inputs"]`` so
    downstream can decide."""


# ---- Shared row discriminator -----------------------------------------------

Entity = Literal["product", "supplier"]

# Per-spec §9: "claves siempre con null explicito cuando faltan; listas
# vacias nunca null". Enforced in the client's ``_coerce_row`` helper; the
# models below provide defaults so pydantic fills missing keys by default.


# ---- Product (spec §2 + §4 + §5) --------------------------------------------


class ProductRow(BaseModel):
    """One product row in ``envelope["data"]`` (spec §2 / §4 / §5).

    §2 strict keys (29 fields, see module docstring). §4 / §5 list the field
    semantics. Every key is always present with ``null`` / ``[]`` explicit if
    the scraper could not derive it.
    """

    # ``extra="allow"`` — the JS parser may add debug keys (e.g. source of the
    # name, rating author) over time. We forward them; the agents repo opts
    # in. Spec §9 explicitly enumerates the flag catalog but does not forbid
    # diagnostic extras.
    model_config = ConfigDict(extra="allow")

    entity: Literal["product"] = "product"

    # ---- §2 strict (29 keys, exact order of the array) ---------------------
    product_id: str | None = None
    sku: str | None = None
    site_code: str | None = "made-in-china"
    product_url: str | None = None
    product_name_original: str | None = None
    product_name_clean: str | None = None
    type: str | None = None
    category_mic: str | None = None
    category_path: list[str] = Field(default_factory=list)
    price_raw: str | None = None
    price_currency: str | None = None
    price_min_usd: float | None = None
    price_max_usd: float | None = None
    price_unit: str | None = None
    price_normalized_per_kg: float | None = None
    moq_quantity: float | None = None
    moq_unit: str | None = None
    image_primary: str | None = None
    cas_no: str | None = None
    grade: str | None = None
    appearance: str | None = None
    formula: str | None = None
    einecs: str | None = None
    origin_country: str | None = None
    supplier_name_raw: str | None = None
    rating_avg: float | None = None
    supplier_id: str | None = None
    scraped_date: str | None = None
    scraper_flags: list[str] = Field(default_factory=list)


# ---- Supplier (spec §2 + §6) ------------------------------------------------


class SupplierRow(BaseModel):
    """One supplier row (spec §2 / §6).

    §2 strict keys (14 fields). §6 details semantics: ``supplier_id`` is the
    subdomain slug; ``supplier_country`` is ISO-2 (middleware normalizes
    free-text names via :func:`iso2_for_country` + flag ``country_unmapped``).
    """

    model_config = ConfigDict(extra="allow")

    entity: Literal["supplier"] = "supplier"

    # ---- §2 strict (14 keys) -----------------------------------------------
    supplier_id: str | None = None
    supplier_url: str | None = None
    supplier_name: str | None = None
    supplier_country: str | None = None
    business_type: str | None = None
    main_products: str | None = None
    year_established: int | None = None
    employees_raw: str | None = None
    member_level: str | None = None
    member_since_year: int | None = None
    audited_supplier: bool | None = None
    management_certifications: list[str] = Field(default_factory=list)
    scraped_date: str | None = None
    scraper_flags: list[str] = Field(default_factory=list)


# ---- Field catalogs (used by the client to coerce rows) ---------------------

PRODUCT_FIELDS: tuple[str, ...] = tuple(ProductRow.model_fields.keys())
SUPPLIER_FIELDS: tuple[str, ...] = tuple(SupplierRow.model_fields.keys())

# Fields that must be a list on the wire (spec §9 "listas vacias nunca null").
# Keep in sync with Field(default_factory=list) above.
PRODUCT_LIST_FIELDS: frozenset[str] = frozenset(
    {
        "category_path",
        "scraper_flags",
    }
)
SUPPLIER_LIST_FIELDS: frozenset[str] = frozenset(
    {
        "management_certifications",
        "scraper_flags",
    }
)

# Map from JS-parser / legacy key name → §2 wire name. The made-in-china
# parser v3+ already emits §2 names directly, so these aliases are mostly
# a safety net for earlier versions (v1 / v2) and for the legacy vendor
# shape (E8 in errors.md: vendor mixed supplier_* into product). Adding an
# entry here is never "inventing a value" — it only renames a key that
# already exists in the raw row.
PRODUCT_ALIASES: dict[str, str] = {
    # Vendor v0 / v1 names that predate the §2 cleanup.
    "url": "product_url",
    "name_raw": "product_name_original",
    "name_original": "product_name_original",
    "name_clean": "product_name_clean",
    "brand_name": "supplier_name_raw",
    # Some parser drafts emitted ``category`` instead of ``category_mic``.
    "category": "category_mic",
    # The v1 parser used ``moq_qty`` before the spec rename.
    "moq_qty": "moq_quantity",
}

SUPPLIER_ALIASES: dict[str, str] = {
    # Vendor v0 / v1 emitted these short forms on the supplier row.
    "url": "supplier_url",
    "name": "supplier_name",
    "country": "supplier_country",
    # Some drafts misspelled this (errors.md E7 shows "business_types").
    "business_types": "business_type",
    # Legacy shorthand seen in early DB AI output.
    "audited": "audited_supplier",
    "certifications": "management_certifications",
    "member": "member_level",
    "member_year": "member_since_year",
}
