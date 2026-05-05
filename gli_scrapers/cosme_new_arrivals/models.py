"""Pydantic v2 models for the ``cosme_new_arrivals`` middleware.

- ``CosmeNewArrivalsInputs`` — public inputs validated *before* calling BrightData.
- ``NewProductRow`` — schema for each item in ``envelope["data"]``.

Rows emitted by Stage 2 (past products) carry only the 9 base fields.
Rows emitted by Stage 3 (release_date >= today) carry the 9 base fields
plus up to 22 enriched fields from the product detail page (spec §5).
``extra="allow"`` absorbs both shapes without requiring separate models.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ---- Public inputs ----------------------------------------------------------


class CosmeNewArrivalsInputs(BaseModel):
    """Public inputs accepted by ``trigger()``."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    year: int | None = Field(None, ge=2020, le=2030)
    month: int | None = Field(None, ge=1, le=12)


# ---- NewProductRow (envelope.data[N]) ---------------------------------------


class NewProductRow(BaseModel):
    """One item in ``envelope["data"]``.

    Base fields are always present. Enriched fields (Stage 3) are present
    only for products with release_date >= scrape date. Missing fields arrive
    as ``None`` — the mapper inserts NULL for absent enriched columns.
    ``extra="allow"`` forwards unknown keys without a middleware release.
    """

    model_config = ConfigDict(extra="allow")

    # --- Base fields (Stage 2, all rows) ---
    product_id: str | None = None
    product_url: str | None = None
    product_name: str | None = None
    brand_id: str | None = None
    brand_name: str | None = None
    brand_url: str | None = None
    release_date: str | None = None       # YYYY-MM-DD
    shop_url: str | None = None
    scraped_at: str | None = None         # ISO 8601 Z

    # --- Enriched fields (Stage 3, future products only) ---
    description: str | None = None
    how_to_use: str | None = None
    ingredients: str | None = None
    classification: str | None = None
    jan_code: str | None = None
    official_url: str | None = None
    manufacturer: str | None = None
    manufacturer_url: str | None = None
    category_full: str | None = None
    category_path: list[Any] | None = None
    rating_detail: float | None = None
    points: float | None = None
    review_count: int | None = None
    photo_count: int | None = None
    qa_count: int | None = None
    cat_rank: int | None = None
    cat_rank_name: str | None = None
    likes: int | None = None
    haves: int | None = None
    all_images: list[str] | None = None
    stores: list[str] | None = None
    related_products: list[Any] | None = None
    scraper_flags: list[str] | None = None


NEW_PRODUCT_FIELDS: tuple[str, ...] = tuple(NewProductRow.model_fields.keys())
NEW_PRODUCT_LIST_FIELDS: frozenset[str] = frozenset(
    {"category_path", "all_images", "stores", "related_products", "scraper_flags"}
)
