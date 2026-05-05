"""Static configuration for the ``olive_young_new_arrivals`` middleware.

All secret/environment values are resolved lazily via env vars. This module
only exposes constant defaults — never read ``os.getenv`` at import time for
required secrets, so downstream code (tests, type checkers) can import without
crashing.

Dual-mode resolution
--------------------

olive-young-new-arrivals supports both BrightData transports:

    - **Datasets v3** (modern, ``gd_...``) — target once the scraper is
      published in Scraper Studio.
    - **DCA legacy** (``c_.../j_...``) — if the scraper is still published
      under the legacy Data Collectors Archive API.

``DATASET_ID_ENV_VAR`` wins over ``COLLECTOR_ID_ENV_VAR`` when both are set.
"""

from __future__ import annotations

import os
from typing import Literal

# ---- BrightData --------------------------------------------------------------

# Source name as it appears in the envelope (scraper canonical name, hyphenated).
SOURCE_NAME: str = "olive-young-new-arrivals"

# Env var that holds the BrightData **dataset id** for this scraper (v3 mode).
DATASET_ID_ENV_VAR: str = "BRIGHTDATA_DATASET_ID_OLIVE_YOUNG_NEW_ARRIVALS"

# Env var that holds the BrightData **collector id** for this scraper (DCA
# legacy mode). Only used when the v3 env var is unset.
COLLECTOR_ID_ENV_VAR: str = "BRIGHTDATA_COLLECTOR_ID_OLIVE_YOUNG_NEW_ARRIVALS"


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

    Precedence:
        1. If ``DATASET_ID`` is set → ``("v3", dataset_id)``. v3 wins over DCA
           when both are populated.
        2. Else if ``COLLECTOR_ID`` is set → ``("dca", collector_id)``.
        3. Else → ``(None, None)`` — let the client raise ``INVALID_INPUTS``
           at trigger time with a hint that names both env vars.
    """
    ds = get_dataset_id()
    col = get_collector_id()
    if ds:
        return ("v3", ds)
    if col:
        return ("dca", col)
    return (None, None)


# Human-readable hint used in the INVALID_INPUTS error message when neither
# env var is populated.
CREDENTIAL_HINT: str = (
    "Set one of:\n"
    f"  {DATASET_ID_ENV_VAR}   (for Datasets v3, gd_...)\n"
    f"  {COLLECTOR_ID_ENV_VAR} (for DCA legacy, c_...)"
)

# ---- Scraper-side defaults ---------------------------------------------------

# Spec §3: the new-arrivals page (Vue 2 SPA shell). Forwarded as the seed URL
# to BrightData so the JS scraper always knows its entry point.
NEW_ARRIVALS_URL: str = "https://global.oliveyoung.com/display/page/new-arrivals"

# Spec §8: hard cap on products per run. The API typically returns < 200 but
# 500 is the configured maximum as a safety net.
DEFAULT_MAX_PRODUCTS: int = 500

# Spec §8: estimated wall time for the run (30 minutes max per spec).
DEFAULT_ETA_SECONDS: int = 60 * 20  # 20 minutes is a reasonable middle estimate

# ---- Snowflake mapper --------------------------------------------------------

from gli_scrapers.snowflake import SnowflakeMapper  # noqa: E402

_DB     = os.getenv("SNOWFLAKE_DATABASE", "DEV_STG")
_SCHEMA = os.getenv("SNOWFLAKE_SCHEMA", "GNM_MEX")

MAPPER = SnowflakeMapper(
    table=f"{_DB}.{_SCHEMA}.SRC_OLIVEYOUNG_NEWARRIVALS",
    source="olive_young_new_arrivals",
    field_map={
        # Producto
        "prdt_no":          "TX_PRDT_NO",
        "url":              "URL_PRODUCTO",
        "product_name_en":  "NM_PRODUCTO_EN",
        "product_name_kr":  "NM_PRODUCTO_KR",
        "image_url":        "URL_IMAGEN",
        # Marca
        "brand_no":         "TX_BRAND_NO",
        "brand_name_en":    "NM_MARCA_EN",
        "brand_url":        "URL_MARCA",
        "brand_image_url":  "URL_IMAGEN_MARCA",
        # Precio
        "sale_amt":         "TX_PRECIO_VENTA",
        "nrml_amt":         "TX_PRECIO_NORMAL",
        "discount_rate":    "TX_DESCUENTO",
        # Categoría
        "category":         "NM_CATEGORIA",
        "categories":       "DS_CATEGORIAS",
        # Métricas
        "rating":           "NU_RATING",
        "review_count":     "NU_RESENAS",
        # Contenido enriquecido
        "why_we_love_it":   "TX_DESCRIPCION",
        "how_to_use":       "TX_MODO_USO",
        "extra_images":     "TX_IMAGENES_EXTRA",
        # Flags
        "is_new":           "FL_NEW",
        "is_best":          "FL_BEST",
        "has_gift":         "FL_REGALO",
        # Corner y metadata
        "corner_name":      "NM_CORNER",
        "scraped_date":     "DT_SCRAPING",
    },
    date_fields={"DT_SCRAPING"},
    variant_fields={"DS_CATEGORIAS"},
)
