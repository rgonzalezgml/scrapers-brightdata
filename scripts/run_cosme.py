"""Run the ``cosme`` middleware end-to-end.

Usage:
    python scripts/run_cosme.py
    python -m scripts.run_cosme

Edit ``INPUTS`` below to change the year / product / category budget before
running. Result goes to ``scripts/last_run_cosme.json``.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts._runner import run  # noqa: E402

from gli_scrapers.cosme import get_result, trigger  # noqa: E402
from gli_scrapers.cosme import client as _client_module  # noqa: E402

INPUTS: dict = {
    "year": 2025,
    "category": "skincare",
    "max_categories": 10,   # → crawl_limit=10 en el seed (alineado con curl del dashboard)
    "max_products": 20,     # cap post-download del middleware, no se envía a BrightData
}


async def main() -> int:
    return await run(
        name="cosme",
        trigger=trigger,
        get_result=get_result,
        inputs=INPUTS,
        env_hints=[
            "BRIGHTDATA_DATASET_ID_COSME",
            "BRIGHTDATA_COLLECTOR_ID_COSME",
        ],
        client_module=_client_module,
    )


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
