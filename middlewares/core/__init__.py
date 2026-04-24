"""Base building blocks shared across all scraper middlewares.

Exports:
    - ``BaseScraperClient``: thin async wrapper around BrightData (dual-mode:
      Datasets v3 + DCA legacy, selected via ``API_MODE``).
    - ``Envelope``: pydantic v2 model for the normalized response shape.
    - ``ScraperError`` / ``NORMALIZED_CODES``: typed error catalog.
    - ``BaseTransport`` / ``V3Transport`` / ``DCATransport``: transport
      strategies. Re-exported for subclasses and tests that need to inject
      a custom transport.

Per ``docs/fase3/README.md`` and ``docs/specs/memory.md`` Etapa 3:
the middleware layer is stateless (no DB, no cache, no ServiceRegistry).
Caller (the agents repo) owns retry / persistence / cache TTL.

For the dual-mode design (v3 + DCA) see
``docs/fase3/middleware-dual-mode.md``.
"""

from middlewares.core.client import BaseScraperClient
from middlewares.core.envelope import Envelope
from middlewares.core.errors import (
    NORMALIZED_CODES,
    ScraperError,
    error_payload,
)
from middlewares.core.transports import (
    BaseTransport,
    DCATransport,
    V3Transport,
)

__all__ = [
    "BaseScraperClient",
    "BaseTransport",
    "DCATransport",
    "Envelope",
    "NORMALIZED_CODES",
    "ScraperError",
    "V3Transport",
    "error_payload",
]
