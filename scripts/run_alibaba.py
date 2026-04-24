"""Run the ``alibaba`` middleware end-to-end.

Usage:
    python scripts/run_alibaba.py
    python -m scripts.run_alibaba

Edit ``INPUTS`` below to change the search terms / page budget before running.
Result goes to ``scripts/last_run_alibaba.json``.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts._runner import run  # noqa: E402

from middlewares.alibaba import get_result, trigger  # noqa: E402
from middlewares.alibaba import client as _client_module  # noqa: E402

INPUTS: dict = {
    "search_terms": ["industrial chemicals"],
    "max_pages": 1,
}


async def main() -> int:
    return await run(
        name="alibaba",
        trigger=trigger,
        get_result=get_result,
        inputs=INPUTS,
        env_hints=[
            "BRIGHTDATA_DATASET_ID_ALIBABA",
            "BRIGHTDATA_COLLECTOR_ID_ALIBABA",
        ],
        client_module=_client_module,
    )


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
