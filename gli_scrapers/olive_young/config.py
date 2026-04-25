"""Static configuration for the ``olive_young`` middleware.

Mirrors the pattern of ``gli_scrapers/cosmetics_design/config.py`` and
``gli_scrapers/cosme/config.py``. All secret/environment values are resolved
lazily via env vars (see ``BaseScraperClient._ensure_credentials``). This
module only exposes constant defaults — never read ``os.getenv`` at import
time for required secrets, so downstream code (tests, type checkers) can
import without crashing.

Dual-mode resolution
--------------------

olive-young can run against either BrightData transport:

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

# Source name as it appears in the envelope (matches scrapers/<name>/ folder,
# hyphenated — the Python package uses underscore but the ``source`` field in
# the envelope is always the scraper's canonical name).
SOURCE_NAME: str = "olive-young"

# Env var that holds the BrightData **dataset id** for this scraper (v3 mode).
DATASET_ID_ENV_VAR: str = "BRIGHTDATA_DATASET_ID_OLIVE_YOUNG"

# Env var that holds the BrightData **collector id** for this scraper (DCA
# legacy mode). Only read when the user has not populated the v3 env var.
COLLECTOR_ID_ENV_VAR: str = "BRIGHTDATA_COLLECTOR_ID_OLIVE_YOUNG"


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

# Spec §3 / §9: the API host for rankings. Used by the JS scraper's Stage 1
# to discover categories and ranking rows. Surfaced here so tests / debug
# scripts can reach the same host without duplicating the string.
RANKINGS_API_HOST: str = "https://product-ranking-service.oliveyoung.com"

# Spec §3 / §9: the public site used for product detail + brand enrichment.
SITE_HOST: str = "https://global.oliveyoung.com"

# Spec §3: only these two regions are valid. ``Global`` and ``language-code=ko``
# return 400 / empty arrays (see scrapers/olive-young/results/errors.md E3).
VALID_REGIONS: tuple[str, ...] = ("KR", "USA")

# Spec §3: locked request knobs for the ranking API.
LANGUAGE_CODE: str = "en"
MARGIN_COUNTRY_CODE: str = "10"
DELIVERY_COUNTRY_CODE: str = "10"

# Scraper v4 listing URL (interaction_code_v4.js LISTING_URL constant).
# The JS scraper uses this as the default when input.url is empty.
# The middleware passes it explicitly so the seed is always unambiguous.
DEFAULT_LISTING_URL: str = "https://global.oliveyoung.com/display/page/best-seller?target=pillsTab1Nav1"

# Default pagination budget forwarded to the JS scraper (input.max_pages).
DEFAULT_MAX_PAGES: int = 3

# Spec §8: default crawl budgets. The middleware does NOT enforce the hard
# caps — the JS scraper does. These are surfaced so the seed built for
# BrightData can carry them forward.
DEFAULT_MAX_PRODUCTS_ENRICH: int = 100  # detail-page enrichments per run
DEFAULT_MAX_BRAND_VISITS: int = 20  # brand-page visits per run

# Spec §8: hard per-run caps. The middleware uses these as the upper bound on
# public inputs so fat-finger typos surface as INVALID_INPUTS.
HARD_CAP_REQUESTS: int = 1000
HARD_CAP_MINUTES: int = 60

# Spec §8: cap on the number of product rows the middleware will emit. There
# are 11 KR categories × 100 rows + 12 USA categories × 100 rows ≈ 2300 rows
# of ranking-level data; after product dedup the distinct product count is
# typically 500–1500. 3000 is a generous upper bound that matches cosme.
MAX_PRODUCTS_HARD_CAP: int = 3000

# ---- Saturation thresholds (per-scraper errors) ------------------------------

# Analogous to cosme's BLOCK_SATURATION. Olive Young global is fronted by
# Cloudflare with a silent bot-challenge (spec §2 genomma lab). If a majority
# of emitted ranking rows carry ``cloudflare_challenge`` or ``api_400``, the
# run is materially useless — surface as BLOCK_SATURATION.
BLOCK_SATURATION_THRESHOLD: float = 0.5

# ---- Misc --------------------------------------------------------------------

# Estimated runtime, surfaced in trigger() as eta_seconds. Spec §8 hard cap
# is 60 minutes wall time. A typical run (26 API calls + up to 100 detail
# enrichments via Scraping Browser + up to 20 brand pages) sits around
# 20-35 minutes. 25 minutes is the safe middle estimate.
DEFAULT_ETA_SECONDS: int = 60 * 25
