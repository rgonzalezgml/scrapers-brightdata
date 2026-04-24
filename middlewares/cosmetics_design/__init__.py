"""``cosmetics_design`` middleware — Python wrapper around the BrightData
``cosmetics-design`` scraper (`scrapers/cosmetics-design/`).

Public API (consumed by the agents repo):

    >>> from middlewares.cosmetics_design import trigger, get_result, TOOL_SCHEMA
    >>> job = await trigger({"window_days": 30})
    >>> res = await get_result(job["job_id"])

See ``docs/fase3/cosmetics-design-handoff.md`` for the contract and
``docs/specs/scrapers/cosmetics-design.md`` for the immutable ``data[]`` shape.
"""

from middlewares.cosmetics_design.client import (
    CosmeticsDesignClient,
    get_result,
    trigger,
)
from middlewares.cosmetics_design.models import (
    Article,
    CosmeticsDesignInputs,
)
from middlewares.cosmetics_design.tool_schema import TOOL_SCHEMA

__all__ = [
    "trigger",
    "get_result",
    "TOOL_SCHEMA",
    "CosmeticsDesignClient",
    "CosmeticsDesignInputs",
    "Article",
]
