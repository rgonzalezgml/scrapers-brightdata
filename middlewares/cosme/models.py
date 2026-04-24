"""Pydantic v2 models for the ``cosme`` middleware.

- :class:`CosmeInputs` — public inputs validated *before* calling BrightData.
  Validation failure = ``INVALID_INPUTS`` (no API call made).
- :class:`ProductRow`, :class:`RankingRow`, :class:`BrandRow` — per-entity
  schemas for items in ``envelope["data"]``.

cosme is a **multi-entity** scraper (spec §2): ``data[]`` is heterogeneous,
each row carrying an ``entity`` discriminator (``"product"``, ``"ranking"``,
``"brand"``) plus the entity-specific fields. This is different from the
single-entity ``cosmetics_design`` middleware where every row is an article.

The strict schema (§2 of the spec) is:

    product: product_id, url, name_raw, brand_id, category_ids, effect_ids,
             ingredient_tag_ids, rating_avg, review_count, launch_date,
             regulation_class, variants
    ranking: source_type, year, group, category_slug, rank, product_id
    brand:   brand_id, name, url, total_products, total_reviews

§4-§7 of the spec catalog additional frequent fields (``product_name_clean``,
``brand_name``, ``category_names``, ``rankings``, ``scraper_flags`` ...). The
scraper's ``sc_code/parser_code_v*.js`` emits those extra keys; pydantic's
``extra="allow"`` forwards them verbatim — every row is *at least* the strict
§2 keys but may carry more without a middleware release.

No reinterpretation: the middleware never synthesizes values that aren't
already in the scraper's output — missing atomic fields come through as
``null``, missing list fields as ``[]`` (spec §8).
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# ---- Public inputs ----------------------------------------------------------


class CosmeInputs(BaseModel):
    """Public inputs accepted by ``trigger()``.

    Agent-facing semantics (not the JS scraper's internal knobs). Translation
    to Stage 1 ``input.award_year`` / ``input.category`` / ``input.crawl_limit``
    happens in :meth:`CosmeClient._build_brightdata_inputs`.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    year: Annotated[int, Field(ge=2000, le=2100)] | None = None
    """Award / ranking year to crawl (spec §10: used to derive the bestcosme
    archive URL). ``None`` means "the current year at scraper launch time"
    (the JS scraper falls back to ``new Date().getFullYear()``).

    Bounded at [2000, 2100] so fat-finger typos surface as ``INVALID_INPUTS``
    instead of a 404 from the scraper. The Stage 1 code itself tolerates any
    year between 2000 and currentYear+1 (spec §10 resolveYear)."""

    max_products: Annotated[int, Field(ge=1, le=3000)] = 1000
    """Hard cap on emitted product rows (spec §7: detail max 3000 unique
    per run). The scraper does NOT enforce this; the middleware clips the
    envelope's ``data[]`` post-download."""

    max_categories: Annotated[int, Field(ge=1, le=1000)] = 1000
    """Maximum number of category slugs to discover at Stage 1. Maps to the
    JS input ``crawl_limit`` consumed by ``scrapers/cosme/sc_browser/interaction_code_vN.js``."""

    category: str | None = None
    """Optional case-insensitive substring to filter the discovered category
    URLs (spec §10 Stage 1 ``input.category``). If set, only category slugs
    whose URL contains this substring are crawled. Example: ``"skin"`` ->
    skincare-adjacent slugs only."""

    include_rankings: bool = True
    """If ``False``, drop every ``ranking`` row from the envelope's ``data[]``.
    Does NOT reduce the scraper's work — only affects post-download filtering.
    """

    include_brands: bool = True
    """If ``False``, drop every ``brand`` row from the envelope's ``data[]``."""

    mode: Literal["incremental", "full-refresh"] = "incremental"
    """``incremental`` respects the dedup / cache heuristics spec §7 describes
    (24h cache per product_id); ``full-refresh`` requests a cold run. The JS
    scraper does not differentiate today — this flag is reserved for the
    agents repo to key its own cache TTL. The middleware forwards it into
    ``envelope["inputs"]`` so downstream can decide."""


# ---- Shared row base --------------------------------------------------------

# Discriminator literal used on every envelope data row.
Entity = Literal["product", "ranking", "brand"]

# Per-spec §8: "claves siempre presentes con null explícito; listas que no
# aplican van como [] nunca null". We enforce that in ``_coerce_row`` on the
# client side; the models below declare defaults so pydantic fills missing
# keys when possible.


# ---- Product (spec §2 + §4) -------------------------------------------------


class ProductRow(BaseModel):
    """One product row in ``envelope["data"]`` (spec §2 / §4).

    §2 strict keys (renamed on the wire to match §2 literally):

        product_id, url, name_raw, brand_id, category_ids, effect_ids,
        ingredient_tag_ids, rating_avg, review_count, launch_date,
        regulation_class, variants

    §4 additional frequent keys (null when missing):

        name_clean, brand_name, category_primary_id, category_names,
        category_chains, effect_names, review_count_photo, launch_year,
        official_name, is_official, maker_id, maker_name, price_text,
        variations, rankings, scraped_date, scraper_flags
    """

    # ``extra="allow"`` — the JS parser_code_v2+ may add new debug keys (e.g.
    # ``_name_source``, ``has_mojibake``). We forward them; the agents repo
    # opts in.
    model_config = ConfigDict(extra="allow")

    entity: Literal["product"] = "product"

    # ---- §2 strict --------------------------------------------------------
    product_id: str | None = None
    url: str | None = None
    name_raw: str | None = None
    brand_id: str | None = None
    category_ids: list[str] = Field(default_factory=list)
    effect_ids: list[str] = Field(default_factory=list)
    ingredient_tag_ids: list[str] = Field(default_factory=list)
    rating_avg: float | None = None
    review_count: int | None = None
    launch_date: str | None = None
    regulation_class: str | None = None
    variants: list[dict[str, Any]] = Field(default_factory=list)

    # ---- §4 additional ----------------------------------------------------
    name_clean: str | None = None
    brand_name: str | None = None
    category_primary_id: str | None = None
    category_names: list[str] = Field(default_factory=list)
    category_chains: list[list[dict[str, Any]]] = Field(default_factory=list)
    effect_names: list[str] = Field(default_factory=list)
    review_count_photo: int | None = None
    launch_year: int | None = None
    official_name: str | None = None
    is_official: bool | None = None
    maker_id: str | None = None
    maker_name: str | None = None
    price_text: str | None = None
    variations: list[dict[str, Any]] = Field(default_factory=list)
    rankings: list[dict[str, Any]] = Field(default_factory=list)
    scraped_date: str | None = None
    scraper_flags: list[str] = Field(default_factory=list)


# ---- Ranking (spec §2 + §4) -------------------------------------------------


class RankingRow(BaseModel):
    """One ranking row (spec §2 / §4).

    §2 strict keys:

        source_type, year, group, category_slug, rank, product_id

    §4 additional keys: ``category_id``, ``product_url``, ``product_name_raw``,
    ``product_name_clean``, ``brand_name_raw``, ``ai_highlights``,
    ``scraped_date``.

    ``source_type`` is one of ``"bestcosme"`` | ``"category_ranking"``
    (spec §4). The middleware does not enforce the enum — the JS scraper does.
    """

    model_config = ConfigDict(extra="allow")

    entity: Literal["ranking"] = "ranking"

    # ---- §2 strict --------------------------------------------------------
    source_type: str | None = None
    year: int | None = None
    group: str | None = None
    category_slug: str | None = None
    rank: int | None = None
    product_id: str | None = None

    # ---- §4 additional ----------------------------------------------------
    category_id: str | None = None
    product_url: str | None = None
    product_name_raw: str | None = None
    product_name_clean: str | None = None
    brand_name_raw: str | None = None
    ai_highlights: list[str] = Field(default_factory=list)
    scraped_date: str | None = None


# ---- Brand (spec §2 + §5) ---------------------------------------------------


class BrandRow(BaseModel):
    """One brand row (spec §2 / §5).

    §2 strict keys:

        brand_id, name, url, total_products, total_reviews

    §5 additional keys: ``official_site``, ``country``, ``scraped_date``.
    """

    model_config = ConfigDict(extra="allow")

    entity: Literal["brand"] = "brand"

    # ---- §2 strict --------------------------------------------------------
    brand_id: str | None = None
    name: str | None = None
    url: str | None = None
    total_products: int | None = None
    total_reviews: int | None = None

    # ---- §5 additional ----------------------------------------------------
    official_site: str | None = None
    country: str | None = None
    scraped_date: str | None = None


# ---- Field catalog (used by the client to coerce rows) ----------------------

PRODUCT_FIELDS: tuple[str, ...] = tuple(ProductRow.model_fields.keys())
RANKING_FIELDS: tuple[str, ...] = tuple(RankingRow.model_fields.keys())
BRAND_FIELDS: tuple[str, ...] = tuple(BrandRow.model_fields.keys())

# Fields that must be a list on the wire (spec §8 "listas ... van como []
# nunca null"). Keep in sync with Field(default_factory=list) above.
PRODUCT_LIST_FIELDS: frozenset[str] = frozenset(
    {
        "category_ids",
        "effect_ids",
        "ingredient_tag_ids",
        "variants",
        "category_names",
        "category_chains",
        "effect_names",
        "variations",
        "rankings",
        "scraper_flags",
    }
)
RANKING_LIST_FIELDS: frozenset[str] = frozenset({"ai_highlights"})
BRAND_LIST_FIELDS: frozenset[str] = frozenset()

# Map from the JS parser's key name → the middleware's wire name. Spec §2
# uses short names (``url``, ``name_raw``) but the scraper emits long
# qualified names (``product_url``, ``product_name_raw``) to keep its own
# multi-entity output unambiguous. The middleware renames on the way out
# so the envelope matches §2 literally. New entries here = new scraper
# field we want to alias; never invent values, only rename keys that
# already exist in the raw row.
PRODUCT_ALIASES: dict[str, str] = {
    "product_url": "url",
    "product_name_raw": "name_raw",
    "product_name_clean": "name_clean",
}

RANKING_ALIASES: dict[str, str] = {
    # The JS schema for Stage 1 uses ``award_year`` / ``award_group`` /
    # ``award_category_slug`` as the sidecar carried via next_stage() (spec
    # §10). If the Stage 2 parser propagates them verbatim into the row
    # instead of renaming to the §2 short forms, alias them here.
    "award_year": "year",
    "award_group": "group",
    "award_category_slug": "category_slug",
}

BRAND_ALIASES: dict[str, str] = {
    "brand_name": "name",
    "brand_url": "url",
    "brand_total_products": "total_products",
    "brand_total_reviews": "total_reviews",
    "brand_official_site": "official_site",
    "brand_country": "country",
}
