"""Pytest config for the ``impi`` middleware tests.

- Forces ``asyncio_mode = "auto"`` (inherited from the root ``pytest.ini``) so
  tests declared as ``async def`` Just Work.
- Ensures the checked-in ``impi_scraper_mx`` package root is importable before
  each test, matching the production middleware's lazy import guard.
- Clears the in-process ``_RESULTS`` cache between tests so job_ids never
  leak across cases.
- Loads the hand-crafted snapshot as a ``snapshot_rows`` fixture.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from middlewares.impi.client import (
    _ensure_impi_scraper_mx_path,
    _reset_results_for_tests,
)

# Re-apply the package path guard at collection time of this conftest.
_ensure_impi_scraper_mx_path()

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SNAPSHOT_FIXTURE = FIXTURES_DIR / "impi_snapshot_s_demo01.json"


@pytest.fixture(autouse=True)
def _reset_results_cache() -> None:
    """Clear the module-level job store between tests.

    ``_RESULTS`` is process-scoped by design (see ``client.py``), so tests
    that share the interpreter can see each other's jobs without this
    auto-reset.
    """
    _reset_results_for_tests()
    yield
    _reset_results_for_tests()


@pytest.fixture
def snapshot_rows() -> list[dict]:
    """Load the canonical hand-crafted fixture as raw ``Marca`` dicts."""
    with SNAPSHOT_FIXTURE.open("r", encoding="utf-8") as fh:
        return json.load(fh)
