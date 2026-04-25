"""Static configuration for the ``impi`` middleware.

Atypical vs the other middlewares: this one does NOT wrap a BrightData scraper
— it wraps the standalone ``impi_scraper_mx`` Python package
(`/workspace/impi_scraper_mx/`)
which hits the IMPI Mexico portal directly. That has three consequences:

    1. No ``DATASET_ID`` / ``COLLECTOR_ID`` / ``BRIGHTDATA_API_KEY`` env vars.
       The adapter needs no credentials — ``impi_scraper_mx.IMPIClient`` talks to
       a public portal.
    2. No polling: the underlying scraper is synchronous and responds in
       seconds. ``trigger`` does all the work; ``get_result`` is a cache lookup.
    3. ``eta_seconds=0`` — there is no background job queue.
"""

from __future__ import annotations

# Source name as it appears in the envelope. Matches the scraper directory
# name convention (other middlewares: "cosmetics-design", "cosme", ...).
SOURCE_NAME: str = "impi"

# Surfaced in ``trigger()`` as ``eta_seconds``. Zero because ``trigger``
# returns only after the underlying sync scraper has already finished and the
# envelope is stored — ``get_result`` is immediate.
DEFAULT_ETA_SECONDS: int = 0
