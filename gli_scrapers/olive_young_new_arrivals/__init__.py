"""``olive_young_new_arrivals`` middleware — Python wrapper around the BrightData
``olive-young-new-arrivals`` scraper (``bd_scrapers/olive-young-new-arrivals/``).

Public API (consumed by the agents repo):

    >>> from gli_scrapers.olive_young_new_arrivals import trigger, get_result, TOOL_SCHEMA
    >>> job = await trigger({})
    >>> res = await get_result(job["job_id"])

See ``docs/specs/scrapers/olive_young_new_arrivals.md`` for the immutable schema
(§2) and the per-entity field catalog (§4-§9).

No inputs required — the scraper takes the full catalogue from
``global.oliveyoung.com/display/page/new-arrivals``.
"""

from gli_scrapers.olive_young_new_arrivals.client import (
    OliveYoungNewArrivalsClient,
    get_result,
    trigger,
)
from gli_scrapers.olive_young_new_arrivals.models import (
    NewArrivalRow,
    OliveYoungNewArrivalsInputs,
)
from gli_scrapers.olive_young_new_arrivals.tool_schema import TOOL_SCHEMA

__all__ = [
    "trigger",
    "get_result",
    "TOOL_SCHEMA",
    "OliveYoungNewArrivalsClient",
    "OliveYoungNewArrivalsInputs",
    "NewArrivalRow",
]
