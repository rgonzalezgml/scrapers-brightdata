"""Run the ``indiamart`` middleware end-to-end.

Usage:
    python scripts/run_indiamart.py
    python -m scripts.run_indiamart

Edit ``INPUTS`` below to change the MCAT slugs / product budget before
running. Result goes to ``scripts/last_run_indiamart.json``.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts._runner import run  # noqa: E402

from gli_scrapers.indiamart import get_result, trigger  # noqa: E402
from gli_scrapers.indiamart import client as _client_module  # noqa: E402

INPUTS: dict = {
    "mcat_slugs": ["caustic-soda"],
    "include_industry_hubs": False,
    "max_products": 20,
    "max_suppliers": 5,
}


async def main() -> int:
    return await run(
        name="indiamart",
        trigger=trigger,
        get_result=get_result,
        inputs=INPUTS,
        env_hints=[
            "BRIGHTDATA_DATASET_ID_INDIAMART",
            "BRIGHTDATA_COLLECTOR_ID_INDIAMART",
        ],
        client_module=_client_module,
    )


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
