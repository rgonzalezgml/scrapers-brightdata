"""Static configuration for the ``cosmetics_design`` middleware.

All secret/environment values are resolved lazily via env vars (see
``BaseScraperClient._ensure_credentials``). This module only exposes constant
defaults — never read ``os.getenv`` at import time for required secrets, so
that downstream code (tests, type checkers) can import without crashing.

Dual-mode resolution
--------------------

cosmetics-design can run against either BrightData transport:

    - **Datasets v3** (modern, ``gd_...``) — the target once the scraper is
      migrated to Scraper Studio in the dashboard.
    - **DCA legacy** (``c_.../j_...``) — the state at day 0 (the scraper is
      already published as collector ``c_mo8nphfk1olmzmfuin``).

The middleware picks the mode based on which env var the user has populated.
See ``docs/fase3/middleware-dual-mode.md`` §3.
"""

from __future__ import annotations

import os
from typing import Literal

# ---- BrightData --------------------------------------------------------------

# Source name as it appears in the envelope (matches scrapers/<name>/ folder).
SOURCE_NAME: str = "cosmetics-design"

# Env var that holds the BrightData **dataset id** for this scraper (v3 mode).
# IMPORTANT: do not hard-code the dataset id. The user populates the .env
# after the BrightData dashboard exposes the value (handoff §0).
DATASET_ID_ENV_VAR: str = "BRIGHTDATA_DATASET_ID_COSMETICS_DESIGN"

# Env var that holds the BrightData **collector id** for this scraper (DCA
# legacy mode). Only read when the user has not populated the v3 env var.
COLLECTOR_ID_ENV_VAR: str = "BRIGHTDATA_COLLECTOR_ID_COSMETICS_DESIGN"


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

# Landing URL the JS scraper crawls. Spec §3 / §10.
SOURCE_LANDING_URL: str = (
    "https://www.nutraingredients.com/Health-conditions/Beauty-wellness/"
)

# Default ``supplier`` value injected into every emitted article (spec §10).
DEFAULT_SUPPLIER: str = "William Reed"

# ---- Translation: public inputs → JS scraper inputs --------------------------

# How many landing-page "Load more" clicks roughly correspond to
# ``max_articles`` items. The landing emits ~50 items per click (spec §3 /
# §7). We use this only to derive ``max_pages`` for the JS scraper input.
ARTICLES_PER_PAGE: int = 50

# Hard cap on max_pages we will ever send to the JS scraper, regardless of
# what max_articles asks for. Mirrors the spec §7 "20 pages ≈ 1000 articles"
# operational recommendation. Above this, prefer max_pages=-1 (unlimited)
# guarded by BrightData's hard cap (5000 requests / 90 min wall time).
MAX_PAGES_HARD_CAP: int = 100

# ---- Misc --------------------------------------------------------------------

# Estimated runtime, surfaced in trigger() as eta_seconds. Used by the agents
# repo to size its polling cadence — not a contractual deadline.
DEFAULT_ETA_SECONDS: int = 60 * 30  # 30 minutes for a typical 1000-article run.
