"""Pytest config for the made_in_china middleware tests.

- Forces ``asyncio_mode = "auto"`` so tests written as ``async def`` Just Work.
- Resolves the fixtures dir once.
- Skips live BrightData tests when env vars are unset. Dual-mode: a live
  test is runnable if EITHER ``BRIGHTDATA_DATASET_ID_MADE_IN_CHINA`` (v3)
  OR ``BRIGHTDATA_COLLECTOR_ID_MADE_IN_CHINA`` (DCA) is populated alongside
  ``BRIGHTDATA_API_KEY``. See ``docs/fase3/middleware-dual-mode.md`` §5.3.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"

# Hand-crafted snapshot mirroring the shape that
# ``scrapers/made-in-china/sc_code/parser_code_v3.js`` emits for product +
# supplier pages. See the README in the fixtures dir for construction notes.
SNAPSHOT_FIXTURE = FIXTURES_DIR / "made_in_china_snapshot_s_demo01.json"


@pytest.fixture
def snapshot_rows() -> list[dict]:
    """Load the canonical fixture as a list of raw BrightData rows."""
    import json

    with SNAPSHOT_FIXTURE.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def pytest_collection_modifyitems(config, items):
    """Skip ``@pytest.mark.brightdata`` tests when env vars are missing."""
    has_key = bool(os.getenv("BRIGHTDATA_API_KEY"))
    has_dataset = bool(os.getenv("BRIGHTDATA_DATASET_ID_MADE_IN_CHINA"))
    has_collector = bool(os.getenv("BRIGHTDATA_COLLECTOR_ID_MADE_IN_CHINA"))
    if has_key and (has_dataset or has_collector):
        return
    skip_reason = (
        "BRIGHTDATA_API_KEY and (BRIGHTDATA_DATASET_ID_MADE_IN_CHINA or "
        "BRIGHTDATA_COLLECTOR_ID_MADE_IN_CHINA) not set — skipping live "
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
        "BRIGHTDATA_DATASET_ID_MADE_IN_CHINA or "
        "BRIGHTDATA_COLLECTOR_ID_MADE_IN_CHINA are set).",
    )
