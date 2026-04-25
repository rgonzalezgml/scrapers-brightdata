"""Transport layer for the middleware base client.

Two concrete implementations share one interface:

- ``V3Transport``: BrightData **Datasets v3** API (``/datasets/v3/*``,
  ``gd_...`` ids). Modern API; what Scraper Studio publishes.
- ``DCATransport``: BrightData **Data Collectors Archive** legacy API
  (``/dca/*``, ``c_...`` / ``j_...`` ids). Still supported by BrightData;
  used by scrapers that have not been migrated to Studio yet.

The :class:`BaseScraperClient` picks one at construction time via its
``API_MODE`` class attribute (``"v3"`` by default). See
``docs/fase3/middleware-dual-mode.md`` for the design.
"""

from __future__ import annotations

from gli_scrapers.core.transports.base import (
    BaseTransport,
    TransportError,
    _TransportError,
)
from gli_scrapers.core.transports.dca import DCATransport
from gli_scrapers.core.transports.v3 import V3Transport

__all__ = [
    "BaseTransport",
    "DCATransport",
    "TransportError",
    "V3Transport",
    "_TransportError",
]
