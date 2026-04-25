"""Normalized error catalog shared across all gli_scrapers.

The middleware never decides retry/alarm policy — it only tags failures with
a stable code. The agents repo decides what to do with ``retriable``.

See ``docs/fase3/<scraper>-handoff.md`` §6 for the per-scraper catalog. Each
scraper handoff may *extend* this base catalog (e.g. cosmetics-design adds
``PAYWALL_SATURATION``); never *redefine* an existing code.

Dual-mode note (Datasets v3 + DCA legacy)
-----------------------------------------

These codes are transport-agnostic — both the v3 and DCA transports
(``gli_scrapers/core/transports/``) raise using the same catalog. Per
``docs/fase3/middleware-dual-mode.md`` §4.3, the HTTP status → code mapping is:

========================  =====================  ============
condition                 code                   applies to
========================  =====================  ============
transport/5xx             ``BRIGHTDATA_ERROR``   both
451 at trigger            ``SITE_BLOCKED``       both
401 / 403                 ``INVALID_INPUTS``     both
4xx at trigger            ``INVALID_INPUTS``     both
404 at poll               ``INVALID_INPUTS``     both
4xx at poll/download      ``BRIGHTDATA_ERROR``   both
malformed JSON            ``BRIGHTDATA_ERROR``   both
missing snapshot_id       ``BRIGHTDATA_ERROR``   v3
missing collection_id     ``BRIGHTDATA_ERROR``   dca
DCA "expired" / "deleted" ``INVALID_INPUTS``     dca
poll → "failed"           ``BRIGHTDATA_ERROR``   both
========================  =====================  ============

``TIMEOUT`` and ``STRUCTURE_CHANGED`` are **not** raised by the transport —
they come from the consumer (wall-time budget) and from per-scraper
subclasses (shape validation) respectively.
"""

from __future__ import annotations

from typing import TypedDict


class NormalizedCode(TypedDict):
    retriable: bool
    description: str


# Base codes — every middleware uses these. Per-scraper packages may add more
# entries to their own local extension of this dict (without mutating the base).
NORMALIZED_CODES: dict[str, NormalizedCode] = {
    "SITE_BLOCKED": {
        "retriable": False,
        "description": "BrightData reports sustained block from the source site.",
    },
    "STRUCTURE_CHANGED": {
        "retriable": False,
        "description": "Parser failures exceed tolerance — site DOM/JSON changed.",
    },
    "TIMEOUT": {
        "retriable": True,
        "description": "Wall-time budget exhausted without final state.",
    },
    "INVALID_INPUTS": {
        "retriable": False,
        "description": "Pydantic validation failed; BrightData was NOT called.",
    },
    "BRIGHTDATA_ERROR": {
        "retriable": True,
        "description": "BrightData API returned 5xx or transport error.",
    },
    "UNKNOWN": {
        "retriable": False,
        "description": "Uncategorized failure — investigate before retrying.",
    },
}


class ScraperError(Exception):
    """Raised internally by client helpers; never escapes the public API.

    The public ``trigger`` / ``get_result`` functions catch this and convert it
    to ``{"status": "failed", "error": {...}}`` via :func:`error_payload`.
    """

    def __init__(
        self,
        code: str,
        message: str,
        *,
        retriable: bool | None = None,
        details: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        # If caller did not pass an explicit override, look up the catalog.
        if retriable is None:
            retriable = NORMALIZED_CODES.get(code, NORMALIZED_CODES["UNKNOWN"])[
                "retriable"
            ]
        self.retriable = retriable
        self.details = details or {}


def error_payload(err: ScraperError) -> dict:
    """Serialize a :class:`ScraperError` into the public failure shape."""
    payload = {
        "code": err.code,
        "message": err.message,
        "retriable": err.retriable,
    }
    if err.details:
        payload["details"] = err.details
    return payload
