"""Run the ``impi`` middleware end-to-end.

Usage:
    python scripts/run_impi.py
    python -m scripts.run_impi

``impi`` wraps the local ``impi_scraper_mx`` package (no BrightData); ``trigger``
runs the search synchronously and ``get_result`` is just a cache lookup, so
the first poll returns ``done``.

Result goes to ``scripts/last_run_impi.json``.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts._runner import run  # noqa: E402

from gli_scrapers.impi import get_result, trigger  # noqa: E402

INPUTS: dict = {
    "owner": "Genomma",
    "expires_within_days": 90,
    "page_size": 50,
}


async def main() -> int:
    return await run(
        name="impi",
        trigger=trigger,
        get_result=get_result,
        inputs=INPUTS,
        poll_interval_s=1,
        max_wait_min=2,
    )


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
