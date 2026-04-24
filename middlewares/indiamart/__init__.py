"""``indiamart`` middleware — Python wrapper around the BrightData
``indiamart`` scraper (`scrapers/indiamart/`).

Public API (consumed by the agents repo):

    >>> from middlewares.indiamart import trigger, get_result, TOOL_SCHEMA
    >>> job = await trigger({"mcat_slugs": ["caustic-soda"], "max_products": 200})
    >>> res = await get_result(job["job_id"])

indiamart is the third Precios-category scraper alongside alibaba and
made-in-china — same schema shape (``price_min_usd``, ``moq_quantity``,
``supplier_*``) so downstream can compare three sources without mapping.
``data[]`` is multi-entity: ``"product"`` + ``"supplier"`` rows share the
array, discriminated by ``entity``.

See ``docs/specs/scrapers/indiamart.md`` for the immutable schema (§2) and
the per-entity field catalog (§4-§9).

No fase 3 handoff exists yet for indiamart (by user instruction the
middleware is built first, then the handoff). The middleware follows the
shape of the canonical POC ``middlewares/cosmetics_design/`` and the
multi-entity pattern of ``middlewares/cosme/``.
"""

from middlewares.indiamart.client import (
    IndiamartClient,
    get_result,
    trigger,
)
from middlewares.indiamart.models import (
    IndiamartInputs,
    ProductRow,
    SupplierRow,
)
from middlewares.indiamart.tool_schema import TOOL_SCHEMA

__all__ = [
    "trigger",
    "get_result",
    "TOOL_SCHEMA",
    "IndiamartClient",
    "IndiamartInputs",
    "ProductRow",
    "SupplierRow",
]
