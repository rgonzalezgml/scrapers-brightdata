"""Abstract base for BrightData transports.

Each concrete transport wraps three BrightData operations:

    1. ``trigger``: fire a run, return the BrightData-side opaque job id.
    2. ``poll``: ask BrightData whether the run is done; returns a
       cross-transport normalized dict (``status`` in ``running|ready|failed``).
    3. ``download``: fetch the final rows.

Concrete transports raise :class:`TransportError` with a **project-level
normalized code** (from ``NORMALIZED_CODES``); the base client re-raises as
:class:`ScraperError`. The transport does **not** depend on the catalog
module — the code is a plain string the base client trusts.

Transports are stateless: a single instance can serve any number of
concurrent calls. The base client caches one instance per ``API_MODE``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Literal

import httpx

# ---------------------------------------------------------------------------
# Internal transport error
# ---------------------------------------------------------------------------

# Normalized poll status as seen by the base client (cross-transport).
NormalizedStatus = Literal["running", "ready", "failed"]


class TransportError(Exception):
    """Typed error raised by a transport.

    The ``code`` is a string pulled from the project's ``NORMALIZED_CODES``
    catalog (e.g. ``"BRIGHTDATA_ERROR"``, ``"INVALID_INPUTS"``, ``"SITE_BLOCKED"``).
    The base client maps 1:1 to :class:`ScraperError` — transports never
    invent codes.
    """

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


# Legacy alias preserved so internal imports can use the leading-underscore
# convention the spec mentions (§7 item 2). Both names point at the same class.
_TransportError = TransportError


# ---------------------------------------------------------------------------
# ABC
# ---------------------------------------------------------------------------


class BaseTransport(ABC):
    """Interface every concrete transport satisfies.

    All methods are keyword-only at the call-site and receive explicit
    dependencies (``api_key``, ``http`` client). The base client injects
    these — transports themselves hold no state.
    """

    #: Human-readable mode tag (``"v3"`` / ``"dca"``). Used for error messages.
    MODE: str = ""

    @abstractmethod
    async def trigger(
        self,
        *,
        api_key: str,
        resource_id: str,
        inputs: list[dict[str, Any]],
        http: httpx.AsyncClient,
        apicore: str,
    ) -> str:
        """Fire a BrightData run.

        ``resource_id`` is ``gd_...`` for v3 and ``c_...`` for DCA. The transport
        treats it as an opaque string (no prefix validation).

        Returns the BrightData-side opaque job id (``snapshot_id`` for v3,
        ``collection_id`` for DCA). The base client surfaces it upward as a
        plain ``job_id`` string — callers never learn which transport is in use.
        """

    @abstractmethod
    async def poll(
        self,
        *,
        api_key: str,
        job_id: str,
        http: httpx.AsyncClient,
        apicore: str,
    ) -> dict[str, Any]:
        """Poll BrightData for progress.

        Returns a normalized dict:

            {"status": "running", "progress_pct": int | None, "raw": {...}}
            {"status": "ready",   "raw": {...}}
            {"status": "failed",  "message": str, "raw": {...}}

        The ``raw`` key is the unaltered payload (useful for debugging and
        for transports that want to avoid an extra round-trip in
        :meth:`download`). The base client only reads ``status`` and
        ``progress_pct``.
        """

    @abstractmethod
    async def download(
        self,
        *,
        api_key: str,
        job_id: str,
        http: httpx.AsyncClient,
        apicore: str,
    ) -> list[dict[str, Any]]:
        """Fetch the final rows for a finished job. Returns ``list[dict]``."""


# ---------------------------------------------------------------------------
# Small HTTP helpers shared by concrete transports
# ---------------------------------------------------------------------------


def auth_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def safe_text(resp: httpx.Response, cap: int = 500) -> str:
    """Truncated, log-safe representation of an HTTP body."""
    try:
        text = resp.text
    except Exception:  # pragma: no cover — defensive
        return "<unreadable>"
    return text[:cap] + ("…" if len(text) > cap else "")
