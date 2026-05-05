"""``OliveYoungNewArrivalsClient`` — public ``trigger`` / ``get_result`` for
the BrightData ``olive-young-new-arrivals`` scraper.

This module is the only place where:

    1. Public inputs (spec §2 databrightdata + §4-§9 genomma lab) are
       translated into the JS scraper's runtime inputs — a single seed URL.
    2. Raw BrightData rows are normalized into the envelope's ``data[]``
       shape — each row coerced to the canonical :class:`NewArrivalRow`
       shape with every §2 field present (``null`` if absent).

Inherits BrightData REST plumbing (trigger, poll, download) from
``BaseScraperClient``. Dual-mode (v3 + DCA legacy) is picked at construction
time via env vars — see :func:`gli_scrapers.olive_young_new_arrivals.config.resolve_mode_and_id`.

No inputs are required — the scraper always fetches the complete new-arrivals
catalogue from ``global.oliveyoung.com/display/page/new-arrivals``.
"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from gli_scrapers.core.client import BaseScraperClient
from gli_scrapers.core.envelope import Envelope, _utc_now_iso
from gli_scrapers.core.errors import ScraperError, error_payload

from gli_scrapers.olive_young_new_arrivals.config import (
    CREDENTIAL_HINT,
    DEFAULT_ETA_SECONDS,
    NEW_ARRIVALS_URL,
    SOURCE_NAME,
    resolve_mode_and_id,
)
from gli_scrapers.olive_young_new_arrivals.models import (
    NEW_ARRIVAL_FIELDS,
    NEW_ARRIVAL_LIST_FIELDS,
    NewArrivalRow,
    OliveYoungNewArrivalsInputs,
)


class OliveYoungNewArrivalsClient(BaseScraperClient):
    """Stateless wrapper around the olive-young-new-arrivals BrightData scraper.

    Dual-mode: picks Datasets v3 or DCA legacy at construction time based on
    which env var the user populated.
    """

    SOURCE_NAME = SOURCE_NAME
    CREDENTIAL_HINT = CREDENTIAL_HINT

    def __init__(
        self,
        api_key: str | None = None,
        resource_id: str | None = None,
        *,
        api_mode: Any = None,
        http_client: Any = None,
        # Silent backwards-compat alias.
        dataset_id: str | None = None,
    ) -> None:
        if resource_id is None and dataset_id is not None:
            resource_id = dataset_id
        if api_mode is None or resource_id is None:
            env_mode, env_rid = resolve_mode_and_id()
            if api_mode is None:
                api_mode = env_mode
            if resource_id is None:
                resource_id = env_rid
        # Default to v3 if still unresolved; missing-credential error fires
        # at trigger time (never at import time).
        if api_mode is None:
            api_mode = "v3"
        super().__init__(
            api_key=api_key,
            resource_id=resource_id,
            api_mode=api_mode,
            http_client=http_client,
        )

    # ---- input translation --------------------------------------------------

    def _build_brightdata_inputs(
        self, public_inputs: OliveYoungNewArrivalsInputs
    ) -> list[dict[str, Any]]:
        """Translate public inputs → JS scraper runtime seed.

        The scraper takes no parameterisation — a single seed URL is enough
        for BrightData to start the run (spec §2 handoff: "Seed a BrightData:
        [{'url': 'https://global.oliveyoung.com/display/page/new-arrivals'}]").
        """
        return [{"url": NEW_ARRIVALS_URL}]

    # ---- envelope construction ----------------------------------------------

    def _build_envelope(
        self,
        rows: list[dict[str, Any]],
        public_inputs: dict[str, Any],
        *,
        started_at: str | None = None,
        ended_at: str | None = None,
    ) -> dict[str, Any]:
        """Normalize raw BrightData rows into the project envelope.

        Steps:
            1. Skip non-dict rows defensively.
            2. Coerce each row to the canonical :class:`NewArrivalRow` shape —
               every §2 strict key present, ``null`` where missing.
            3. Compute ``meta`` counters.
        """
        started = started_at or _utc_now_iso()

        emitted: list[dict[str, Any]] = []
        errors = 0
        skipped_by_reason: dict[str, int] = {}

        for raw in rows:
            if not isinstance(raw, dict):
                _bump(skipped_by_reason, "non_dict_row")
                errors += 1
                continue

            normalized = _coerce_new_arrival(raw)
            emitted.append(normalized)

        ended = ended_at or _utc_now_iso()

        meta: dict[str, Any] = {
            "rows": len(rows),
            "emitted": len(emitted),
            "errors": errors,
            "skipped_by_reason": skipped_by_reason,
            "started_at": started,
            "ended_at": ended,
        }

        envelope = Envelope(
            source=SOURCE_NAME,
            inputs=public_inputs,
            data=emitted,
            meta=meta,
        )
        return envelope.model_dump()

    # ---- public flow --------------------------------------------------------

    async def trigger(
        self, inputs: OliveYoungNewArrivalsInputs | dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Validate inputs, fire the BrightData trigger, return ``{job_id, eta_seconds}``.

        Never raises — failures land in the response shape:
            {"status": "failed", "error": {...}}
        """
        try:
            validated = _validate_inputs(inputs)
        except ScraperError as e:
            return {"status": "failed", "error": error_payload(e)}

        try:
            bd_inputs = self._build_brightdata_inputs(validated)
            snapshot_id = await self._trigger_brightdata(bd_inputs)
        except ScraperError as e:
            return {"status": "failed", "error": error_payload(e)}

        return {
            "job_id": snapshot_id,
            "eta_seconds": DEFAULT_ETA_SECONDS,
        }

    async def get_result(self, job_id: str) -> dict[str, Any]:
        """Poll progress; if ready, fetch and normalize the snapshot.

        Never raises. Returns one of:
            {"status": "running", "progress_pct": int}
            {"status": "done",    "data": <envelope>}
            {"status": "failed",  "error": {...}}
        """
        if not job_id or not isinstance(job_id, str):
            return {
                "status": "failed",
                "error": error_payload(
                    ScraperError("INVALID_INPUTS", "job_id must be a non-empty string.")
                ),
            }

        try:
            progress = await self._get_progress(job_id)
        except ScraperError as e:
            return {"status": "failed", "error": error_payload(e)}

        norm_status = progress.get("status")
        if norm_status == "running":
            pct = progress.get("progress_pct")
            if not isinstance(pct, int):
                pct = 0
            return {"status": "running", "progress_pct": pct}
        if norm_status == "failed":
            msg = progress.get("message") or "BrightData reported failure."
            return {
                "status": "failed",
                "error": error_payload(
                    ScraperError("BRIGHTDATA_ERROR", str(msg))
                ),
            }
        if norm_status != "ready":
            # Defensive: unknown status → keep polling.
            return {"status": "running", "progress_pct": 0}

        # State == ready: fetch snapshot and build envelope.
        try:
            rows = await self._fetch_snapshot(job_id)
        except ScraperError as e:
            return {"status": "failed", "error": error_payload(e)}

        envelope = self.build_envelope_for_rows(rows, public_inputs={})
        return envelope

    # ---- public helper for the agents repo ---------------------------------

    def build_envelope_for_rows(
        self,
        rows: list[dict[str, Any]],
        public_inputs: dict[str, Any] | OliveYoungNewArrivalsInputs,
    ) -> dict[str, Any]:
        """Build the envelope from already-fetched rows + caller's inputs.

        Useful when the caller (agents repo) cached the snapshot rows and
        public_inputs alongside the job_id and wants to re-derive the
        envelope without another API round-trip.
        """
        if isinstance(public_inputs, OliveYoungNewArrivalsInputs):
            inputs_dict = public_inputs.model_dump()
        else:
            try:
                inputs_dict = _validate_inputs(public_inputs).model_dump()
            except ScraperError:
                inputs_dict = dict(public_inputs)
        envelope = self._build_envelope(rows, inputs_dict)
        return {"status": "done", "data": envelope}


# ---- module-level helpers ---------------------------------------------------


def _validate_inputs(
    inputs: OliveYoungNewArrivalsInputs | dict[str, Any] | None,
) -> OliveYoungNewArrivalsInputs:
    """Coerce/validate caller inputs. Raises ``ScraperError(INVALID_INPUTS)``."""
    if inputs is None:
        return OliveYoungNewArrivalsInputs()
    if isinstance(inputs, OliveYoungNewArrivalsInputs):
        return inputs
    if not isinstance(inputs, dict):
        raise ScraperError(
            "INVALID_INPUTS",
            f"inputs must be a dict or OliveYoungNewArrivalsInputs, got {type(inputs).__name__}.",
        )
    try:
        return OliveYoungNewArrivalsInputs(**inputs)
    except ValidationError as e:
        raise ScraperError(
            "INVALID_INPUTS",
            f"inputs validation failed: {e.errors(include_url=False)}",
        ) from e


def _coerce_new_arrival(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize a raw BrightData row to the canonical :class:`NewArrivalRow` shape.

    Every §2 field is always present in the output (``None`` if absent in the
    raw row). No aliases needed — the JS scraper emits snake_case keys matching
    the spec §2 field names directly.
    """
    out: dict[str, Any] = {}
    for key in NEW_ARRIVAL_FIELDS:
        if key in NEW_ARRIVAL_LIST_FIELDS:
            # No list fields for this entity — unreachable but kept for
            # consistency with the sibling middlewares.
            val = raw.get(key)
            out[key] = val if isinstance(val, list) else ([] if val is None else [val])
        else:
            out[key] = raw.get(key)

    # Forward extra keys verbatim (pydantic extra="allow" forwards them in
    # model_dump; here we do the same before model validation).
    for key, value in raw.items():
        if key not in out:
            out[key] = value

    try:
        return NewArrivalRow(**out).model_dump()
    except ValidationError:
        return out


def _bump(d: dict[str, int], key: str) -> None:
    d[key] = d.get(key, 0) + 1


# ---- module-level public entry points ----------------------------------------

# Names the agents repo imports:
#     from gli_scrapers.olive_young_new_arrivals import trigger, get_result, TOOL_SCHEMA


async def trigger(
    inputs: OliveYoungNewArrivalsInputs | dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Module-level convenience for ``OliveYoungNewArrivalsClient().trigger(...)``."""
    client = OliveYoungNewArrivalsClient()
    try:
        return await client.trigger(inputs or {})
    finally:
        await client.aclose()


async def get_result(job_id: str) -> dict[str, Any]:
    """Module-level convenience for ``OliveYoungNewArrivalsClient().get_result(...)``."""
    client = OliveYoungNewArrivalsClient()
    try:
        return await client.get_result(job_id)
    finally:
        await client.aclose()
