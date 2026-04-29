"""``cosme_ranking_products`` middleware — Python wrapper around the BrightData
``cosme-ranking-products`` scraper (``bd_scrapers/cosme-ranking-products/``).

Public API (consumed by the agents repo):

    >>> from gli_scrapers.cosme_ranking_products import trigger, get_result, TOOL_SCHEMA
    >>> job = await trigger({"max_pages": 10})
    >>> res = await get_result(job["job_id"])

See ``docs/fase3/cosme-ranking-products-handoff.md`` for the contract.
The ``data[]`` shape is defined by the 29 fields emitted by the JS scraper.
"""

from gli_scrapers.cosme_ranking_products.client import (
    CosmeRankingClient,
    get_result,
    trigger,
)
from gli_scrapers.cosme_ranking_products.models import (
    CosmeRankingInputs,
    RankingEntry,
)
from gli_scrapers.cosme_ranking_products.tool_schema import TOOL_SCHEMA

__all__ = [
    "trigger",
    "get_result",
    "TOOL_SCHEMA",
    "CosmeRankingClient",
    "CosmeRankingInputs",
    "RankingEntry",
]
