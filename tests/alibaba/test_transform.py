"""Tests for scrapers.alibaba.transform — spec §4 rules."""

from __future__ import annotations

import pytest

from scrapers.alibaba.transform import (
    classify,
    clean_name,
    is_chinese_only,
    is_empty_price,
    is_machinery,
    name_from_url,
    normalize_price_per_kg,
    parse_price,
    resolve_name,
)


# ---------------------------------------------------------------------------
# §4.1 — skip rules
# ---------------------------------------------------------------------------


class TestSkipRules:
    """Skip rules 1–4 from spec §4.1."""

    def test_skip_empty_name(self):
        # Rule 1: clean_name on empty / only-noise input yields "".
        assert clean_name("") == ""
        assert clean_name(None) == ""
        assert clean_name("   ") == ""

    @pytest.mark.parametrize("value", [None, "", "None", "null", "[]", "   "])
    def test_skip_missing_price(self, value):
        # Rule 2: these sentinel values count as "no price".
        assert is_empty_price(value) is True

    def test_non_empty_price_not_skipped(self):
        assert is_empty_price("$1.20/kg") is False

    @pytest.mark.parametrize(
        "name",
        [
            "Industrial water pump stainless",
            "Flow meter sensor",
            "Bomba industrial para quimicos",
            "Dosiermaschine fur fabrik",
        ],
    )
    def test_skip_machinery_keywords(self, name):
        # Rule 3: machinery/equipment terms trigger skip.
        assert is_machinery(name) is True

    def test_non_machinery_name(self):
        assert is_machinery("Glycerin Industrial Grade Liquid") is False

    def test_chinese_only_title_detected(self):
        # Rule 4: no ASCII letters or digits -> chinese-only.
        assert is_chinese_only("工业级甘油") is True
        assert is_chinese_only("甘油 99.5") is False
        assert is_chinese_only("Glycerin") is False
        assert is_chinese_only("") is False


# ---------------------------------------------------------------------------
# §4.2 — clean_name
# ---------------------------------------------------------------------------


class TestCleanName:
    def test_removes_marketing_and_certs(self):
        raw = "High Quality Glycerin 99.5% FDA Certified Factory Direct"
        cleaned = clean_name(raw)
        assert "high quality" not in cleaned.lower()
        assert "factory direct" not in cleaned.lower()
        assert "glycerin" in cleaned.lower()

    def test_truncates_to_80_chars_on_word_boundary(self):
        # Build a name well over 80 characters using non-noise tokens.
        raw = " ".join(["Glycerin"] * 20)  # > 80 chars
        cleaned = clean_name(raw)
        assert len(cleaned) <= 80
        # Truncation must fall on a space (no partial word at the end).
        assert not cleaned.endswith("Glyceri")

    def test_collapses_separators_and_whitespace(self):
        raw = "Sodium  Hydroxide  |  99%  /  NaOH"
        cleaned = clean_name(raw)
        assert "  " not in cleaned
        assert "|" not in cleaned

    def test_removes_long_parentheticals(self):
        raw = "Glycerin Liquid (this is a very long marketing parenthetical)"
        cleaned = clean_name(raw)
        assert "(" not in cleaned


# ---------------------------------------------------------------------------
# §4.3 — parse_price + normalize_price_per_kg
# ---------------------------------------------------------------------------


class TestParsePrice:
    def test_range_usd_per_kg(self):
        # Spec §4.3: "$1.20-$2.50/kg" -> (1.20, 2.50, "USD", "kg").
        pmin, pmax, cur, unit = parse_price("$1.20-$2.50/kg")
        assert pmin == pytest.approx(1.20)
        assert pmax == pytest.approx(2.50)
        assert cur == "USD"
        assert unit == "kg"

    def test_empty_price_returns_nones(self):
        pmin, pmax, cur, unit = parse_price("")
        assert pmin is None
        assert pmax is None
        assert unit is None

    def test_none_sentinel_returns_nones(self):
        pmin, _, _, _ = parse_price("None")
        assert pmin is None

    def test_cny_converted_to_usd(self):
        pmin, pmax, cur, unit = parse_price("CNY 10-20/kg")
        # 10 * 0.14 = 1.4 ; 20 * 0.14 = 2.8
        assert pmin == pytest.approx(1.4, abs=1e-4)
        assert pmax == pytest.approx(2.8, abs=1e-4)
        assert cur == "USD"
        assert unit == "kg"

    def test_ton_unit_normalized_per_kg(self):
        # Spec §4.3 rule 13: ton -> divide by 1000 for per-kg.
        pmin, _, _, unit = parse_price("$500-$800/ton")
        assert unit == "ton"
        per_kg = normalize_price_per_kg(pmin, unit)
        assert per_kg == pytest.approx(0.5, abs=1e-4)

    def test_mt_unit_normalized_per_kg(self):
        per_kg = normalize_price_per_kg(1000.0, "mt")
        assert per_kg == pytest.approx(1.0, abs=1e-4)

    def test_piece_unit_not_normalized(self):
        assert normalize_price_per_kg(5.0, "piece") is None


# ---------------------------------------------------------------------------
# §4.4 — classify
# ---------------------------------------------------------------------------


class TestClassify:
    @pytest.mark.parametrize(
        "name,expected",
        [
            ("Sodium Hydroxide 99%", ("chemical", "Alkali")),
            ("Hydrochloric Acid Industrial", ("chemical", "Acid")),
            ("SLES 70% Surfactant", ("chemical", "Surfactant")),
            ("Industrial Ethanol Solvent", ("chemical", "Solvent")),
            ("Sodium Benzoate Preservative", ("chemical", "Preservative")),
            ("Rose Fragrance Oil", ("chemical", "Fragrance")),
            ("Random Chemical XYZ", ("chemical", "Other")),
        ],
    )
    def test_chemical_categories(self, name, expected):
        assert classify(name) == expected

    @pytest.mark.parametrize(
        "name,expected_category",
        [
            ("Steel Drum 200L", "Packaging_Drum"),
            ("HDPE Barrel Industrial", "Packaging_Drum"),
            ("PP Woven Bag", "Packaging_Bag"),
            ("Jumbo Sack", "Packaging_Bag"),
            ("IBC Container 1000L", "Packaging_Container"),
            ("Chemical Tank 500L", "Packaging_Container"),
        ],
    )
    def test_packaging_subcategories(self, name, expected_category):
        product_type, category = classify(name)
        assert product_type == "packaging"
        assert category == expected_category


# ---------------------------------------------------------------------------
# §4.5 — name_from_url + resolve_name
# ---------------------------------------------------------------------------


class TestNameFromUrl:
    def test_extracts_slug_before_underscore(self):
        url = "https://www.alibaba.com/product-detail/Glycerin-99-5-Industrial_123456.html"
        assert name_from_url(url) == "Glycerin 99 5 Industrial"

    def test_returns_empty_for_unrelated_url(self):
        assert name_from_url("https://example.com/") == ""

    def test_returns_empty_for_empty_url(self):
        assert name_from_url("") == ""

    def test_resolve_name_falls_back_to_url(self):
        cleaned, original = resolve_name(
            "",
            "https://www.alibaba.com/product-detail/Glycerin-99-5-Industrial_123456.html",
        )
        assert "Glycerin" in original
        assert "Glycerin" in cleaned
