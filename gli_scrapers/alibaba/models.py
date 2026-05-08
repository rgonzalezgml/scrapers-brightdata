"""Pydantic v2 models for the ``alibaba`` middleware.

- :class:`AlibabaInputs` — public inputs validated *before* calling BrightData.
  Validation failure = ``INVALID_INPUTS`` (no API call made).
- :class:`ProductRow` — schema for each item in ``envelope["data"]``.

Per spec §2 the scraper declares a single entity: ``product`` (one row per
SKU). Every row carries an ``entity`` discriminator for parity with the
other multi-entity middlewares (``cosme``, ``olive-young``) — the agents
repo routes on ``entity`` uniformly across scrapers. The ``supplier_*``
fields live *on* the product row per spec §4/§5, not as a separate entity.

Adding a future ``supplier`` entity would be a spec §2 extension and is NOT
in scope here; when it arrives we add a ``SupplierRow`` next to
``ProductRow`` and update :data:`_classify_entity` in ``client.py`` — the
plumbing already supports heterogeneous ``data[]``.

No reinterpretation: the middleware never synthesizes values that are not
in the scraper's output. Missing atomic fields pass through as ``null``,
missing list fields as ``[]`` (spec §10 "ausencias siempre null explicito.
Listas que no aplican van como [] nunca null").
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

# ---- Public inputs ----------------------------------------------------------


class AlibabaInputs(BaseModel):
    """Public inputs accepted by ``trigger()``.

    These are the *agent-facing* knobs. Translation to the JS scraper's
    runtime inputs (``input.url`` / ``input.search_keyword`` /
    ``input.max_pages`` / ``input.supplier_country`` / ``input.min_price`` /
    ``input.max_price`` / ``input.min_order_quantity``) happens in
    :meth:`AlibabaClient._build_brightdata_inputs`.

    The scraper emits **one BrightData seed per search term** — a run with
    ``search_terms=[t1, t2, t3]`` triggers three seeds in parallel. Each seed
    crawls up to ``max_pages`` listing pages and follows every product
    detail link found. Default search_terms cover the 5 canonical chemical
    + packaging keywords from spec §3.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    search_terms: list[Annotated[str, Field(min_length=1, max_length=120)]] | None = None
    """Keywords to feed the Alibaba trade search. ``None`` or empty list
    means "use the 5 default canonical terms from spec §3". Each term maps
    to one BrightData trigger seed. Bounded at 20 items to keep the
    BrightData payload predictable."""

    max_pages: Annotated[int, Field(ge=1, le=100)] = 20
    """Listing pages to crawl per search term. The interaction code caps
    this at ``min(input.max_pages || 5, 100)``; we enforce the same bound
    here so the middleware never sends a value the scraper will clamp."""

    supplier_country: str | None = None
    """Optional ISO-2 country filter applied by the JS Stage 1 filter
    (vendor interaction code line 47-56). ``None`` means "no country
    restriction"; to get the canonical CN-only behavior the spec §3
    describes, pass ``"CN"`` explicitly. The middleware does not enforce
    ISO-2 validity — the scraper tolerates any string and falls through the
    filter when it does not match."""

    min_order_quantity: Annotated[int, Field(ge=1)] | None = None
    """Minimum order quantity filter forwarded to the JS scraper as
    ``input.min_order_quantity``. The vendor interaction code passes it
    through to each product next_stage so Stage 2 can filter cards below
    this MOQ. ``None`` means no restriction."""

    min_price: Annotated[float, Field(ge=0)] | None = None
    """Minimum product price (USD) for the Stage 1 card filter. ``None``
    means "no lower bound"; defaults to 1 USD in the scraper if omitted
    (spec §3, genomma lab)."""

    max_price: Annotated[float, Field(ge=0)] | None = None
    """Maximum product price (USD) for the Stage 1 card filter. ``None``
    means "no upper bound"; defaults to 10000 USD in the scraper if
    omitted."""

    max_products: Annotated[int, Field(ge=1, le=10000)] = 2000
    """Hard cap on emitted product rows. Applied post-download as a clip on
    the envelope's ``data[]``; the scraper itself has no such knob. A
    5-term x 5-page run comfortably fits under 2000 products even with
    ~80 cards per page of overlap."""

    mode: Literal["incremental", "full-refresh"] = "incremental"
    """``incremental`` hints to the agents repo that its dedup cache (by
    ``product_url + scraped_date`` per spec §10) is in force;
    ``full-refresh`` requests a cold run. The scraper is stateless and does
    not differentiate — this flag is reserved for the agents-repo cache
    key."""


# ---- Shared discriminator ---------------------------------------------------

# Spec §2 declares only ``product`` today. Kept as a Literal (rather than a
# plain str) so mypy / pydantic reject typos upstream. When the spec adds
# ``supplier`` it becomes ``Literal["product", "supplier"]``.
Entity = Literal["product"]


# ---- Product (spec §2 + §4 + §5) --------------------------------------------


