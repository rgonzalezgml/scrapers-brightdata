"""Run the ``cosmetics_design`` middleware end-to-end.

Usage:
    python scripts/run_cosmetics_design.py
    python -m scripts.run_cosmetics_design

Edit ``INPUTS`` below to change the budget / filters before running.
Result goes to ``scripts/last_run_cosmetics_design.json``.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts._runner import run  # noqa: E402

from middlewares.cosmetics_design import get_result, trigger  # noqa: E402
from middlewares.cosmetics_design import client as _client_module  # noqa: E402

INPUTS: dict = {
    "window_days": 7,
    "max_articles": 5,
    "mode": "full-refresh",
}


async def main() -> int:
    return await run(
        name="cosmetics_design",
        trigger=trigger,
        get_result=get_result,
        inputs=INPUTS,
        env_hints=[
            "BRIGHTDATA_DATASET_ID_COSMETICS_DESIGN",
            "BRIGHTDATA_COLLECTOR_ID_COSMETICS_DESIGN",
        ],
        client_module=_client_module,
    )


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
