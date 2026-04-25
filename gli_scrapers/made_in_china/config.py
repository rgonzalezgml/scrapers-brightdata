"""Static configuration for the ``made_in_china`` middleware.

Mirrors ``gli_scrapers/cosme/config.py`` and ``gli_scrapers/cosmetics_design/config.py``.
All secret/environment values are resolved lazily via env vars (see
``BaseScraperClient._ensure_credentials``). This module only exposes constant
defaults — never read ``os.getenv`` at import time for required secrets, so
downstream code (tests, type checkers) can import without crashing.

Dual-mode resolution
--------------------

made-in-china can run against either BrightData transport:

    - **Datasets v3** (modern, ``gd_...``) — the target once the scraper is
      published to Scraper Studio in the dashboard.
    - **DCA legacy** (``c_.../j_...``) — if the scraper ships under the
      legacy Data Collectors Archive API.

The middleware picks the mode based on which env var the user has populated.
See ``docs/fase3/middleware-dual-mode.md`` §3.
"""

from __future__ import annotations

import os
from typing import Literal

# ---- BrightData --------------------------------------------------------------

# Source name as it appears in the envelope (matches scrapers/<name>/ folder
# name, which uses a hyphen — spec §1 of genomma lab "campo site fijo
# made-in-china").
SOURCE_NAME: str = "made-in-china"

# Env var that holds the BrightData **dataset id** for this scraper (v3 mode).
DATASET_ID_ENV_VAR: str = "BRIGHTDATA_DATASET_ID_MADE_IN_CHINA"

# Env var that holds the BrightData **collector id** for this scraper (DCA
# legacy mode). Only read when the user has not populated the v3 env var.
COLLECTOR_ID_ENV_VAR: str = "BRIGHTDATA_COLLECTOR_ID_MADE_IN_CHINA"


def get_dataset_id() -> str | None:
    """Resolve the BrightData dataset id (v3) from the environment.

    Returns ``None`` if the env var is unset; the client surfaces this as an
    ``INVALID_INPUTS`` error at trigger time (never at import time).
    """
    return os.getenv(DATASET_ID_ENV_VAR)


def get_collector_id() -> str | None:
    """Resolve the BrightData collector id (DCA legacy) from the environment.

    Returns ``None`` if the env var is unset.
    """
    return os.getenv(COLLECTOR_ID_ENV_VAR)


ApiMode = Literal["v3", "dca"]


def resolve_mode_and_id() -> tuple[ApiMode | None, str | None]:
    """Decide ``(api_mode, resource_id)`` based on the populated env vars.

    Precedence (per dual-mode spec §3.3):

        1. If ``DATASET_ID`` is set → ``("v3", dataset_id)``. v3 wins over DCA
           when both are populated — that means the user migrated to Studio
           and the DCA leftover should be ignored.
        2. Else if ``COLLECTOR_ID`` is set → ``("dca", collector_id)``.
        3. Else → ``(None, None)`` — let the client raise ``INVALID_INPUTS``
           at trigger time with a hint that names both env vars.

    No prefix validation on the resource id (treated as an opaque string).
    """
    ds = get_dataset_id()
    col = get_collector_id()
    if ds:
        return ("v3", ds)
    if col:
        return ("dca", col)
    return (None, None)


# Human-readable hint used in the INVALID_INPUTS error message when neither
# env var is populated (surfaced via ``BaseScraperClient.CREDENTIAL_HINT``).
CREDENTIAL_HINT: str = (
    "Set one of:\n"
    f"  {DATASET_ID_ENV_VAR}   (for Datasets v3, gd_...)\n"
    f"  {COLLECTOR_ID_ENV_VAR} (for DCA legacy, c_...)"
)

# ---- Scraper-side defaults ---------------------------------------------------

# Default seed URLs — via-2 catalog (spec §9 v6 / §12).
# 12 subcategorías verificadas con HTTP 200 el 2026-04-24, alineadas con
# las familias de alibaba e indiamart para comparación cross-source.
DEFAULT_SEED_URLS: tuple[str, ...] = (
    # Químicos industriales (8)
    "https://www.made-in-china.com/Chemicals-Catalog/Alkali.html",
    "https://www.made-in-china.com/Chemicals-Catalog/Acid.html",
    "https://www.made-in-china.com/Chemicals-Catalog/Organic-Intermediate.html",
    "https://www.made-in-china.com/Chemicals-Catalog/Ester-Derivative.html",
    "https://www.made-in-china.com/Chemicals-Catalog/Essential-Oil-Balsam-Fine-Chemicals.html",
    "https://www.made-in-china.com/Chemicals-Catalog/Surface-Disposal-Agent.html",
    "https://www.made-in-china.com/Chemicals-Catalog/Fungicide-Bactericide.html",
    "https://www.made-in-china.com/Chemicals-Catalog/Inorganic-Chemicals.html",
    # Empaque industrial (4)
    "https://www.made-in-china.com/Packaging-Printing-Catalog/Packaging-Materials.html",
    "https://www.made-in-china.com/Packaging-Printing-Catalog/Stretch-Film.html",
    "https://www.made-in-china.com/Packaging-Printing-Catalog/Packaging-Barrels-Buckets.html",
    "https://www.made-in-china.com/Packaging-Printing-Catalog/Woven-Bag.html",
)

