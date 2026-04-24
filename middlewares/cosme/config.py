"""Static configuration for the ``cosme`` middleware.

Mirrors the pattern of ``middlewares/cosmetics_design/config.py``. All
secret/environment values are resolved lazily via env vars (see
``BaseScraperClient._ensure_credentials``). This module only exposes constant
defaults — never read ``os.getenv`` at import time for required secrets, so
downstream code (tests, type checkers) can import without crashing.

Dual-mode resolution
--------------------

cosme can run against either BrightData transport:

    - **Datasets v3** (modern, ``gd_...``) — the target once the scraper is
      migrated to Scraper Studio in the dashboard.
    - **DCA legacy** (``c_.../j_...``) — if the scraper is still published
      under the legacy Data Collectors Archive API.

The middleware picks the mode based on which env var the user has populated.
See ``docs/fase3/middleware-dual-mode.md`` §3.
"""

from __future__ import annotations

import os
from typing import Literal

# ---- BrightData --------------------------------------------------------------

# Source name as it appears in the envelope (matches scrapers/<name>/ folder).
SOURCE_NAME: str = "cosme"

# Env var that holds the BrightData **dataset id** for this scraper (v3 mode).
DATASET_ID_ENV_VAR: str = "BRIGHTDATA_DATASET_ID_COSME"

# Env var that holds the BrightData **collector id** for this scraper (DCA
# legacy mode). Only read when the user has not populated the v3 env var.
COLLECTOR_ID_ENV_VAR: str = "BRIGHTDATA_COLLECTOR_ID_COSME"


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

# Seed URL for Stage 1 (sc_browser) discovery. The integration code derives
# ``award_year`` from ``input.award_year`` (see spec §10 / §11); if not
# provided it falls back to ``new Date().getFullYear()``.
# Default seed = the bestcosme archive root for the current year. The Stage 1
# code will expand it into grand/hall/rookie/category URLs and next_stage()
# each product discovered there.
ARCHIVE_ROOT_URL_TMPL: str = "https://www.cosme.net/bestcosme/archive/{year}/"


def archive_root_url(year: int) -> str:
    return ARCHIVE_ROOT_URL_TMPL.format(year=year)


# Spec §7: bestcosme grand/hall/rookie = 1 page each, category = 24+ slugs x
# 1 page each, category ranking = max 5 x 30 cats, product detail = max 3000
# unique products with dedup, brand listing = max 10 pages >=20 products,
# hard cap = 10000 requests or 120 min.
MAX_PRODUCTS_HARD_CAP: int = 3000
"""Hard ceiling on ``max_products`` (spec §7: product detail max 3000 unique)."""

MAX_CATEGORIES_HARD_CAP: int = 30
"""Hard ceiling on category_ranking slugs (spec §7: 5 pages x 30 cats max)."""

# Current calendar year — used as the default when caller does not pass
# ``year`` to ``trigger``. The JS scraper resolves the same fallback on its
# side (spec §10 resolveYear), but we surface it on the Python side so the
# envelope's ``inputs`` dict is self-documenting.
import datetime as _dt

DEFAULT_YEAR: int = _dt.datetime.now(_dt.timezone.utc).year

# ---- Saturation thresholds (per-scraper errors) ------------------------------

# Threshold above which we surface BLOCK_SATURATION instead of returning data.
# Analogous to cosmetics-design's PAYWALL_SATURATION. For cosme the site
# blocks aggressively (spec §2 of genomma lab describes the 3-retry flow);
# if a majority of emitted rows carry ``rate_limit_blocked`` or
# ``name_extract_failed`` the run is materially useless.
BLOCK_SATURATION_THRESHOLD: float = 0.5

# ---- Misc --------------------------------------------------------------------

# Estimated runtime, surfaced in trigger() as eta_seconds. Spec §7 hard cap
# is 120 minutes, a typical run that covers grand/hall/rookie + 24 categories
# sits in the 45-75 minute band (Stage 1 discovery is fast; Stage 2 HTTP
# fetch is the bottleneck with 1-2s delay per product). 60 minutes is a
# safe middle estimate.
DEFAULT_ETA_SECONDS: int = 60 * 60
