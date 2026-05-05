"""``cosme_new_arrivals`` middleware — Python wrapper around the BrightData
``cosme-new-arrivals`` scraper (``bd_scrapers/cosme-new-arrivals/``).

Public API (consumed by the agents repo):

    >>> from gli_scrapers.cosme_new_arrivals import trigger, get_result, TOOL_SCHEMA
    >>> job = await trigger({"year": 2026, "month": 5})
    >>> res = await get_result(job["job_id"])

See ``docs/fase3/cosme-new-arrivals-handoff.md`` for the contract.
The ``data[]`` shape is defined by the 9 fields emitted by the JS scraper
(spec §2): product_id, product_url, product_name, brand_id, brand_name,
brand_url, release_date, shop_url, scraped_at.
"""

from gli_scrapers.cosme_new_arrivals.client import (
    CosmeNewArrivalsClient,
    get_result,
    trigger,
)
from gli_scrapers.cosme_new_arrivals.models import (
    CosmeNewArrivalsInputs,
    NewProductRow,
)
from gli_scrapers.cosme_new_arrivals.tool_schema import TOOL_SCHEMA

__all__ = [
    "trigger",
    "get_result",
    "TOOL_SCHEMA",
    "CosmeNewArrivalsClient",
    "CosmeNewArrivalsInputs",
    "NewProductRow",
]
