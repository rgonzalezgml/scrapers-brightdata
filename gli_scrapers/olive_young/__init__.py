"""``olive_young`` middleware — Python wrapper around the BrightData
``olive-young`` scraper (`scrapers/olive-young/`).

Public API (consumed by the agents repo):

    >>> from gli_scrapers.olive_young import trigger, get_result, TOOL_SCHEMA
    >>> job = await trigger({"regions": ["KR"], "max_products": 500})
    >>> res = await get_result(job["job_id"])

See ``docs/specs/scrapers/olive-young.md`` for the immutable schema (§2) and
the per-entity field catalog (§4-§10).

No fase 3 handoff exists yet for olive-young (by user instruction the
middleware is built first, then the handoff). The middleware follows the
shape of the canonical POC ``gli_scrapers/cosmetics_design/`` and sibling
``gli_scrapers/cosme/``.
"""

from gli_scrapers.olive_young.client import (
    OliveYoungClient,
    get_result,
    trigger,
)
from gli_scrapers.olive_young.models import (
    BrandRow,
    OliveYoungInputs,
    ProductRow,
    RankingRow,
)
from gli_scrapers.olive_young.tool_schema import TOOL_SCHEMA

__all__ = [
    "trigger",
    "get_result",
    "TOOL_SCHEMA",
    "OliveYoungClient",
    "OliveYoungInputs",
    "RankingRow",
    "ProductRow",
    "BrandRow",
]
