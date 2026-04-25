"""Run the ``made_in_china`` middleware end-to-end.

Usage:
    python scripts/run_made_in_china.py
    python -m scripts.run_made_in_china

Edit ``INPUTS`` below to change the seed URLs / page budget before running.
``urls=None`` uses the middleware's default listing URL.

Result goes to ``scripts/last_run_made_in_china.json``.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts._runner import run  # noqa: E402

from gli_scrapers.made_in_china import get_result, trigger  # noqa: E402
from gli_scrapers.made_in_china import client as _client_module  # noqa: E402

INPUTS: dict = {
    "urls": None,
    "max_pages": 1,
}


async def main() -> int:
    return await run(
        name="made_in_china",
        trigger=trigger,
        get_result=get_result,
        inputs=INPUTS,
        env_hints=[
            "BRIGHTDATA_DATASET_ID_MADE_IN_CHINA",
            "BRIGHTDATA_COLLECTOR_ID_MADE_IN_CHINA",
        ],
        client_module=_client_module,
    )


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
