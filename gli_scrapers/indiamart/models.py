"""Pydantic v2 models for the ``indiamart`` middleware.

- :class:`IndiamartInputs` — public inputs validated *before* calling
  BrightData. Validation failure = ``INVALID_INPUTS`` (no API call made).
- :class:`ProductRow`, :class:`SupplierRow` — per-entity schemas for items
  in ``envelope["data"]``.

indiamart is a **multi-entity** scraper (spec §2): ``data[]`` is
heterogeneous, each row carrying an ``entity`` discriminator (``"product"``
or ``"supplier"``) plus the entity-specific fields. Same pattern as
``cosme`` (multi-entity), different from ``cosmetics_design``
(single-entity).

The strict §2 schema is:

    product:  product_id, url, name_clean, type, category_mic,
              category_path, price_min_usd, price_max_usd, price_unit,
              price_currency, moq_quantity, moq_unit, supplier_id,
              supplier_city, scraped_date
    supplier: supplier_id, url, name, country, city, state, business_type,
              member_since_year, verified, trustseal

§4-§7 catalog the verbose keys the JS parser actually emits
(``product_url``, ``supplier_name``, ``supplier_url``, ``verified_exporter``,
``scraper_flags`` ...). The middleware aliases those back to the §2 short
names on the wire; anything the JS scraper emits beyond the catalog is
forwarded verbatim via ``extra="allow"``.

No reinterpretation: the middleware never synthesizes values the scraper
did not emit — missing atomic fields surface as ``null``, missing list
fields as ``[]`` (spec §5 "Todos los campos con null explicito cuando
faltan; nunca omitir la clave.").
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# ---- Public inputs ----------------------------------------------------------


class IndiamartInputs(BaseModel):
    """Public inputs accepted by ``trigger()``.

    Agent-facing semantics (not the JS scraper's internal knobs). Translation
    to Stage 1 seed URLs (``dir.indiamart.com/impcat/<slug>.html`` and
    ``dir.indiamart.com/indianexporters/ind_<industry>.html``) happens in
    :meth:`IndiamartClient._build_brightdata_inputs`.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    mcat_slugs: list[str] | None = None
    """Optional explicit list of MCAT category slugs to seed Stage 1 with.
    Each slug expands to ``dir.indiamart.com/impcat/{slug}.html``. When
    ``None`` the middleware uses the 12 default slugs (spec §9). Bounded at
    [1, MAX_MCAT_SEEDS_HARD_CAP]."""

    industry_hubs: list[str] | None = None
    """Optional explicit list of industry hub codes (e.g. ``"chem"``,
    ``"packaging"``) to seed Stage 1 with. Each expands to
    ``dir.indiamart.com/indianexporters/ind_<code>.html``. When ``None`` uses
    the 2 default hubs (spec §9)."""

    include_industry_hubs: bool = True
    """If ``False``, do not emit industry hub seeds — only MCATs. Useful for
    tight runs where the ~100 MCATs each hub enumerates would blow past the
    request budget."""

    max_products: Annotated[int, Field(ge=1, le=1500)] = 500
    """Hard cap on emitted product rows. Spec §9 caps unique PRODUCT_ID
    detail pages at 1500 per run. The middleware clips post-download — the
    scraper itself runs until the BrightData-side cap or site exhaustion."""

    max_suppliers: Annotated[int, Field(ge=0, le=300)] = 150
    """Hard cap on emitted supplier rows. Spec §9 caps supplier home visits
    at 300. Zero is allowed — suppresses every supplier row from the
    envelope even if the scraper emitted them."""

    include_suppliers: bool = True
    """If ``False``, drop every ``supplier`` row from the envelope's
    ``data[]`` regardless of ``max_suppliers``. The scraper still crawls
    suppliers (it cannot be disabled at the JS layer) — this only affects
    post-download filtering."""

    mode: Literal["incremental", "full-refresh"] = "incremental"
    """``incremental`` respects the dedup / cache heuristics spec §9 describes
    (24h cache per product_id); ``full-refresh`` requests a cold run. The JS
    scraper does not differentiate today — this flag is reserved for the
    agents repo to key its own cache TTL. The middleware forwards it into
    ``envelope["inputs"]`` so downstream can decide."""


# ---- Shared row base --------------------------------------------------------

# Discriminator literal used on every envelope data row.
Entity = Literal["product", "supplier"]


# ---- Product (spec §2 + §4 + §5) -------------------------------------------


class ProductRow(BaseModel):
    """One product row in ``envelope["data"]`` (spec §2 / §4 / §5).

    §2 strict keys:

        product_id, url, name_clean, type, category_mic, category_path,
        price_min_usd, price_max_usd, price_unit, price_currency,
        moq_quantity, moq_unit, supplier_id, supplier_city, scraped_date

    §4 / §5 additional keys (null or [] when missing):

        site_code, product_url, product_name_original, product_description,
        image_primary, industry_slug, price_raw, price_value_raw,
        availability, supplier_name, supplier_state, supplier_country,
        cas_no, grade, appearance, packaging_type, concentration,
        price_normalized_per_kg, scraper_flags
    """

    # ``extra="allow"`` — the JS parser may add future debug keys (e.g.
    # ``_price_source``, ``_moq_source``). We forward them verbatim; the
    # agents repo opts in.
    model_config = ConfigDict(extra="allow")

    entity: Literal["product"] = "product"

    # ---- §2 strict --------------------------------------------------------
    product_id: str | None = None
    url: str | None = None
    name_clean: str | None = None
    type: str | None = None
    category_mic: str | None = None
    category_path: list[str] = Field(default_factory=list)
    price_min_usd: float | None = None
    price_max_usd: float | None = None
    price_unit: str | None = None
    price_currency: str | None = None
    moq_quantity: int | None = None
    moq_unit: str | None = None
    supplier_id: str | None = None
    supplier_city: str | None = None
    scraped_date: str | None = None

    # ---- §4 additional ----------------------------------------------------
    site_code: str | None = None
    product_name_original: str | None = None
    product_description: str | None = None
    image_primary: str | None = None
    industry_slug: str | None = None
    price_raw: str | None = None
    price_value_raw: str | None = None
    availability: str | None = None
    supplier_name: str | None = None
    supplier_state: str | None = None
    supplier_country: str | None = None

    # ---- §5 additional (specs table) --------------------------------------
    cas_no: str | None = None
    grade: str | None = None
    appearance: str | None = None
    packaging_type: str | None = None
    concentration: str | None = None
    price_normalized_per_kg: float | None = None

    # ---- Flags ------------------------------------------------------------
    scraper_flags: list[str] = Field(default_factory=list)


# ---- Supplier (spec §2 + §6) -----------------------------------------------


class SupplierRow(BaseModel):
    """One supplier row (spec §2 / §6).

    §2 strict keys:

        supplier_id, url, name, country, city, state, business_type,
        member_since_year, verified, trustseal

    §6 additional keys (null when missing):

        supplier_url, supplier_name, year_established, verified_exporter,
        gst, annual_turnover, certifications, scraped_date, scraper_flags
    """

    model_config = ConfigDict(extra="allow")

    entity: Literal["supplier"] = "supplier"

    # ---- §2 strict --------------------------------------------------------
    supplier_id: str | None = None
    url: str | None = None
    name: str | None = None
    country: str | None = None
    city: str | None = None
    state: str | None = None
    business_type: str | None = None
    member_since_year: int | None = None
    verified: bool | None = None
    trustseal: bool | None = None

    # ---- §6 additional ----------------------------------------------------
    year_established: int | None = None
    gst: str | None = None
    annual_turnover: str | None = None
    certifications: list[str] = Field(default_factory=list)
    scraped_date: str | None = None

    # ---- Flags ------------------------------------------------------------
    scraper_flags: list[str] = Field(default_factory=list)


# ---- Field catalog (used by the client to coerce rows) ----------------------

PRODUCT_FIELDS: tuple[str, ...] = tuple(ProductRow.model_fields.keys())
SUPPLIER_FIELDS: tuple[str, ...] = tuple(SupplierRow.model_fields.keys())

# Fields that must be a list on the wire (spec §5 / §6 "listas vacias nunca
# null"). Keep in sync with Field(default_factory=list) above.
PRODUCT_LIST_FIELDS: frozenset[str] = frozenset(
    {
        "category_path",
        "scraper_flags",
    }
)
SUPPLIER_LIST_FIELDS: frozenset[str] = frozenset(
    {
        "certifications",
        "scraper_flags",
    }
)

# Map from the JS parser's key name → the middleware's wire name. Spec §2
# uses short forms (``url``, ``name_clean``, ``name``); the JS scraper emits
# verbose qualified names (``product_url``, ``supplier_url``,
# ``supplier_name``, ``verified_exporter``) so the multi-entity output is
# unambiguous on the scraper side. The middleware renames on the way out so
# the envelope matches §2 literally. New entries here = new scraper field we
# want to alias; never invent values, only rename keys that already exist in
# the raw row.
PRODUCT_ALIASES: dict[str, str] = {
    "product_url": "url",
}

# NOTE: ``supplier_name``, ``supplier_url``, ``verified_exporter`` appear
# in BOTH entities with different meanings:
#   - On product: they are foreign keys / denormalized copies (supplier_*).
#     Kept verbatim under the ``supplier_*`` name — do NOT alias to ``url`` /
#     ``name`` (those are the *product*'s url/name in a product row).
#   - On supplier: they are the entity's own identity. We alias them here so
#     the supplier row matches §2 short names.
SUPPLIER_ALIASES: dict[str, str] = {
    "supplier_url": "url",
    "supplier_name": "name",
    "supplier_city": "city",
    "supplier_state": "state",
    "supplier_country": "country",
    "verified_exporter": "verified",
    # trustseal_verified is the occasional alternate name for the bool.
    "trustseal_verified": "trustseal",
}


# ---- ISO-2 country mapping (spec §2/§6: supplier_country is ISO-2) ----------

# The scraper emits ``supplier_country = "IN"`` literal per spec §4, but
# historically vendor code (e.g. made-in-china) has been known to emit free
# text like ``"India"``. We normalize defensively. Only map names known to
# appear in IndiaMART data — anything else surfaces as-is with a scraper
# flag so the agents repo can triage.
COUNTRY_NAME_TO_ISO2: dict[str, str] = {
    "india": "IN",
    "in": "IN",
    # IndiaMART has a foreign exporters section we do NOT crawl today
    # (robots disallow /foreignexporters/), so in practice IN is the only
    # value. The extras below are defensive for when a future scraper
    # version expands scope.
    "united states": "US",
    "usa": "US",
    "china": "CN",
    "united arab emirates": "AE",
    "uae": "AE",
    "united kingdom": "GB",
    "uk": "GB",
}
