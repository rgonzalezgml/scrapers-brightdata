"""``made_in_china`` middleware — Python wrapper around the BrightData
``made-in-china`` scraper (`scrapers/made-in-china/`).

Public API (consumed by the agents repo):

    >>> from middlewares.made_in_china import trigger, get_result, TOOL_SCHEMA
    >>> job = await trigger({"urls": ["https://www.made-in-china.com/products-search/hot-china-products/Industrial_Chemicals.html"], "max_pages": 3})
    >>> res = await get_result(job["job_id"])

See ``docs/specs/scrapers/made-in-china.md`` for the immutable schema (§2)
and the per-entity field catalog (§4-§6).

Per user instruction (2026-04-21) the task order was inverted: the middleware
is built first and the Fase 3 handoff ``docs/fase3/made-in-china-handoff.md``
will be written afterwards. The middleware follows the shape of the canonical
sibling ``middlewares/cosme/`` (multi-entity, dual-mode).
"""

from middlewares.made_in_china.client import (
    MadeInChinaClient,
    get_result,
    trigger,
)
from middlewares.made_in_china.models import (
    MadeInChinaInputs,
    ProductRow,
    SupplierRow,
)
from middlewares.made_in_china.tool_schema import TOOL_SCHEMA

__all__ = [
    "trigger",
    "get_result",
    "TOOL_SCHEMA",
    "MadeInChinaClient",
    "MadeInChinaInputs",
    "ProductRow",
    "SupplierRow",
]
