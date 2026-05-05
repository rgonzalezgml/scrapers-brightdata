"""Pydantic v2 models for the ``olive_young_new_arrivals`` middleware.

- :class:`OliveYoungNewArrivalsInputs` — public inputs validated *before*
  calling BrightData. No inputs required.
- :class:`NewArrivalRow` — per-entity schema for items in
  ``envelope["data"]``.

Field catalog (actual keys emitted by the BrightData scraper):

    Producto: prdt_no, url, product_name_en, product_name_kr, image_url
    Marca: brand_no, brand_name_en, brand_name_kr, brand_url, brand_image_url
    Precio: sale_amt, nrml_amt, discount_rate
    Categoría: category, categories, category_1, category_2, category_3
    Métricas: rating, review_count
    Contenido: why_we_love_it, how_to_use, extra_images
    Flags: is_new, is_best, is_soldout, is_flash, has_coupon, has_gift
    Metadata: corner_name, scraped_date

Note: ``category_1/2/3`` are not emitted by the scraper directly —
they are derived from the ``categories`` array in ``_expand_categories``
before the mapper processes the row.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

# ---- Public inputs ----------------------------------------------------------


class OliveYoungNewArrivalsInputs(BaseModel):
    """Public inputs accepted by ``trigger()``.

    The scraper fetches the full new-arrivals catalogue without any
    parameterisation — no inputs are required.
    """

    model_config = ConfigDict(extra="forbid")


# ---- new_arrival row --------------------------------------------------------


class NewArrivalRow(BaseModel):
    """One new_arrival row from the BrightData scraper."""

    model_config = ConfigDict(extra="allow")

    # Producto
    prdt_no: str | None = None
    url: str | None = None
    product_name_en: str | None = None
    product_name_kr: str | None = None
    image_url: str | None = None

    # Marca
    brand_no: str | None = None
    brand_name_en: str | None = None
    brand_name_kr: str | None = None
    brand_url: str | None = None
    brand_image_url: str | None = None

    # Precio (USD decimal strings, e.g. "15.39")
    sale_amt: str | None = None
    nrml_amt: str | None = None
    discount_rate: str | None = None

    # Categoría
    category: str | None = None
    categories: list | None = None

    # Métricas
    rating: float | None = None
    review_count: int | None = None

    # Contenido enriquecido
    why_we_love_it: str | None = None
    how_to_use: str | None = None
    extra_images: str | None = None

    # Flags
    is_new: bool | None = None
    is_best: bool | None = None
    is_soldout: bool | None = None
    is_flash: bool | None = None
    has_coupon: bool | None = None
    has_gift: bool | None = None

    # Metadata
    corner_name: str | None = None
    scraped_date: str | None = None


# ---- Field catalog (used by the client to coerce rows) ----------------------

NEW_ARRIVAL_FIELDS: tuple[str, ...] = tuple(NewArrivalRow.model_fields.keys())

# No list fields to serialize as JSON strings (categories is handled via
# _expand_categories before it reaches the mapper).
NEW_ARRIVAL_LIST_FIELDS: frozenset[str] = frozenset()
