"""``cosme`` middleware — Python wrapper around the BrightData ``cosme``
scraper (`scrapers/cosme/`).

Public API (consumed by the agents repo):

    >>> from middlewares.cosme import trigger, get_result, TOOL_SCHEMA
    >>> job = await trigger({"year": 2025, "max_products": 500})
    >>> res = await get_result(job["job_id"])

See ``docs/specs/scrapers/cosme.md`` for the immutable schema (§2) and the
per-entity field catalog (§4-§10).

No fase 3 handoff exists yet for cosme (by user instruction the middleware is
built first, then the handoff). The middleware follows the shape of the
canonical POC ``middlewares/cosmetics_design/``.
"""

from middlewares.cosme.client import (
    CosmeClient,
    get_result,
    trigger,
)
from middlewares.cosme.models import (
    BrandRow,
    CosmeInputs,
    ProductRow,
    RankingRow,
)
from middlewares.cosme.tool_schema import TOOL_SCHEMA

__all__ = [
    "trigger",
    "get_result",
    "TOOL_SCHEMA",
    "CosmeClient",
    "CosmeInputs",
    "ProductRow",
    "RankingRow",
    "BrandRow",
]
