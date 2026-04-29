"""Pydantic v2 models for the ``cosme_ranking_products`` middleware.

- ``CosmeRankingInputs`` — public inputs validated *before* calling BrightData.
  Validation failure = ``INVALID_INPUTS`` (no API call made).
- ``RankingEntry`` — schema for each item in ``envelope["data"]``. Mirrors the
  44 fields emitted by ``bd_scrapers/cosme-ranking-products/sc_code/`` per row.

The middleware is a thin wrapper: we validate the *shape* of each row but
never reinterpret semantics — if BrightData omits a field, we surface it as
``null`` (or empty list for list-typed fields).

Note: ``product_url`` maps to ``input.prod_url`` in the parser (Stage 1 sends
the URL as ``input.url`` — known mismatch, field will arrive as null until
the Stage 1 interaction code is fixed).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


# ---- Public inputs ----------------------------------------------------------


class CosmeRankingInputs(BaseModel):
    """Public inputs accepted by ``trigger()``.

    These are the agent-facing knobs. They are translated to the JS scraper's
    runtime inputs (``page``, ``max_pages``, ``url``) inside
    ``CosmeRankingClient._build_brightdata_inputs``.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    max_pages: int = Field(default=10, ge=1, le=10)
    """Number of listing pages to scrape (10 products per page). Max 10 = 100
    products (the full weekly ranking). The scraper JS hard-caps at 10 pages."""

    mode: Literal["incremental", "full-refresh"] = "incremental"
    """``incremental`` is the default for weekly runs. ``full-refresh`` is
    semantically identical for this scraper (the ranking is always the current
    week's data) but kept for parity with other middlewares."""


# ---- RankingEntry (envelope.data[N]) ----------------------------------------

# 29 fields emitted by sc_code/ per row. Order mirrors the parser's output.


class RankingEntry(BaseModel):
    """One item in ``envelope["data"]``. Schema fixed by the scraper JS output.

    Pydantic allows ``None`` for every scalar field: the scraper emits explicit
    ``null`` rather than dropping the key when data is unavailable. List fields
    default to empty list, never ``None``.
    """

    # ``extra="allow"`` — forward any extra keys the JS scraper adds in future
    # versions without requiring a middleware release.
    model_config = ConfigDict(extra="allow")

    # --- Ranking position ---
    rank: int | None = None
    rank_change: str | None = None

    # --- Product identity ---
    product_id: str | None = None
    product_name: str | None = None
    product_name_jp: str | None = None
    product_url: str | None = None          # null hasta fix Stage1→Stage2 (input.prod_url)
    product_img: str | None = None

    # --- Brand ---
    brand_id: str | None = None
    brand_name: str | None = None
    brand_name_jp: str | None = None
    brand_url: str | None = None
    manufacturer: str | None = None
    manufacturer_url: str | None = None

    # --- Category ---
    category: str | None = None
    category_url: str | None = None
    category_full: str | None = None
    category_path: list[dict[str, str]] = Field(default_factory=list)

    # --- Price ---
    price_text: str | None = None
    price_yen: float | None = None
    size: str | None = None
    is_open_price: bool | None = None
    tax_included: bool | None = None

    # --- Ratings & ranking metrics ---
    rating: float | None = None
    rating_detail: float | None = None
    points: float | None = None
    cat_rank: int | None = None
    cat_rank_name: str | None = None
    ranking_in: list[str] = Field(default_factory=list)

    # --- Community metrics ---
    review_count: int | None = None
    photo_count: int | None = None
    qa_count: int | None = None
    likes: int | None = None
    haves: int | None = None

    # --- Release ---
    release_date: str | None = None
    is_best_cosme: bool | None = None
    is_new: bool | None = None

    # --- Product detail (Stage 2) ---
    description: str | None = None
    how_to_use: str | None = None
    ingredients: str | None = None
    classification: str | None = None
    jan_code: str | None = None
    official_url: str | None = None
    all_images: list[str] = Field(default_factory=list)
    shop_url: str | None = None
    stores: list[str] = Field(default_factory=list)
    related_products: list[dict[str, str]] = Field(default_factory=list)

    # --- Ranking period ---
    period_start: str | None = None
    period_end: str | None = None
    total_products: int | None = None

    # --- Scraper metadata ---
    scraped_at: str | None = None
    source: str | None = None
    country: str | None = None
    ranking_by: str | None = None
    input: dict[str, Any] | None = None


# Canonical ordered tuple of field names — used by the client to guarantee
# all keys are emitted on every row (spec: "todas las claves presentes con
# null explicito cuando falten").
RANKING_ENTRY_FIELDS: tuple[str, ...] = tuple(RankingEntry.model_fields.keys())

# Fields that must be a list (never null) on the wire.
RANKING_LIST_FIELDS: frozenset[str] = frozenset({
    "all_images", "category_path", "ranking_in", "stores", "related_products",
})
