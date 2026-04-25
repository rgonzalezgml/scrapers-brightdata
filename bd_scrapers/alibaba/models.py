"""Pydantic model for the Alibaba product output.

The 16 base fields defined in spec §3 plus the 3 supplier-reputation fields
from §3.1. All fields are emitted on every record; missing values are ``None``.

The five fields listed in backlog item G3 (``price_normalized_per_kg``,
``moq_quantity``, ``moq_unit``, ``supplier_country``, ``supplier_verified``)
are ``Optional`` with ``None`` default pending implementation.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


ProductType = Literal["chemical", "packaging"]
PriceUnit = Literal["kg", "ton", "L", "piece", "mt", "set"]


class AlibabaProduct(BaseModel):
    """Canonical product record emitted by the Alibaba scraper."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)

    product_name_clean: str = Field(..., max_length=80)
    product_name_original: str
    type: ProductType
    category: str
    price_raw: str
    price_min_usd: Optional[float] = None
    price_max_usd: Optional[float] = None
    price_unit: Optional[PriceUnit] = None
    # G3-a — normalization rule not implemented yet.
    price_normalized_per_kg: Optional[float] = None
    # G3-b / G3-c — MOQ parsing not implemented yet.
    moq_quantity: Optional[int] = None
    moq_unit: Optional[str] = None
    supplier_name: str
    # G3-d — ISO-2 mapping not implemented yet.
    supplier_country: Optional[str] = None
    # G3-e — verified badge selector not implemented yet.
    supplier_verified: Optional[bool] = None
    product_url: str
    scraped_date: str

    supplier_rating: Optional[float] = None
    supplier_reviews_count: Optional[int] = None
    supplier_response_rate: Optional[str] = None
