"""Data transformation helpers for the Alibaba scraper.

Ports ``clean_name``, ``parse_price``, ``classify`` and the skip rules from
``scripts/clean_data.py``. Keeps the public API narrow and side-effect-free so
each rule is independently testable per spec §4.

Working taxonomy (backlog item G1): prompt v2 English labels plus ``Other`` as
fallback. The extended taxonomy emitted by ``scripts/clean_data.py`` is left
out on purpose until G1 is resolved.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Optional, Tuple


EXCHANGE_RATES: dict[str, float] = {
    "USD": 1.0, "CHF": 1.11, "EUR": 1.08, "GBP": 1.27,
    "CNY": 0.14, "HKD": 0.13, "SGD": 0.74, "INR": 0.012,
    "JPY": 0.0067, "KRW": 0.00075, "MXN": 0.058, "MYR": 0.22,
    "NZD": 0.61, "IDR": 0.000061, "AUD": 0.65, "BRL": 0.19,
    "CAD": 0.73, "THB": 0.028,
}

CURRENCY_SYMBOLS: list[tuple[str, str]] = [
    ("NZ$", "NZD"), ("CA$", "CAD"), ("A$", "AUD"), ("US$", "USD"),
    ("R$", "BRL"), ("B/.", "USD"), ("RM", "MYR"), ("Rp", "IDR"),
    ("€", "EUR"), ("£", "GBP"), ("¥", "JPY"),
    ("₹", "INR"), ("₩", "KRW"), ("฿", "THB"),
]

REMOVE_PATTERNS: list[str] = [
    r"\b(high quality|best price|hot sale|factory direct|free sample|top quality)\b",
    r"\b(oem|odm|customized|wholesale|bulk)\b",
    r"\b(iso[ -]?\d+|ce|gmp|fda|reach|rohs|kosher|halal)[ -]?(certified?|approved?|standard)?\b",
    r"\b(manufacturer|factory|supplier|exporter|producer)\b",
    r"\b(best selling|best-selling|top selling|popular|professional)\b",
    r"\b(direktvertrieb|vom hersteller|meistverkaufter|fabrik)\b",
    r"\b(qualit|zertifiziert|reinheit)\b",
    r"\b(calidad|certificado|fabricante|proveedor|directo)\b",
    r"\b(mejor precio|venta directa)\b",
    r"\b(jiahua|shandong|hebei|guangzhou|shanghai|beijing)\b",
]

MACHINERY_KW: list[str] = [
    "machine", "equipment", "pump", "motor", "meter", "sensor",
    "device", "tool", "instrument", "apparatus", "system",
    "maquina", "equipo", "bomba", "herramienta",
    "maschine", "gerat", "anlage",
]

# Prompt v2 working taxonomy. G1 backlog tracks unification with clean_data.py
# and detail_v2.js.
PACKAGING_KEYWORDS: list[str] = [
    "drum", "barrel", "container", "bag", "bottle", "tank",
    "ibc", "packaging", "package", "sack",
]

PACKAGING_SUBCATEGORIES: list[tuple[str, list[str]]] = [
    ("Packaging_Drum", ["drum", "barrel"]),
    ("Packaging_Bag", ["bag", "sack"]),
    ("Packaging_Container", ["container", "ibc", "tank", "bottle"]),
]

CHEMICAL_CATEGORIES: list[tuple[str, list[str]]] = [
    ("Alkali", ["sodium hydroxide", "caustic soda", "potassium hydroxide", "naoh", "koh"]),
    ("Acid", ["hydrochloric", "sulfuric", "nitric", "acetic", "acid", "hcl", "h2so4", "citric"]),
    ("Surfactant", ["sles", "sls", "laureth", "lauryl", "surfactant", "detergent"]),
    ("Solvent", ["ethanol", "methanol", "acetone", "isopropanol", "ipa", "solvent"]),
    ("Preservative", ["sodium benzoate", "potassium sorbate", "preservative", "benzoate"]),
    ("Fragrance", ["fragrance", "perfume", "aroma", "essential oil"]),
]

_PRICE_UNITS: list[tuple[str, str]] = [
    ("/kg", "kg"),
    ("/ton", "ton"),
    ("/mt", "mt"),
    ("/l", "L"),
    ("/piece", "piece"),
    ("/set", "set"),
]

_ASCII_LATIN_RE = re.compile(r"[A-Za-z0-9]")


def normalize(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text.lower())
        if unicodedata.category(c) != "Mn"
    )


def name_from_url(url: str) -> str:
    """Spec §4.5 — recover product name from product-detail URL slug."""

    if not url:
        return ""
    try:
        match = re.search(r"/product-detail/([^_]+)_", url)
        if not match:
            match = re.search(r"/product-detail/(.+?)[\?_]", url)
        if match:
            slug = match.group(1)
            return re.sub(r"\s+", " ", slug.replace("-", " ")).strip()
    except re.error:
        return ""
    return ""


def clean_name(raw: Optional[str]) -> str:
    """Spec §4.2 — strip marketing/cert/city noise and truncate to 80 chars."""

    if not raw:
        return ""
    name = raw.strip()
    for pattern in REMOVE_PATTERNS:
        name = re.sub(pattern, "", name, flags=re.IGNORECASE)
    name = re.sub(r"\([^)]{20,}\)", "", name)
    name = re.sub(r"[|/\\&]+", " ", name)
    name = re.sub(r"\s{2,}", " ", name)
    name = name.strip(" -,.")
    if len(name) > 80:
        name = name[:80].rsplit(" ", 1)[0]
    return name.strip()


def parse_price(
    price_raw: Optional[str],
) -> Tuple[Optional[float], Optional[float], str, Optional[str]]:
    """Spec §4.3 — return (min_usd, max_usd, currency, unit).

    ``currency`` is always ``"USD"`` when a numeric value is returned, because
    ``min``/``max`` are already converted via ``EXCHANGE_RATES``.
    """

    if not price_raw:
        return None, None, "USD", None
    s = str(price_raw).strip()
    if not s or s in ("None", "[]", "null"):
        return None, None, "USD", None

    currency = "USD"
    matched_symbol = False
    for symbol, code in CURRENCY_SYMBOLS:
        if symbol in s:
            currency = code
            matched_symbol = True
            break
    if not matched_symbol:
        upper = s.upper()
        for code in EXCHANGE_RATES:
            if code in upper:
                currency = code
                break

    unit: Optional[str] = None
    lowered = s.lower()
    for token, canonical in _PRICE_UNITS:
        if token in lowered:
            unit = canonical
            break

    nums = [
        float(n)
        for n in re.findall(r"\d+\.?\d*", s.replace(",", ""))
        if n
    ]
    if not nums:
        return None, None, currency, unit

    rate = EXCHANGE_RATES.get(currency, 1.0)
    return (
        round(min(nums) * rate, 4),
        round(max(nums) * rate, 4),
        "USD",
        unit,
    )


def normalize_price_per_kg(
    price_min_usd: Optional[float],
    price_unit: Optional[str],
) -> Optional[float]:
    """Spec §4.3 rule 13 — per-kg normalization.

    Only ``ton`` and ``mt`` have an explicit factor. Other units return ``None``
    until their rule is defined (see backlog G3-a).
    """

    if price_min_usd is None or price_unit is None:
        return None
    if price_unit == "kg":
        return round(price_min_usd, 4)
    if price_unit in ("ton", "mt"):
        return round(price_min_usd / 1000.0, 6)
    return None


def is_machinery(name: str) -> bool:
    """Spec §4.1 rule 3."""

    n = normalize(name)
    return any(kw in n for kw in MACHINERY_KW)


def is_chinese_only(text: Optional[str]) -> bool:
    """Spec §4.1 rule 4 — title with no ASCII/Latin letters or digits."""

    if not text:
        return False
    return _ASCII_LATIN_RE.search(text) is None


def is_empty_price(price_raw: Optional[str]) -> bool:
    """Spec §4.1 rule 2."""

    if price_raw is None:
        return True
    s = str(price_raw).strip()
    return s in ("", "None", "[]", "null")


def classify(name: str) -> Tuple[str, str]:
    """Spec §4.4 — (type, category) under the prompt-v2 working taxonomy.

    Backlog G1: align with clean_data.py and detail_v2.js.
    """

    n = name.lower()
    if any(k in n for k in PACKAGING_KEYWORDS):
        for category, keywords in PACKAGING_SUBCATEGORIES:
            if any(k in n for k in keywords):
                return "packaging", category
        return "packaging", "Other"
    for category, keywords in CHEMICAL_CATEGORIES:
        if any(k in n for k in keywords):
            return "chemical", category
    return "chemical", "Other"


def resolve_name(raw_name: Optional[str], product_url: Optional[str]) -> Tuple[str, str]:
    """Return (cleaned, original). Original falls back to URL-derived slug."""

    original = (raw_name or "").strip()
    if not original and product_url:
        original = name_from_url(product_url)
    cleaned = clean_name(original)
    return cleaned, original
