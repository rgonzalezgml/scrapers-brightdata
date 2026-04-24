"""Pydantic v2 models for the ``olive_young`` middleware.

- :class:`OliveYoungInputs` — public inputs validated *before* calling
  BrightData. Validation failure = ``INVALID_INPUTS`` (no API call made).
- :class:`RankingRow`, :class:`ProductRow`, :class:`BrandRow` — per-entity
  schemas for items in ``envelope["data"]``.

olive-young is a **multi-entity** scraper (spec §2): ``data[]`` is
heterogeneous, each row carrying an ``entity`` discriminator (``"ranking"``,
``"product"``, ``"brand"``) plus the entity-specific fields. Same shape as
``middlewares.cosme``.

Immutable §2 schema:

    ranking: ranking_id, region, cat_id, rank, prdt_no, name_en, brand_no,
             rate, is_soldout, promo, scraped_date
    product: prdt_no, url, name_clean_en, name_clean_kr, brand_no,
             category_ids, ranks, best_regions, review_count, claim_tags
    brand:   brand_no, name_en, url, total_in_rankings, avg_rank

§4-§6 of the spec catalog additional frequent fields (``site_code``,
``category_name``, ``brand_name_en``, ``thumbnail_img_url_full``,
``scraper_flags`` ...). The scraper's parser emits those extra keys;
pydantic's ``extra="allow"`` forwards them verbatim — every row is *at least*
the strict §2 keys but may carry more without a middleware release.

Naming convention (spec §2 vs §4+ prosa)
----------------------------------------

Spec §2 uses short names (``region``, ``cat_id``, ``name_en``, ``promo``,
``url``, ``total_in_rankings``, ``avg_rank``). Spec §4-§6 prosa uses longer
qualified names (``region_code``, ``category_id``, ``product_name_en``,
``promotion_name``, ``product_url``, ``brand_total_products_in_rankings``,
``brand_avg_rank``) that the scraper emits so its multi-entity output is
unambiguous on the JS side.

The middleware renames on the way out via ``*_ALIASES`` dicts so the
envelope matches §2 literally (all §2 keys present and correct). See
``client.py::_apply_aliases``.

No reinterpretation: the middleware never synthesizes values that aren't
already in the scraper's output — missing atomic fields come through as
``null``, missing list fields as ``[]`` (spec: "todos los campos del §2
presentes en cada row (null / [] explícito si faltan)").
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# ---- Public inputs ----------------------------------------------------------


class OliveYoungInputs(BaseModel):
    """Public inputs accepted by ``trigger()``.

    Agent-facing semantics (not the JS scraper's internal knobs). Translation
    to the BrightData seed happens in
    :meth:`OliveYoungClient._build_brightdata_inputs`.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    url: str | None = None
    """Listing URL forwarded to the JS scraper as ``input.url``. Defaults to
    ``DEFAULT_LISTING_URL`` when ``None``."""

    region: Literal["kr", "us"] = "kr"
    """Region forwarded to the JS scraper as ``input.region`` (and passed to
    BrightData's ``country()`` directive). Spec v5: ``"kr"`` or ``"us"``."""

    regions: Annotated[
        list[Literal["KR", "USA"]],
        Field(min_length=1, max_length=2),
    ] = ["KR", "USA"]
    """Legacy v4 field — which regions of the ranking API to crawl. Kept for
    envelope metadata only; v5 uses ``region`` (singular) instead."""

    max_products: Annotated[int, Field(ge=1, le=3000)] = 1000
    """Hard cap on emitted ``product`` rows. Spec §8 says up to ~100 detail
    enrichments via Scraping Browser per run; the raw ranking emits up to
    11×100 + 12×100 = 2300 rows which dedupe into a smaller product set.
    The middleware clips the envelope's ``data[]`` post-download — the
    scraper is NOT reconfigured."""

    max_brand_visits: Annotated[int, Field(ge=0, le=100)] = 20
    """Cap on brand-page visits (spec §8: top-20 brands by
    ``brand_total_products_in_rankings``). Does NOT enforce the cap in the
    scraper — used to build the brand whitelist emitted in the seed."""

    include_rankings: bool = True
    """If ``False``, drop every ``ranking`` row from the envelope's ``data[]``.
    Does NOT reduce the scraper's work — only affects post-download filtering.
    """

    include_brands: bool = True
    """If ``False``, drop every ``brand`` row from the envelope's ``data[]``."""

    include_products: bool = True
    """If ``False``, drop every ``product`` row from the envelope's ``data[]``.
    Useful when the agent only wants the ranking signal (rank + prdt_no),
    not the enriched detail data."""

    categories: list[str] | None = None
    """Optional whitelist of ranking API ``category-id`` values (spec §9:
    e.g. ``1000000001`` All, ``1000000008`` Skincare, ``1000000031`` Makeup).
    If ``None`` the JS scraper discovers categories from
    ``/v1/pages/ranking/sales/categories``. Primarily useful for debug runs.
    """

    mode: Literal["incremental", "full-refresh"] = "incremental"
    """``incremental`` respects the dedup / 24h cache heuristics spec §8
    describes; ``full-refresh`` requests a cold run. The JS scraper does not
    differentiate today — this flag is reserved for the agents repo to key
    its own cache TTL. The middleware forwards it into ``envelope["inputs"]``
    so downstream can decide."""


# ---- Shared row base --------------------------------------------------------

# Discriminator literal used on every envelope data row.
Entity = Literal["ranking", "product", "brand"]


# ---- Ranking (spec §2 + §4) -------------------------------------------------


class RankingRow(BaseModel):
    """One ranking row in ``envelope["data"]`` (spec §2 / §4).

    §2 strict keys (short names, renamed on the wire to match §2 literally):

        ranking_id, region, cat_id, rank, prdt_no, name_en, brand_no, rate,
        is_soldout, promo, scraped_date

    §4 additional frequent keys (``null`` / ``[]`` when missing):

        site_code, category_name, product_url, product_name_kr,
        brand_name_en, brand_name_kr, has_coupon, has_gift,
        thumbnail_img_url_raw, thumbnail_img_url_full, scraper_flags
    """

    model_config = ConfigDict(extra="allow")

    entity: Literal["ranking"] = "ranking"

    # ---- §2 strict --------------------------------------------------------
    ranking_id: str | None = None
    region: str | None = None
    cat_id: str | None = None
    rank: int | None = None
    prdt_no: str | None = None
    name_en: str | None = None
    brand_no: str | None = None
    rate: float | None = None
    is_soldout: bool | None = None
    promo: str | None = None
    scraped_date: str | None = None

    # ---- §4 additional ----------------------------------------------------
    site_code: str | None = None
    category_name: str | None = None
    product_url: str | None = None
    product_name_kr: str | None = None
    brand_name_en: str | None = None
    brand_name_kr: str | None = None
    has_coupon: bool | None = None
    has_gift: bool | None = None
    thumbnail_img_url_raw: str | None = None
    thumbnail_img_url_full: str | None = None
    scraper_flags: list[str] = Field(default_factory=list)


# ---- Product (spec §2 + §5) -------------------------------------------------


class ProductRow(BaseModel):
    """One product row (spec §2 / §5).

    §2 strict keys:

        prdt_no, url, name_clean_en, name_clean_kr, brand_no, category_ids,
        ranks, best_regions, review_count, claim_tags

    §5 additional keys (null/[] when missing):

        product_name_en, product_name_kr, brand_name_en, brand_name_kr,
        rate, is_soldout, thumbnail_img_url_full, category_names, new_yn,
        best_yn, flash_yn, scraped_date, scraper_flags
    """

    model_config = ConfigDict(extra="allow")

    entity: Literal["product"] = "product"

    # ---- §2 strict --------------------------------------------------------
    prdt_no: str | None = None
    url: str | None = None
    name_clean_en: str | None = None
    name_clean_kr: str | None = None
    brand_no: str | None = None
    category_ids: list[str] = Field(default_factory=list)
    ranks: list[int] = Field(default_factory=list)
    best_regions: list[str] = Field(default_factory=list)
    review_count: int | None = None
    claim_tags: list[str] = Field(default_factory=list)

    # ---- §5 additional ----------------------------------------------------
    product_name_en: str | None = None
    product_name_kr: str | None = None
    brand_name_en: str | None = None
    brand_name_kr: str | None = None
    rate: float | None = None
    is_soldout: bool | None = None
    thumbnail_img_url_full: str | None = None
    category_names: list[str] = Field(default_factory=list)
    new_yn: bool | None = None
    best_yn: bool | None = None
    flash_yn: bool | None = None
    scraped_date: str | None = None
    scraper_flags: list[str] = Field(default_factory=list)


# ---- Brand (spec §2 + §6) ---------------------------------------------------


class BrandRow(BaseModel):
    """One brand row (spec §2 / §6).

    §2 strict keys:

        brand_no, name_en, url, total_in_rankings, avg_rank

    §6 additional keys:

        name_kr, brand_og_image, scraped_date, scraper_flags
    """

    model_config = ConfigDict(extra="allow")

    entity: Literal["brand"] = "brand"

    # ---- §2 strict --------------------------------------------------------
    brand_no: str | None = None
    name_en: str | None = None
    url: str | None = None
    total_in_rankings: int | None = None
    avg_rank: float | None = None

    # ---- §6 additional ----------------------------------------------------
    name_kr: str | None = None
    brand_og_image: str | None = None
    scraped_date: str | None = None
    scraper_flags: list[str] = Field(default_factory=list)


# ---- Field catalog (used by the client to coerce rows) ----------------------

RANKING_FIELDS: tuple[str, ...] = tuple(RankingRow.model_fields.keys())
PRODUCT_FIELDS: tuple[str, ...] = tuple(ProductRow.model_fields.keys())
BRAND_FIELDS: tuple[str, ...] = tuple(BrandRow.model_fields.keys())

# Fields that must be a list on the wire. Keep in sync with
# ``Field(default_factory=list)`` above.
RANKING_LIST_FIELDS: frozenset[str] = frozenset({"scraper_flags"})
PRODUCT_LIST_FIELDS: frozenset[str] = frozenset(
    {
        "category_ids",
        "ranks",
        "best_regions",
        "claim_tags",
        "category_names",
        "scraper_flags",
    }
)
BRAND_LIST_FIELDS: frozenset[str] = frozenset({"scraper_flags"})

# Map from the JS parser's key name → the middleware's wire name. Spec §2
# uses short names (``region``, ``cat_id``, ``name_en``, ``promo``, ``url``,
# ``total_in_rankings``, ``avg_rank``) but the scraper emits long qualified
# names (``region_code``, ``category_id``, ``product_name_en``,
# ``promotion_name``, ``product_url``, ``brand_total_products_in_rankings``,
# ``brand_avg_rank``) to keep its multi-entity output unambiguous.
#
# The middleware renames on the way out so the envelope matches §2 literally.
# New entries here = new scraper field we want to alias; never invent values,
# only rename keys that already exist in the raw row.
RANKING_ALIASES: dict[str, str] = {
    # §4 prosa → §2 short name
    "region_code": "region",
    "category_id": "cat_id",
    "product_name_en": "name_en",
    "promotion_name": "promo",
    # product_url is already in §4 additional, no rename needed.
}

PRODUCT_ALIASES: dict[str, str] = {
    # §5 prosa → §2 short name. The scraper uses ``product_url`` /
    # ``product_name_clean_en`` / ``product_name_clean_kr``; §2 uses ``url`` /
    # ``name_clean_en`` / ``name_clean_kr``.
    "product_url": "url",
    "product_name_clean_en": "name_clean_en",
    "product_name_clean_kr": "name_clean_kr",
}

BRAND_ALIASES: dict[str, str] = {
    # §6 prosa → §2 short name.
    "brand_name_en": "name_en",
    "brand_name_kr": "name_kr",
    "brand_url": "url",
    "brand_total_products_in_rankings": "total_in_rankings",
    "brand_avg_rank": "avg_rank",
}
