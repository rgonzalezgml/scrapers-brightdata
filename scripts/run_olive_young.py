"""Run the ``olive_young`` middleware end-to-end.

Usage:
    python scripts/run_olive_young.py
    python -m scripts.run_olive_young

Edit ``INPUTS`` below to change the regions / product budget before running.
Result goes to ``scripts/last_run_olive_young.json``.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts._runner import run  # noqa: E402

from middlewares.olive_young import get_result, trigger  # noqa: E402
from middlewares.olive_young import client as _client_module  # noqa: E402

INPUTS: dict = {
    "region": "kr",
    "max_products": 20,
}


async def main() -> int:
    return await run(
        name="olive_young",
        trigger=trigger,
        get_result=get_result,
        inputs=INPUTS,
        env_hints=[
            "BRIGHTDATA_DATASET_ID_OLIVE_YOUNG",
            "BRIGHTDATA_COLLECTOR_ID_OLIVE_YOUNG",
        ],
        client_module=_client_module,
    )


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
