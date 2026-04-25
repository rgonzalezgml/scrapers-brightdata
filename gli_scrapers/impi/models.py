"""Pydantic v2 models for the ``impi`` middleware.

Only :class:`IMPIInputs` lives here — the row shape for ``envelope["data"]``
is defined by :class:`impi_scraper_mx.models.Marca` (the standalone package) and
forwarded verbatim by the adapter, so there is no separate ``Row`` pydantic
model in this package.

Validation failure at trigger time surfaces as ``INVALID_INPUTS`` per
``docs/fase3/README.md`` — the portal is never called.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class IMPIInputs(BaseModel):
    """Public inputs accepted by ``trigger()``.

    These are the agent-facing knobs. They map 1:1 to
    :class:`impi_scraper_mx.models.SearchInputs` (with the addition of ``mode``
    which is a cache-TTL hint for the agents repo and does NOT change
    middleware behavior).
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    owner: Annotated[str, Field(min_length=1, max_length=200)] = "Genomma"
    """Titular (substring, server-side) to search in the IMPI portal. Default
    ``Genomma`` covers the Genomma Lab group."""

    expires_within_days: Annotated[int, Field(ge=1, le=3650)] = 90
    """Window of days from today (UTC) for the DATE_EXPIRY filter. The portal
    filters server-side; the middleware does not re-filter."""

    page_size: Annotated[int, Field(ge=1, le=200)] = 50
    """Page size requested to the portal's ``result`` endpoint. The scraper
    only fetches the first page — rows beyond ``page_size`` are flagged as
    ``paginated`` (see ``Marca.scraper_flags``) but not emitted."""

    mode: Literal["incremental", "full-refresh"] = "incremental"
    """Hint for the agents repo's cache TTL. The middleware treats both the
    same way (the portal always returns the full current window)."""