class ProductRow(BaseModel):
    """One product row in ``envelope["data"]`` (spec §2 + §4 + §5).

    §2 strict keys (16 — the scraper MUST emit every one, ``None``/``[]``
    when data is missing):

        product_name_clean, product_name_original, type, category,
        price_raw, price_min_usd, price_max_usd, price_unit,
        price_normalized_per_kg, moq_quantity, moq_unit,
        supplier_name, supplier_country, supplier_verified,
        product_url, scraped_date

    §5 reputation keys (3 optional, frequent):

        supplier_rating, supplier_reviews_count, supplier_response_rate

    Additional debug keys used by the middleware / scraper:

        entity (discriminator), scraper_flags (spec §10 allow-list),
        site (always "alibaba" per spec §1).
    """

    # ``extra="allow"`` — the JS parser may add new debug keys as we iterate
    # (e.g. ``_price_parser_used``, ``_category_reason``). We forward them
    # verbatim; the agents repo opts in. Same convention as cosme.
    model_config = ConfigDict(extra="allow")

    entity: Literal["product"] = "product"

    # ---- §2 strict (16) ---------------------------------------------------
    product_name_clean: str | None = None
    product_name_original: str | None = None
    type: Literal["chemical", "packaging"] | None = None
    """Spec §9 enum. ``None`` when the scraper could not classify (e.g. a row
    that slipped past the skip filter but has no usable name)."""
    category: str | None = None
    """Spec §9 enum: ``Alkali | Acid | Solvent | Surfactant | Preservative |
    Fragrance | Packaging_Drum | Packaging_Bag | Packaging_Container |
    Glycol | Silicate | Polymer | Corrosion | Bleach | Fertilizer | Other``.
    We keep it as ``str`` (not Literal) because spec §9 lists 16 values
    across the two types and new ones may arrive; the scraper is the source
    of truth for the enum."""
    price_raw: str | None = None
    price_min_usd: float | None = None
    price_max_usd: float | None = None
    price_unit: str | None = None
    """Spec §4 enum: ``kg | ton | L | piece | mt | set | null``. Not Literal
    because the scraper treats unknown units as ``null`` + a flag."""
    price_normalized_per_kg: float | None = None
    moq_quantity: int | None = None
    moq_unit: str | None = None
    supplier_name: str | None = None
    supplier_country: str | None = None
    """ISO-2 country code per spec §4. The middleware normalizes free-text
    labels (e.g. ``"China"``) to ISO-2 via
    :data:`gli_scrapers.alibaba.config.COUNTRY_TO_ISO2`; unmapped values
    become ``null`` + ``country_unmapped`` flag."""
    supplier_verified: bool | None = None
    product_url: str | None = None
    scraped_date: str | None = None

    # ---- §5 reputation (3 optional) ---------------------------------------
    supplier_rating: float | None = None
    supplier_reviews_count: int | None = None
    supplier_response_rate: str | None = None

    # ---- Middleware-added metadata ----------------------------------------
    site: str = "alibaba"
    """Spec §1 (genomma lab): "Campo site fijo alibaba". Injected by the
    middleware on every row so cross-source joins in the agents repo /
    downstream warehouse can group-by it without having to introspect
    ``source`` from the envelope."""

    scraper_flags: list[str] = Field(default_factory=list)
    """Spec §10 allow-list: ``name_clean_fallback``, ``rating_invalid``,
    ``price_fx_needed``, ``price_unit_unknown``, ``schema_change``,
    ``captcha_detected``, ``rate_limit_blocked``. The middleware APPENDS
    its own flags (``country_unmapped``) — it never removes flags the
    scraper set."""


# ---- Field catalog (used by the client to coerce rows) ----------------------

PRODUCT_FIELDS: tuple[str, ...] = tuple(ProductRow.model_fields.keys())

# Fields that must be a list on the wire (spec §10 "listas ... van como []
# nunca null"). Keep in sync with Field(default_factory=list) above.
PRODUCT_LIST_FIELDS: frozenset[str] = frozenset({"scraper_flags"})

# Map from the JS parser's key name → the middleware's wire name.
#
# The vendor parser today emits a *very* different shape (see
# scrapers/alibaba/vendor/sc_code/parser_code.js: ``cleaned_product_name``,
# ``minimum_order_quantity``, plus non-§2 fields like ``cas_number`` /
# ``purity``). The spec §2 names are the canonical ones the v1+ JS parsers
# will emit once the vendor gap is closed.
#
# The aliases below cover BOTH the spec-compliant names (passthrough) AND the
# current vendor names — so a snapshot captured from the vendor today still
# produces a spec-shaped envelope without waiting for the JS rewrite.
PRODUCT_ALIASES: dict[str, str] = {
    # vendor → spec §2
    "cleaned_product_name": "product_name_clean",
    "minimum_order_quantity": "moq_quantity",
    # Common scraper-side variants seen across the sibling made-in-china spec
    # and the genomma lab Python connector referenced in spec §3. These are
    # defensive: renaming cost is negligible, and a snapshot produced with
    # slightly different key names still lands cleanly in the envelope.
    "name_raw": "product_name_original",
    "name_clean": "product_name_clean",
    "url": "product_url",
    "moq": "moq_quantity",
    "moq_unit_raw": "moq_unit",
    "supplier": "supplier_name",
    "country": "supplier_country",
    "verified": "supplier_verified",
    "rating": "supplier_rating",
    "reviews_count": "supplier_reviews_count",
    "response_rate": "supplier_response_rate",
}
