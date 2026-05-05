"""Static configuration for the ``cosme_new_arrivals`` middleware.

All secret/environment values are resolved lazily via env vars. This module
only exposes constant defaults — never read ``os.getenv`` at import time for
required secrets, so that downstream code (tests, type checkers) can import
without crashing.

Dual-mode resolution
--------------------

cosme-new-arrivals can run against either BrightData transport:

    - **Datasets v3** (modern, ``gd_...``) — if the scraper is in Scraper Studio.
    - **DCA legacy** (``c_.../j_...``) — if it lives as a legacy collector.

The middleware picks the mode based on which env var the user has populated.
v3 wins when both are set (same precedence rule as other middlewares).
"""

from __future__ import annotations

import os
from typing import Literal

# ---- BrightData -------------------------------------------------------------

SOURCE_NAME: str = "cosme-new-arrivals"

# Env var for the BrightData dataset id (v3 mode).
DATASET_ID_ENV_VAR: str = "BRIGHTDATA_DATASET_ID_COSME_NEW_ARRIVALS"

# Env var for the BrightData collector id (DCA legacy mode).
COLLECTOR_ID_ENV_VAR: str = "BRIGHTDATA_COLLECTOR_ID_COSME_NEW_ARRIVALS"


def get_dataset_id() -> str | None:
    """Resolve the BrightData dataset id (v3) from the environment."""
    return os.getenv(DATASET_ID_ENV_VAR)


def get_collector_id() -> str | None:
    """Resolve the BrightData collector id (DCA legacy) from the environment."""
    return os.getenv(COLLECTOR_ID_ENV_VAR)


ApiMode = Literal["v3", "dca"]


def resolve_mode_and_id() -> tuple[ApiMode | None, str | None]:
    """Decide ``(api_mode, resource_id)`` based on the populated env vars.

    Precedence:
        1. ``BRIGHTDATA_DATASET_ID_COSME_NEW_ARRIVALS`` set → ``("v3", dataset_id)``
        2. ``BRIGHTDATA_COLLECTOR_ID_COSME_NEW_ARRIVALS`` set → ``("dca", collector_id)``
        3. Neither → ``(None, None)`` — client raises ``INVALID_INPUTS`` at trigger time.
    """
    ds = get_dataset_id()
    col = get_collector_id()
    if ds:
        return ("v3", ds)
    if col:
        return ("dca", col)
    return (None, None)


CREDENTIAL_HINT: str = (
    "Set one of:\n"
    f"  {DATASET_ID_ENV_VAR}   (for Datasets v3, gd_...)\n"
    f"  {COLLECTOR_ID_ENV_VAR} (for DCA legacy, c_...)"
)

# ---- Operational limits -----------------------------------------------------

# ETA estimate surfaced in trigger(). Calendar scraping covers a full month
# (~31 day-pages). Conservative upper bound for polling cadence sizing.
DEFAULT_ETA_SECONDS: int = 1800

# ---- Snowflake mapper --------------------------------------------------------

from gli_scrapers.snowflake import SnowflakeMapper  # noqa: E402

_DB     = os.getenv("SNOWFLAKE_DATABASE", "DEV_STG")
_SCHEMA = os.getenv("SNOWFLAKE_SCHEMA", "GNM_MEX")

MAPPER = SnowflakeMapper(
    table=f"{_DB}.{_SCHEMA}.SRC_COSME_RANKING_NEWARRIVALS",
    source="cosme-new-arrivals",
    field_map={
        # Base fields (Stage 2 — todos los productos)
        "product_id":        "ID_PRODUCTO",
        "product_url":       "URL_PRODUCTO",
        "product_name":      "NM_PRODUCTO",
        # "brand_id":        "ID_MARCA",      # 100% NULL — columna eliminada de la tabla
        "brand_name":        "NM_MARCA",
        "brand_url":         "URL_MARCA",
        "release_date":      "DT_LANZAMIENTO",
        "shop_url":          "URL_TIENDA",
        "scraped_at":        "DT_SCRAPING",
        # Enriched fields (Stage 3 — solo productos futuros)
        "description":       "TX_DESCRIPCION",
        "how_to_use":        "TX_MODO_USO",
        # "ingredients":     "TX_INGREDIENTES",   # 100% NULL — columna eliminada de la tabla
        # "classification":  "TX_CLASIFICACION",  # 100% NULL — columna eliminada de la tabla
        # "jan_code":        "TX_JAN_CODE",        # 100% NULL — columna eliminada de la tabla
        # "official_url":    "URL_OFICIAL",        # 100% NULL — columna eliminada de la tabla
        "manufacturer":      "NM_FABRICANTE",
        "manufacturer_url":  "URL_FABRICANTE",
        "category_full":     "TX_CATEGORIA_FULL",
        "category_path":     "DS_CATEGORIA_PATH",
        "rating_detail":     "NU_RATING",
        "points":            "NU_PUNTOS",
        "review_count":      "NU_RESENAS",
        "photo_count":       "NU_FOTOS",
        "qa_count":          "NU_QA",
        # "cat_rank":        "NU_RANK_CATEGORIA",  # 100% NULL — columna eliminada de la tabla
        # "cat_rank_name":   "NM_CATEGORIA_RANK",  # 100% NULL — columna eliminada de la tabla
        "likes":             "NU_LIKES",
        "haves":             "NU_HAVES",
        "all_images":        "DS_IMAGENES",
        "stores":            "DS_TIENDAS",
        "related_products":  "DS_PRODUCTOS_RELACIONADOS",
        # "scraper_flags":   "DS_FLAGS",           # 100% NULL — columna eliminada de la tabla
    },
    date_fields={"DT_LANZAMIENTO", "DT_SCRAPING"},
    variant_fields={
        "DS_CATEGORIA_PATH", "DS_IMAGENES", "DS_TIENDAS",
        "DS_PRODUCTOS_RELACIONADOS",
    },
)
