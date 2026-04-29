"""Pytest config for the cosme_ranking_products middleware tests.

- Forces ``asyncio_mode = "auto"`` so tests written as ``async def`` Just Work.
- Resolves the fixtures dir once.
- Skips tests that need real BrightData credentials when the env is unset.
  Dual-mode: a live test is runnable if EITHER ``BRIGHTDATA_DATASET_ID_*``
  (v3) OR ``BRIGHTDATA_COLLECTOR_ID_*`` (DCA) is populated alongside
  ``BRIGHTDATA_API_KEY``.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"

SNAPSHOT_FIXTURE = FIXTURES_DIR / "cosme_ranking_snapshot_demo01.json"


@pytest.fixture
def snapshot_rows() -> list[dict]:
    """Load the canonical fixture as a list of raw BrightData rows."""
    import json

    with SNAPSHOT_FIXTURE.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def pytest_collection_modifyitems(config, items):
    """Skip ``@pytest.mark.brightdata`` tests when env vars are missing."""
    has_key = bool(os.getenv("BRIGHTDATA_API_KEY"))
    has_dataset = bool(os.getenv("BRIGHTDATA_DATASET_ID_COSME_RANKING"))
    has_collector = bool(os.getenv("BRIGHTDATA_COLLECTOR_ID_COSME_RANKING"))
    if has_key and (has_dataset or has_collector):
        return
    skip_reason = (
        "BRIGHTDATA_API_KEY and (BRIGHTDATA_DATASET_ID_COSME_RANKING or "
        "BRIGHTDATA_COLLECTOR_ID_COSME_RANKING) not set — skipping live "
        "BrightData tests."
    )
    skip_marker = pytest.mark.skip(reason=skip_reason)
    for item in items:
        if "brightdata" in item.keywords:
            item.add_marker(skip_marker)


def pytest_configure(config):
    """Register the ``brightdata`` marker so pytest does not warn about it."""
    config.addinivalue_line(
        "markers",
        "brightdata: test that hits the real BrightData API "
        "(skipped unless BRIGHTDATA_API_KEY and one of "
        "BRIGHTDATA_DATASET_ID_COSME_RANKING or "
        "BRIGHTDATA_COLLECTOR_ID_COSME_RANKING are set).",
    )
