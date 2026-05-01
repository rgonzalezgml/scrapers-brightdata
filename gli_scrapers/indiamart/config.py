"""Static configuration for the ``indiamart`` middleware.

All secret/environment values are resolved lazily via env vars (see
``BaseScraperClient._ensure_credentials``). This module only exposes constant
defaults — never read ``os.getenv`` at import time for required secrets, so
downstream code (tests, type checkers) can import without crashing.

Dual-mode resolution
--------------------

indiamart can run against either BrightData transport:

    - **Datasets v3** (modern, ``gd_...``) — once the scraper is migrated to
      Scraper Studio in the dashboard.
    - **DCA legacy** (``c_.../j_...``) — if still published under the legacy
      Data Collectors Archive API.

The middleware picks the mode based on which env var the user has populated.
See ``docs/fase3/middleware-dual-mode.md`` §3.
"""

from __future__ import annotations

import os
from typing import Literal

# ---- BrightData --------------------------------------------------------------

# Source name as it appears in the envelope (matches scrapers/<name>/ folder).
SOURCE_NAME: str = "indiamart"

# Env var that holds the BrightData **dataset id** for this scraper (v3 mode).
DATASET_ID_ENV_VAR: str = "BRIGHTDATA_DATASET_ID_INDIAMART"

# Env var that holds the BrightData **collector id** for this scraper (DCA
# legacy mode). Only read when the user has not populated the v3 env var.
COLLECTOR_ID_ENV_VAR: str = "BRIGHTDATA_COLLECTOR_ID_INDIAMART"


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

# Default seed MCATs for Stage 1 discovery (spec §9 "12 MCATs seed"). The JS
# scraper's interaction code expands each seed into subcats + product detail
# pages. We forward the user's requested category slugs as seeds; the default
# set mirrors spec §9 exactly.
DEFAULT_MCAT_SLUGS: tuple[str, ...] = (
    "caustic-soda",
    "sodium-hydroxide-pellets",
    "hydrochloric-acid",
    "sulphuric-acid",
    "sodium-carbonate",
    "acetic-acid",
    "industrial-drums",
    "industrial-containers",
    "plastic-drums",
    "corrugated-box",
    "packaging-materials",
    "stretch-film",
)

# Default industry hubs (spec §9 via-2). Used when ``include_industry_hubs``
# is true (default). Each hub enumerates up to 100 additional MCATs.
DEFAULT_INDUSTRY_HUBS: tuple[str, ...] = ("chem", "packaging")

# URL templates — Stage 1 seeds.
MCAT_LISTING_URL_TMPL: str = "https://dir.indiamart.com/impcat/{slug}.html"
INDUSTRY_HUB_URL_TMPL: str = (
    "https://dir.indiamart.com/indianexporters/ind_{industry}.html"
)


def mcat_listing_url(slug: str) -> str:
    return MCAT_LISTING_URL_TMPL.format(slug=slug)


def industry_hub_url(industry: str) -> str:
    return INDUSTRY_HUB_URL_TMPL.format(industry=industry)


# Hard caps per spec §9: "3000 requests o 90 minutos" for the whole run;
# 1500 unique PRODUCT_ID detail, 300 supplier home. The middleware does NOT
# re-enforce the global request cap (that lives in BrightData's own runtime),
# but clips emitted rows post-download.
MAX_PRODUCTS_HARD_CAP: int = 1500
"""Hard ceiling on ``max_products`` — spec §9 ("1500 unique PRODUCT_ID detail")."""

MAX_SUPPLIERS_HARD_CAP: int = 300
"""Hard ceiling on emitted supplier rows — spec §9 ("300 supplier home")."""

MAX_MCAT_SEEDS_HARD_CAP: int = 50
"""Upper bound on MCAT seeds per run. The scraper itself caps by site
discovery; this is a sanity fence so a fat-finger call cannot balloon the
seed list beyond what the scraper will actually consume."""

# ---- Saturation thresholds (per-scraper errors) ------------------------------

