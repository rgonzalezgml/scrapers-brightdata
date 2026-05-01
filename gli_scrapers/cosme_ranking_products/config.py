"""Static configuration for the ``cosme_ranking_products`` middleware.

All secret/environment values are resolved lazily via env vars. This module
only exposes constant defaults — never read ``os.getenv`` at import time for
required secrets, so that downstream code (tests, type checkers) can import
without crashing.

Dual-mode resolution
--------------------

cosme-ranking-products can run against either BrightData transport:

    - **Datasets v3** (modern, ``gd_...``) — if the scraper is in Scraper Studio.
    - **DCA legacy** (``c_.../j_...``) — if it lives as a legacy collector.

The middleware picks the mode based on which env var the user has populated.
v3 wins when both are set (same precedence rule as cosmetics-design).
"""

from __future__ import annotations

import os
from typing import Literal

# ---- BrightData -------------------------------------------------------------

SOURCE_NAME: str = "cosme_ranking_products"

# Env var for the BrightData dataset id (v3 mode).
DATASET_ID_ENV_VAR: str = "BRIGHTDATA_DATASET_ID_COSME_RANKING"

# Env var for the BrightData collector id (DCA legacy mode).
COLLECTOR_ID_ENV_VAR: str = "BRIGHTDATA_COLLECTOR_ID_COSME_RANKING"


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
        1. ``BRIGHTDATA_DATASET_ID_COSME_RANKING`` set → ``("v3", dataset_id)``
        2. ``BRIGHTDATA_COLLECTOR_ID_COSME_RANKING`` set → ``("dca", collector_id)``
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

# ---- Scraper-side defaults ---------------------------------------------------

# Default landing URL (used when the user does not pass a custom URL).
SOURCE_LANDING_URL: str = "https://www.cosme.net/ranking/products"

# ---- Operational limits -----------------------------------------------------

# ETA estimate surfaced in trigger(). The run is typically 10-15 min for
# 100 products (Stage 1 + Stage 2 HTTP fetches). 900s is a conservative upper
# bound surfaced to the agents repo for polling cadence sizing.
DEFAULT_ETA_SECONDS: int = 900

# Max pages the scraper JS supports (10 products per page, 10 pages = 100 products).
MAX_PAGES: int = 10

# ---- Snowflake mapper --------------------------------------------------------

from gli_scrapers.snowflake import SnowflakeMapper  # noqa: E402

_DB     = os.getenv("SNOWFLAKE_DATABASE", "DEV_STG")
_SCHEMA = os.getenv("SNOWFLAKE_SCHEMA", "GNM_MEX")

MAPPER = SnowflakeMapper(
    table=f"{_DB}.{_SCHEMA}.SRC_COSME_RANKING_HIST",
    source="cosme_ranking_products",
    field_map={
        "rank":              "NU_RANK",
        "rank_change":       "TX_RANK_CAMBIO",
        "product_id":        "ID_PRODUCTO",
        "product_name":      "NM_PRODUCTO",
        "product_name_jp":   "NM_PRODUCTO_JP",
        "product_img":       "URL_IMG_PRINCIPAL",
        "brand_name":        "NM_MARCA",
        "brand_name_jp":     "NM_MARCA_JP",
        "brand_url":         "URL_MARCA",
        "manufacturer":      "NM_FABRICANTE",
        "manufacturer_url":  "URL_FABRICANTE",
        "category":          "NM_CATEGORIA",
        "category_url":      "URL_CATEGORIA",
        "category_full":     "TX_CATEGORIA_FULL",
        "category_path":     "DS_CATEGORIA_PATH",
        "price_text":        "TX_PRECIO_RAW",
        "price_yen":         "NU_PRECIO_YEN",
        "size":              "TX_TALLA",
        "is_open_price":     "FL_PRECIO_ABIERTO",
        "tax_included":      "FL_INCLUYE_IVA",
        "rating":            "NU_RATING",
        "rating_detail":     "NU_RATING_DETAIL",
        "points":            "NU_PUNTOS",
        "ranking_in":        "DS_RANKING_EN",
        "review_count":      "NU_RESENAS",
        "photo_count":       "NU_FOTOS",
        "qa_count":          "NU_QA",
        "likes":             "NU_LIKES",
        "haves":             "NU_HAVES",
        "release_date":      "TX_FECHA_LANZAMIENTO",
        "is_best_cosme":     "FL_BEST_COSME",
        "is_new":            "FL_NUEVO",
        "description":       "TX_DESCRIPCION",
        "how_to_use":        "TX_MODO_USO",
        "ingredients":       "TX_INGREDIENTES",
        "classification":    "TX_CLASIFICACION",
        "jan_code":          "TX_JAN_CODE",
        "official_url":      "URL_OFICIAL",
        "all_images":        "DS_IMAGENES",
        "stores":            "DS_TIENDAS",
        "related_products":  "DS_PRODUCTOS_RELACIONADOS",
        "shop_url":          "URL_TIENDA",
        "period_start":      "DT_PERIODO_INICIO",
        "period_end":        "DT_PERIODO_FIN",
        "scraped_at":        "DT_SCRAPING",
        "input":             "DS_INPUT",
    },
    variant_fields={
        "DS_IMAGENES", "DS_INPUT", "DS_CATEGORIA_PATH",
        "DS_RANKING_EN", "DS_TIENDAS", "DS_PRODUCTOS_RELACIONADOS",
    },
    date_fields={"DT_PERIODO_INICIO", "DT_PERIODO_FIN", "DT_SCRAPING"},
)