# Kept for backwards-compat with code that references DEFAULT_LISTING_URL.
DEFAULT_LISTING_URL: str = DEFAULT_SEED_URLS[0]

# Default ``max_pages`` forwarded to the JS scraper's v5 parallel pagination
# logic. Per spec §9: ``-1`` means process up to ``total_pages`` derived from
# the ``.page-total`` widget of the listing; ``N > 0`` processes
# ``min(N, total_pages)``; ``0`` is normalized to ``-1`` by the interaction
# code. Spec §9 defaults are "3 paginas c/u" but are override-able at runtime.
DEFAULT_MAX_PAGES: int = 3

# Hard caps on middleware-side row clipping (spec §9: "hasta 800 unique
# PRODUCT_ID detail; hasta 200 supplier home").
MAX_PRODUCTS_HARD_CAP: int = 800
MAX_SUPPLIERS_HARD_CAP: int = 200

# Hard cap on the number of seed URLs the caller may request per trigger. Each
# seed fans out to ``total_pages`` of listing + N product/supplier details —
# sending thousands of seeds at once saturates the BrightData budget (spec §9:
# 2000 requests / 90 min). Cap chosen to give headroom for the 12 slugs listed
# in spec §9 default (5 keywords + 8 chem subcats + 4 packaging subcats).
MAX_SEED_URLS: int = 50

# ---- Country-to-ISO2 mapping (spec §4 / §6 / errors.md E3) ------------------

# The JS vendor v0 emitted ``supplier_country`` as the literal country name
# ("China", "Vietnam"); spec §6 requires an ISO-2 code (CN, VN). The parser
# v2+ already does the mapping on the scraper side (``COUNTRY_ISO`` in
# ``sc_code/parser_code_v3.js``), so for most rows the supplier_country comes
# through already normalized. The middleware keeps this map locally as a
# SAFETY NET: if a row carries a free-text country name (e.g. an older parser
# version, or a scraper-side regression), we re-normalize here.
#
# Covers every country observed in MIC supplier home pages plus the majors.
# Add entries as new suppliers surface during live runs.
COUNTRY_NAME_TO_ISO2: dict[str, str] = {
    # Asia
    "China": "CN",
    "Vietnam": "VN",
    "Viet Nam": "VN",
    "Thailand": "TH",
    "India": "IN",
    "Taiwan": "TW",
    "Hong Kong": "HK",
    "South Korea": "KR",
    "Korea": "KR",
    "Republic of Korea": "KR",
    "Japan": "JP",
    "Singapore": "SG",
    "Malaysia": "MY",
    "Indonesia": "ID",
    "Philippines": "PH",
    "Pakistan": "PK",
    "Bangladesh": "BD",
    "Sri Lanka": "LK",
    "Turkey": "TR",
    "Türkiye": "TR",
    "United Arab Emirates": "AE",
    "UAE": "AE",
    "Saudi Arabia": "SA",
    "Israel": "IL",
    "Iran": "IR",
    # Americas
    "United States": "US",
    "USA": "US",
    "U.S.A.": "US",
    "Canada": "CA",
    "Mexico": "MX",
    "Brazil": "BR",
    "Argentina": "AR",
    "Chile": "CL",
    "Colombia": "CO",
    "Peru": "PE",
    # Europe
    "United Kingdom": "GB",
    "UK": "GB",
    "Germany": "DE",
    "France": "FR",
    "Italy": "IT",
    "Spain": "ES",
    "Netherlands": "NL",
    "Belgium": "BE",
    "Poland": "PL",
    "Russia": "RU",
    "Switzerland": "CH",
    "Sweden": "SE",
    "Norway": "NO",
    "Denmark": "DK",
    "Finland": "FI",
    "Ireland": "IE",
    "Portugal": "PT",
    "Austria": "AT",
    "Greece": "GR",
    "Czech Republic": "CZ",
    "Czechia": "CZ",
    # Oceania
    "Australia": "AU",
    "New Zealand": "NZ",
    # Africa
    "South Africa": "ZA",
    "Egypt": "EG",
    "Morocco": "MA",
    "Nigeria": "NG",
    "Kenya": "KE",
}


