"""``alibaba`` middleware — Python wrapper around the BrightData ``alibaba``
scraper (`scrapers/alibaba/`).

Public API (consumed by the agents repo):

    >>> from gli_scrapers.alibaba import trigger, get_result, TOOL_SCHEMA
    >>> job = await trigger({"search_terms": ["industrial chemicals"]})
    >>> res = await get_result(job["job_id"])

See ``docs/specs/scrapers/alibaba.md`` for the immutable schema (§2) and the
per-entity field catalog (§4-§11). This is the first **Precios** category
middleware (vs cosmetics-design / cosme / olive-young which are I+D).

No fase 3 handoff exists for alibaba yet — per user instruction the middleware
is built first, then the handoff. The middleware follows the shape of the
canonical POCs ``gli_scrapers/cosmetics_design/`` and ``gli_scrapers/cosme/``.
"""

from gli_scrapers.alibaba.client import (
    AlibabaClient,
    get_result,
    trigger,
)
from gli_scrapers.alibaba.models import (
    AlibabaInputs,
    ProductRow,
)
from gli_scrapers.alibaba.tool_schema import TOOL_SCHEMA

__all__ = [
    "trigger",
    "get_result",
    "TOOL_SCHEMA",
    "AlibabaClient",
    "AlibabaInputs",
    "ProductRow",
]
