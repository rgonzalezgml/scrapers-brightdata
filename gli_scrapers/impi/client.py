"""``IMPIMiddlewareClient`` — adapter around the standalone ``impi_scraper_mx``
Python package.

Atypical vs the rest of ``gli_scrapers/``:

    * The wrapped scraper is a local Python package (``impi_scraper_mx``) that
      hits the IMPI Mexico portal directly with ``httpx``. There is no
      BrightData involved, therefore NO ``BaseScraperClient``, NO transports,
      NO dataset/collector id, NO dual-mode.
    * ``impi_scraper_mx.IMPIClient`` is synchronous. The ``trigger`` coroutine
      runs it via ``asyncio.to_thread`` to avoid blocking the event loop.
    * There is no background job — the portal responds in seconds. ``trigger``
      performs the full round-trip, builds the envelope, stores it under a
      ``job_id``, and returns ``eta_seconds=0``. ``get_result`` is a cache
      lookup.
    * Storage is in-process (``_RESULTS``). Lifetime = process lifetime. That
      matches how the harness already handles session state.

Public API (contract consumed by the agents harness):

    >>> from gli_scrapers.impi import trigger, get_result
    >>> job = await trigger({"owner": "Genomma", "expires_within_days": 90})
    >>> res = await get_result(job["job_id"])

The error catalog is the base one from ``gli_scrapers.core.errors``; portal
errors map to ``BRIGHTDATA_ERROR`` (generic upstream-failure bucket) even
though there is no BrightData in the loop — the semantics match (upstream
data source unreachable/broken).
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path
from typing import Any, Callable

from pydantic import ValidationError

from gli_scrapers.core.envelope import Envelope, _utc_now_iso

from gli_scrapers.impi.config import DEFAULT_ETA_SECONDS, SOURCE_NAME
from gli_scrapers.impi.models import IMPIInputs


# -----------------------------------------------------------------------------
# Local package import guard
# -----------------------------------------------------------------------------
#
# The standalone package lives in ``/workspace/impi_scraper_mx``. In local
# script runs it may not be installed editable, so add that directory once
# before lazy imports. This keeps the middleware usable from a fresh checkout.
# -----------------------------------------------------------------------------


def _ensure_impi_scraper_mx_path() -> None:
    """Make the checked-in ``impi_scraper_mx`` package importable.

    Idempotent: subsequent calls are a no-op once the package root is already
    present on ``sys.path``.
    """
    package_root = str(Path(__file__).resolve().parents[1] / "impi_mx")
    if package_root not in sys.path:
        sys.path.insert(0, package_root)


# -----------------------------------------------------------------------------
# In-process job storage
# -----------------------------------------------------------------------------
#
# Maps ``job_id -> {"status": "done"|"failed", "data"?: envelope, "error"?: dict}``.
# Populated by ``trigger``; read by ``get_result``. Module-level so that the
# harness, which instantiates fresh ``IMPIMiddlewareClient`` per call for
# statelessness (see ``agent_harness/registry.py``), can still correlate the
# two halves of the call via ``job_id``.
#
# Lifetime: the current process. When uvicorn restarts, in-flight job_ids are
# lost — same behavior as the harness session store.
# -----------------------------------------------------------------------------

_RESULTS: dict[str, dict[str, Any]] = {}


def _reset_results_for_tests() -> None:
    """Test helper: clear the in-process job store.

    Exported with a ``_`` prefix so it does not leak into ``__all__``; tests
    call it from their fixtures to avoid cross-test sangrado.
    """
    _RESULTS.clear()


# -----------------------------------------------------------------------------
# Lazy import of the wrapped package
# -----------------------------------------------------------------------------
#
# ``impi_scraper_mx`` is checked into this repo. We import it lazily
# inside the methods that need it so that importing ``gli_scrapers.impi`` at
# test-collection time never fails even on environments where the package is
# not installed.
# -----------------------------------------------------------------------------


def _default_client_factory() -> Any:
    """Return a fresh ``impi_scraper_mx.IMPIClient`` instance.

    Imported lazily so that ``from gli_scrapers.impi import trigger`` works even
    when ``impi_scraper_mx`` is missing (the failure surfaces at trigger
    time as ``BRIGHTDATA_ERROR``, not at import time).
    """
    _ensure_impi_scraper_mx_path()
    from impi_scraper_mx import IMPIClient  # local import (see module docstring)

    return IMPIClient()


def _impi_error_types() -> tuple[type[BaseException], ...]:
    """Return the tuple of ``impi_scraper_mx`` exception classes to catch.

    Lazy import keeps the module importable when the wrapped package is
    absent; we fall back to an empty tuple so the except clause still works
    (nothing will match specifically — the broader ``except Exception`` below
    will catch instead).
    """
    _ensure_impi_scraper_mx_path()
    try:
        from impi_scraper_mx.errors import IMPIError

        return (IMPIError,)
    except Exception:  # noqa: BLE001 — defensive, see docstring.
        return ()


# -----------------------------------------------------------------------------
# Client
# -----------------------------------------------------------------------------


class IMPIMiddlewareClient:
    """Stateless adapter that translates ``IMPIInputs`` → portal search →
    normalized envelope.

    Not a subclass of ``BaseScraperClient``: the BrightData plumbing is not
    applicable here. We still expose ``build_envelope_for_rows`` so that the
    harness' fixture mode can reuse the same envelope builder when it is
    given pre-recorded rows.
    """

    def __init__(
        self,
        client_factory: Callable[[], Any] | None = None,
    ) -> None:
        """``client_factory`` lets tests inject a mock ``IMPIClient`` without
        touching ``impi_scraper_mx`` directly. Each trigger invocation calls the
        factory to get a fresh instance (mirroring the standalone package's
        "one client per search" usage in its CLI)."""
        self._client_factory = client_factory or _default_client_factory

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def trigger(
        self, inputs: IMPIInputs | dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Validate inputs, run the scraper synchronously in a worker thread,
        store the envelope, return ``{job_id, eta_seconds}``.

        Never raises. All failure paths land as ``{job_id, eta_seconds}``
        pointing at a pre-populated failure entry in ``_RESULTS``, so that
        ``get_result`` can surface the error uniformly with the BrightData
        middlewares (same public shape).
        """
        job_id = f"local_impi_{uuid.uuid4().hex[:16]}"

        # ---- 1. Validate public inputs ----------------------------------
        try:
            validated = _validate_inputs(inputs)
        except _InputValidationError as e:
            _RESULTS[job_id] = {
                "status": "failed",
                "error": {
                    "code": "INVALID_INPUTS",
                    "message": str(e),
                    "retriable": False,
                },
            }
            return {"job_id": job_id, "eta_seconds": DEFAULT_ETA_SECONDS}

        # ---- 2. Run the sync scraper off-loop ---------------------------
        # Lazy import of SearchInputs so module import stays cheap.
        _ensure_impi_scraper_mx_path()
        try:
            from impi_scraper_mx import SearchInputs
        except Exception as e:  # noqa: BLE001 — missing editable install.
            _RESULTS[job_id] = {
                "status": "failed",
                "error": {
                    "code": "BRIGHTDATA_ERROR",
                    "message": f"impi_scraper_mx package unavailable: {type(e).__name__}: {e}",
                    "retriable": False,
                },
            }
            return {"job_id": job_id, "eta_seconds": DEFAULT_ETA_SECONDS}

        impi_inputs = SearchInputs(
            owner=validated.owner,
            expires_within_days=validated.expires_within_days,
            page_size=validated.page_size,
        )

        started_at = _utc_now_iso()
        impi_errors = _impi_error_types()
        try:
            scraper = self._client_factory()
            result = await asyncio.to_thread(scraper.search, impi_inputs)
        except impi_errors as e:
            # Known scraper failure (XSRF missing, upstream 5xx, timeout...).
            _RESULTS[job_id] = {
                "status": "failed",
                "error": {
                    "code": "BRIGHTDATA_ERROR",
                    "message": f"IMPI local scraper error: {type(e).__name__}: {e}",
                    "retriable": True,
                },
            }
            return {"job_id": job_id, "eta_seconds": DEFAULT_ETA_SECONDS}
        except Exception as e:  # noqa: BLE001 — last-resort bucket.
            _RESULTS[job_id] = {
                "status": "failed",
                "error": {
                    "code": "BRIGHTDATA_ERROR",
                    "message": f"Unexpected error in impi_scraper_mx: {type(e).__name__}: {e}",
                    "retriable": False,
                },
            }
            return {"job_id": job_id, "eta_seconds": DEFAULT_ETA_SECONDS}
        ended_at = _utc_now_iso()

        # ---- 3. Normalize rows + envelope -------------------------------
        rows = [m.model_dump() for m in result.rows]
        total_in_portal = getattr(result, "total", None)
        fetched = getattr(result, "fetched", len(rows))
        paginated = bool(
            getattr(
                result,
                "paginated",
                total_in_portal is not None and fetched < total_in_portal,
            )
        )
        envelope = self._build_envelope(
            rows,
            public_inputs=validated.model_dump(),
            started_at=started_at,
            ended_at=ended_at,
            search_id=result.search_id,
            total_in_portal=total_in_portal,
            paginated=paginated,
        )
        _RESULTS[job_id] = {"status": "done", "data": envelope}
        return {"job_id": job_id, "eta_seconds": DEFAULT_ETA_SECONDS}

    async def get_result(self, job_id: str) -> dict[str, Any]:
        """Look up the previously-triggered job.

        Never raises. Returns the stored ``{"status": ..., ...}`` record, or
        an ``INVALID_INPUTS`` failure for unknown ids (same shape the other
        middlewares return when asked about a non-existent snapshot).
        """
        if not isinstance(job_id, str) or not job_id:
            return {
                "status": "failed",
                "error": {
                    "code": "INVALID_INPUTS",
                    "message": "job_id must be a non-empty string.",
                    "retriable": False,
                },
            }
        out = _RESULTS.get(job_id)
        if out is None:
            return {
                "status": "failed",
                "error": {
                    "code": "INVALID_INPUTS",
                    "message": f"unknown job_id: {job_id!r}",
                    "retriable": False,
                },
            }
        return out

    # ------------------------------------------------------------------
    # Envelope builder — also used by the harness fixture mode
    # ------------------------------------------------------------------

    def _build_envelope(
        self,
        rows: list[dict[str, Any]],
        public_inputs: dict[str, Any] | IMPIInputs | None = None,
        *,
        started_at: str | None = None,
        ended_at: str | None = None,
        search_id: str | None = None,
        total_in_portal: int | None = None,
        paginated: bool = False,
    ) -> dict[str, Any]:
        """Build the raw envelope dict (without the ``{"status": "done",
        "data": ...}`` wrapper).

        Returns the canonical base shape:

            {
              "source": "impi",
              "scraped_at": <ISO8601 UTC>,
              "inputs":  <public inputs with defaults applied>,
              "data":    <list of Marca dicts>,
              "meta":    {"rows", "emitted", "skipped_by_reason", "errors",
                          "total_in_portal", "paginated", "search_id",
                          "started_at", "ended_at"}
            }
        """
        # Normalize public_inputs: apply pydantic defaults for any missing
        # fields so the envelope always shows the resolved inputs.
        if isinstance(public_inputs, IMPIInputs):
            inputs_dict = public_inputs.model_dump()
        elif public_inputs is None:
            inputs_dict = IMPIInputs().model_dump()
        else:
            try:
                inputs_dict = IMPIInputs.model_validate(public_inputs).model_dump()
            except ValidationError:
                # Never crash the envelope builder on input re-validation —
                # we were called *after* a successful run, so downgrading
                # to the raw dict keeps the row data accessible.
                inputs_dict = dict(public_inputs)

        now = _utc_now_iso()
        envelope = Envelope(
            source=SOURCE_NAME,
            scraped_at=started_at or now,
            inputs=inputs_dict,
            data=list(rows),
            meta={
                "rows": len(rows),
                "emitted": len(rows),
                "skipped_by_reason": {},
                "errors": 0,
                "total_in_portal": total_in_portal,
                "paginated": paginated,
                "search_id": search_id,
                "started_at": started_at or now,
                "ended_at": ended_at or now,
            },
        )
        return envelope.model_dump()

    def build_envelope_for_rows(
        self,
        rows: list[dict[str, Any]],
        public_inputs: dict[str, Any] | IMPIInputs | None = None,
        *,
        started_at: str | None = None,
        ended_at: str | None = None,
        search_id: str | None = None,
        total_in_portal: int | None = None,
        paginated: bool = False,
    ) -> dict[str, Any]:
        """Public helper — build the same envelope as ``trigger`` would and
        wrap it in the ``{"status": "done", "data": <envelope>}`` shape the
        agents harness expects.

        Called by the harness fixture-mode dispatcher
        (``agent_harness.registry._envelope_for_rows``) when it loads a
        canned snapshot from disk.
        """
        envelope = self._build_envelope(
            rows,
            public_inputs=public_inputs,
            started_at=started_at,
            ended_at=ended_at,
            search_id=search_id,
            total_in_portal=total_in_portal,
            paginated=paginated,
        )
        return {"status": "done", "data": envelope}


