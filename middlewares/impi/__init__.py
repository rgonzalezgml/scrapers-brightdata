"""``impi`` middleware — Python adapter around the standalone
``impi_scraper_mx`` package (``/workspace/impi_scraper_mx/``).

Unlike the other middlewares in this directory, ``impi`` does NOT wrap a
BrightData Scraper Studio scraper. It wraps a local Python package that
talks to the IMPI Mexico portal directly. Consequence: there is no
BrightData trigger/poll cycle — ``trigger`` runs the scraper synchronously
in a worker thread and stores the envelope; ``get_result`` is a cache
lookup. See ``middlewares/impi/client.py`` for the rationale.

Public API (consumed by the agents repo / harness):

    >>> from middlewares.impi import trigger, get_result, TOOL_SCHEMA
    >>> job = await trigger({"owner": "Genomma", "expires_within_days": 90})
    >>> res = await get_result(job["job_id"])

See ``docs/specs/scrapers/impi.md`` for the schema of each row in
``envelope["data"]`` (delegated to :class:`impi_scraper_mx.models.Marca`).
"""

from middlewares.impi.client import (
    IMPIMiddlewareClient,
    get_result,
    trigger,
)
from middlewares.impi.models import IMPIInputs
from middlewares.impi.tool_schema import TOOL_SCHEMA

__all__ = [
    "trigger",
    "get_result",
    "TOOL_SCHEMA",
    "IMPIMiddlewareClient",
    "IMPIInputs",
]