def iso2_for_country(name: str | None) -> str | None:
    """Normalize a free-text country name to ISO-2 (``None`` if unknown).

    Trims whitespace and does a case-sensitive lookup first, then a
    case-insensitive fallback. Returns ``None`` (not the raw name) when
    unmapped so the caller can emit ``country_unmapped`` / ``country_iso_unknown``.
    """
    if not name or not isinstance(name, str):
        return None
    key = name.strip()
    if not key:
        return None
    if key in COUNTRY_NAME_TO_ISO2:
        return COUNTRY_NAME_TO_ISO2[key]
    # Case-insensitive fallback (map keys are the canonical spelling).
    lower = key.lower()
    for canonical, iso in COUNTRY_NAME_TO_ISO2.items():
        if canonical.lower() == lower:
            return iso
    return None


# ---- Price-unit normalization (spec §4 / §5) ---------------------------------

# Canonical set of price_unit / moq_unit values the scraper emits. Anything
# outside this set is forwarded as-is but flagged ``price_unit_unknown``
# (spec §8 already asks for this on the scraper side; middleware re-checks to
# cover parser regressions).
KNOWN_PRICE_UNITS: frozenset[str] = frozenset(
    {
        "Ton",
        "Tons",
        "Mt",
        "MT",
        "Kg",
        "KG",
        "Piece",
        "Pieces",
        "Pcs",
        "Set",
        "Sets",
        "Bag",
        "Bags",
        "Drum",
        "Drums",
        "L",
        "Liter",
        "Liters",
        "Litre",
        "Litres",
        "M",
        "Meter",
        "Meters",
        "Metre",
        "Metres",
        "SQM",
        "SquareMeter",
    }
)

# ---- Saturation thresholds (per-scraper errors) ------------------------------

# Threshold above which we surface ``BLOCK_SATURATION`` / structural errors
# instead of returning data. Analogous to cosmetics-design PAYWALL_SATURATION
# and cosme BLOCK_SATURATION. Chosen the same 50% cutoff.
BLOCK_SATURATION_THRESHOLD: float = 0.5

# Threshold above which we surface ``STRUCTURE_CHANGED`` when too many rows
# carry ``metric_unit_missing`` / ``jsonld_parse_fallback`` / ``price_unit_unknown``
# — signals that the vendor DOM / JSON-LD changed and the parser degraded.
STRUCTURE_DEGRADED_THRESHOLD: float = 0.5

# ---- Misc --------------------------------------------------------------------

# Estimated runtime, surfaced in ``trigger()`` as ``eta_seconds``. Spec §9
# hard cap is 90 minutes / 2000 requests. A typical 5-keyword via-1 run with
# default ``max_pages=3`` and ~20 products per page plus details sits in the
# 30-60 minute band. 45 minutes is a safe middle estimate.
DEFAULT_ETA_SECONDS: int = 60 * 45


# ---- Snowflake mapper --------------------------------------------------------

from gli_scrapers.snowflake import SnowflakeMapper  # noqa: E402

MAPPER = SnowflakeMapper(
    table="DEV_STG.GNM_MEX.SRC_MADEINCHINA_PROV_HIST",
    source="made_in_china",
    field_map={
        "product_id":           "ID_PRODUCTO",
        "sku":                  "TX_SKU",
        "product_url":          "URL_PRODUCTO",
        "product_name_original":"NM_PRODUCTO_ORIGINAL",
        "product_name_clean":   "NM_PRODUCTO_CLEAN",
        "type":                 "TX_TIPO",
        "category_mic":         "TX_CATEGORIA_MIC",
        "category_path":        "DS_CATEGORIA_PATH",
        "price_min_usd":        "DS_PRECIO_MIN_USD",
        "price_max_usd":        "DS_PRECIO_MAX_USD",
        "price_raw":            "TX_PRECIO_RAW",
        "price_currency":       "TX_MONEDA",
        "moq_quantity":         "NU_MOQ_CANTIDAD",
        "moq_unit":             "TX_MOQ_UNIDAD",
        "cas_no":               "TX_CAS",
        "formula":              "TX_FORMULA",
        "einecs":               "TX_EINECS",
        "grade":                "TX_GRADO",
        "appearance":           "TX_APARIENCIA",
        "supplier_id":          "ID_PROVEEDOR",
        "supplier_name_raw":    "NM_PROVEEDOR_RAW",
        "image_primary":        "URL_IMAGEN",
        "site_code":            "TX_SITIO",
        "scraper_flags":        "DS_FLAGS",
        "scraped_date":         "DT_SCRAPING",
        "input":                "DS_INPUT",
    },
    variant_fields={"DS_CATEGORIA_PATH", "DS_PRECIO_MIN_USD", "DS_PRECIO_MAX_USD",
                    "DS_FLAGS", "DS_INPUT"},
)