# -----------------------------------------------------------------------------
# Internal validation helper
# -----------------------------------------------------------------------------


class _InputValidationError(Exception):
    """Internal sentinel — converted to ``INVALID_INPUTS`` by ``trigger``."""


def _validate_inputs(
    inputs: IMPIInputs | dict[str, Any] | None,
) -> IMPIInputs:
    """Coerce/validate caller inputs. Raises :class:`_InputValidationError`
    on failure.

    Accepts ``None`` (→ defaults), ``IMPIInputs`` (passthrough), or ``dict``
    (validated). Any other type is rejected — we refuse to guess.
    """
    if inputs is None:
        return IMPIInputs()
    if isinstance(inputs, IMPIInputs):
        return inputs
    if not isinstance(inputs, dict):
        raise _InputValidationError(
            f"inputs must be a dict or IMPIInputs, got {type(inputs).__name__}."
        )
    try:
        return IMPIInputs(**inputs)
    except ValidationError as e:
        raise _InputValidationError(
            f"inputs validation failed: {e.errors(include_url=False)}"
        ) from e


# -----------------------------------------------------------------------------
# Module-level entry points (contract imported by the harness)
# -----------------------------------------------------------------------------


async def trigger(
    inputs: IMPIInputs | dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Module-level convenience for ``IMPIMiddlewareClient().trigger(...)``.

    The agents harness imports this function directly (see
    ``agent_harness/registry.py::_discover_middlewares``), so the name and
    signature must stay stable.
    """
    return await IMPIMiddlewareClient().trigger(inputs)


async def get_result(job_id: str) -> dict[str, Any]:
    """Module-level convenience for ``IMPIMiddlewareClient().get_result(...)``."""
    return await IMPIMiddlewareClient().get_result(job_id)
