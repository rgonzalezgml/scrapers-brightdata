"""Tests for scrapers.alibaba.models — spec §3 shape."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from scrapers.alibaba.models import AlibabaProduct


EXPECTED_FIELDS = {
    # Spec §3 — 16 base fields
    "product_name_clean",
    "product_name_original",
    "type",
    "category",
    "price_raw",
    "price_min_usd",
    "price_max_usd",
    "price_unit",
    "price_normalized_per_kg",
    "moq_quantity",
    "moq_unit",
    "supplier_name",
    "supplier_country",
    "supplier_verified",
    "product_url",
    "scraped_date",
    # Spec §3.1 — supplier reputation
    "supplier_rating",
    "supplier_reviews_count",
    "supplier_response_rate",
}

MANDATORY_FIELDS = {
    "product_name_clean",
    "product_name_original",
    "type",
    "category",
    "price_raw",
    "supplier_name",
    "product_url",
    "scraped_date",
}


def _minimal_payload(**overrides):
    base = {
        "product_name_clean": "Glycerin Industrial Grade Liquid",
        "product_name_original": "High Quality Glycerin 99.5% Industrial Grade Liquid",
        "type": "chemical",
        "category": "Other",
        "price_raw": "$1.20-$2.50/kg",
        "price_min_usd": 1.20,
        "price_max_usd": 2.50,
        "price_unit": "kg",
        "supplier_name": "Shandong Example Chem Co., Ltd.",
        "product_url": "https://www.alibaba.com/product-detail/Glycerin_123.html",
        "scraped_date": "2026-04-21",
    }
    base.update(overrides)
    return base


class TestAlibabaProductFields:
    def test_all_spec_fields_exposed(self):
        payload = _minimal_payload()
        product = AlibabaProduct(**payload)
        dumped = product.model_dump()
        assert set(dumped.keys()) == EXPECTED_FIELDS

    def test_nullable_fields_default_to_none(self):
        payload = _minimal_payload()
        product = AlibabaProduct(**payload)
        dumped = product.model_dump()
        # G3 fields pending implementation must be present with None.
        for field in (
            "price_normalized_per_kg",
            "moq_quantity",
            "moq_unit",
            "supplier_country",
            "supplier_verified",
            "supplier_rating",
            "supplier_reviews_count",
            "supplier_response_rate",
        ):
            assert field in dumped
            assert dumped[field] is None

    def test_nulls_are_serialized_not_omitted(self):
        payload = _minimal_payload(price_min_usd=None, price_max_usd=None, price_unit=None)
        product = AlibabaProduct(**payload)
        dumped = product.model_dump()
        assert dumped["price_min_usd"] is None
        assert dumped["price_max_usd"] is None
        assert dumped["price_unit"] is None

    @pytest.mark.parametrize("missing", sorted(MANDATORY_FIELDS))
    def test_mandatory_fields_required(self, missing):
        payload = _minimal_payload()
        payload.pop(missing)
        with pytest.raises(ValidationError):
            AlibabaProduct(**payload)

    def test_type_enum_enforced(self):
        payload = _minimal_payload(type="bogus")
        with pytest.raises(ValidationError):
            AlibabaProduct(**payload)

    def test_price_unit_enum_enforced(self):
        payload = _minimal_payload(price_unit="bogus")
        with pytest.raises(ValidationError):
            AlibabaProduct(**payload)

    def test_product_name_clean_max_80(self):
        payload = _minimal_payload(product_name_clean="A" * 81)
        with pytest.raises(ValidationError):
            AlibabaProduct(**payload)

    def test_extra_fields_forbidden(self):
        payload = _minimal_payload(unexpected_field="x")
        with pytest.raises(ValidationError):
            AlibabaProduct(**payload)