# Threshold above which we surface STRUCTURE_CHANGED instead of returning data.
# Per the task contract: if the parser extracted <50% of the rows expected
# (i.e. rows without product_id or name because the site DOM/JSON-LD moved),
# escalate. We key on per-product ``scraper_flags`` that indicate parse
# fallbacks (``jsonld_parse_fallback``, ``breadcrumb_missing``, ...).
STRUCTURE_CHANGED_THRESHOLD: float = 0.5

# Threshold above which we surface SITE_BLOCKED. Per spec §2 genomma lab, a
# sustained 403/503 + "Access Denied" + redirect to /enquiry.html surfaces
# as ``blocked`` / ``rate_limit_blocked`` flags on the product row. If >50%
# of emitted rows carry either flag, the run is materially useless.
BLOCK_SATURATION_THRESHOLD: float = 0.5

# ---- FX / currency ----------------------------------------------------------

# Default exchange rate INR → USD. Spec §4 "price_min_usd, price_max_usd
# numericos convertidos con EXCHANGE_RATES (INR~0.012)". The JS scraper
# applies conversion itself; this constant is only a reference value the
# middleware surfaces in ``meta`` for the agents repo.
DEFAULT_INR_TO_USD: float = 0.012

# ---- Misc --------------------------------------------------------------------

# Estimated runtime, surfaced in trigger() as eta_seconds. Spec §9 hard cap
# is 90 minutes; a default run of 12 MCATs + 2 hubs + 500-1000 products fits
# in 30-60 minutes. 45 minutes is a safe middle estimate.
DEFAULT_ETA_SECONDS: int = 60 * 45


# ---- Snowflake mapper --------------------------------------------------------

from gli_scrapers.snowflake import SnowflakeMapper  # noqa: E402

_DB     = os.getenv("SNOWFLAKE_DATABASE", "DEV_STG")
_SCHEMA = os.getenv("SNOWFLAKE_SCHEMA", "GNM_MEX")

MAPPER = SnowflakeMapper(
    table=f"{_DB}.{_SCHEMA}.SRC_INDIAMART_PROV_HIST",
    source="indiamart",
    field_map={
        "product_id":          "ID_PRODUCTO",
        "url":                 "URL_PRODUCTO",
        "product_name_original":"NM_PRODUCTO_ORIGINAL",
        "product_name_clean":  "NM_PRODUCTO_CLEAN",
        "product_description": "TX_DESCRIPCION",
        "type":                "TX_TIPO",
        "category_mic":        "TX_CATEGORIA_MIC",
        "category_path":       "DS_CATEGORIA_PATH",
        "price_min_usd":       "DS_PRECIO_MIN_USD",
        "price_max_usd":       "DS_PRECIO_MAX_USD",
        "price_raw":           "TX_PRECIO_RAW",
        "price_value_raw":     "TX_PRECIO_VALOR_RAW",
        "price_unit":          "TX_UNIDAD_PRECIO",
        "price_currency":      "TX_MONEDA",
        "availability":        "TX_DISPONIBILIDAD",
        "supplier_id":         "ID_PROVEEDOR",
        "supplier_name":       "NM_PROVEEDOR",
        "supplier_url":        "URL_PROVEEDOR",
        "supplier_city":       "TX_CIUDAD_PROVEEDOR",
        "supplier_country":    "TX_PAIS_PROVEEDOR",
        "verified":            "FL_VERIFICADO",
        "trustseal":           "FL_TRUSTSEAL",
        "member_since_year":   "NU_ANIO_MIEMBRO",
        "image_primary":       "URL_IMAGEN",
        "site_code":           "TX_SITIO",
        "scraper_flags":       "DS_FLAGS",
        "scraped_date":        "DT_SCRAPING",
        "input":               "DS_INPUT",
    },
    variant_fields={"DS_CATEGORIA_PATH", "DS_PRECIO_MIN_USD", "DS_PRECIO_MAX_USD",
                    "DS_FLAGS", "DS_INPUT"},
)
