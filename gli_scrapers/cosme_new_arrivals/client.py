"""``CosmeNewArrivalsClient`` — public ``trigger`` / ``get_result`` for the
``cosme-new-arrivals`` BrightData scraper.

This module is the only place where:

    1. Public inputs (year, month) are translated into the JS scraper's seed
       URL ``https://www.cosme.net/calendar/index/year/{year}/month/{month:02d}``.
    2. The raw BrightData snapshot rows are normalized into the envelope's
       ``data[]`` shape (9 fields per row, spec §2).

The class is stateless and inherits the BrightData REST plumbing from
``BaseScraperClient``.
"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from gli_scrapers.core.client import BaseScraperClient
from gli_scrapers.core.envelope import Envelope, _utc_now_iso
from gli_scrapers.core.errors import ScraperError, error_payload

from gli_scrapers.cosme_new_arrivals.config import (
    CREDENTIAL_HINT,
    DEFAULT_ETA_SECONDS,
    SOURCE_NAME,
    resolve_mode_and_id,
)
from gli_scrapers.cosme_new_arrivals.models import (
    NEW_PRODUCT_FIELDS,
    NEW_PRODUCT_LIST_FIELDS,
    CosmeNewArrivalsInputs,
    NewProductRow,
)


class CosmeNewArrivalsClient(BaseScraperClient):
    """Stateless wrapper around the cosme-new-arrivals BrightData scraper.

    Dual-mode: picks the BrightData transport (Datasets v3 or DCA legacy) at
    construction time based on which env var the user populated.
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
        self, public_inputs: CosmeNewArrivalsInputs
    ) -> list[dict[str, Any]]:
        """Translate public inputs → JS scraper seed.

        DCA legacy: el collector tiene URL fija en el dashboard — enviar [{}].
        Datasets v3: se puede pasar url/year/month al scraper.
        """
        from datetime import date
        today = date.today()
        year  = public_inputs.year  or today.year
        month = public_inputs.month or today.month

        if self._api_mode == "dca":
            # Collector DCA requiere solo url base (sin year/month en path)
            return [{"url": "https://www.cosme.net/calendar"}]

        seed: dict[str, Any] = {
            "url": (
                f"https://www.cosme.net/calendar/index/year/"
                f"{year}/month/{month:02d}"
            ),
            "year":  year,
            "month": month,
        }
        return [seed]

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
            1. Skip non-dict rows (BrightData edge case).
            2. Coerce every row to the canonical ``NewProductRow`` shape —
               every key present, scalars default to null.
            3. Compute ``meta`` counters.
        """
        started = started_at or _utc_now_iso()

        emitted: list[dict[str, Any]] = []
        errors = 0

        for raw in rows:
            if not isinstance(raw, dict):
                errors += 1
                continue
            normalized = _coerce_entry(raw)
            emitted.append(normalized)

        ended = ended_at or _utc_now_iso()

        meta: dict[str, Any] = {
            "rows": len(rows),
            "emitted": len(emitted),
            "errors": errors,
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
        self, inputs: CosmeNewArrivalsInputs | dict[str, Any]
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
            return {"status": "running", "progress_pct": 0}

        # State == ready: fetch snapshot and build envelope.
        try:
            rows = await self._fetch_snapshot(job_id)
        except ScraperError as e:
            return {"status": "failed", "error": error_payload(e)}

        envelope = self.build_envelope_for_rows(rows, public_inputs={})
        return envelope

    # ---- public helper for the agents repo ----------------------------------

    def build_envelope_for_rows(
        self,
        rows: list[dict[str, Any]],
        public_inputs: dict[str, Any] | CosmeNewArrivalsInputs,
    ) -> dict[str, Any]:
        """Build the envelope from already-fetched rows + caller's inputs.

        Useful when the caller (agents repo) cached the snapshot rows and
        public_inputs alongside the job_id and wants to re-derive the
        envelope without another API round-trip.
        """
        if isinstance(public_inputs, CosmeNewArrivalsInputs):
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
    inputs: CosmeNewArrivalsInputs | dict[str, Any] | None,
) -> CosmeNewArrivalsInputs:
    """Coerce/validate caller inputs. Raises ``ScraperError(INVALID_INPUTS)``."""
    if inputs is None:
        raise ScraperError(
            "INVALID_INPUTS",
            "inputs are required: provide 'year' (2020-2030) and 'month' (1-12).",
        )
    if isinstance(inputs, CosmeNewArrivalsInputs):
        return inputs
    if not isinstance(inputs, dict):
        raise ScraperError(
            "INVALID_INPUTS",
            f"inputs must be a dict or CosmeNewArrivalsInputs, got {type(inputs).__name__}.",
        )
    try:
        return CosmeNewArrivalsInputs(**inputs)
    except ValidationError as e:
        raise ScraperError(
            "INVALID_INPUTS",
            f"inputs validation failed: {e.errors(include_url=False)}",
        ) from e


def _coerce_entry(raw: dict[str, Any]) -> dict[str, Any]:
    """Force every spec field key to be present.

    Uses the pydantic model to apply defaults / type coercion. ``extra="allow"``
    on the model means any extra keys BrightData emits are forwarded verbatim.
    """
    out: dict[str, Any] = {}
    for key in NEW_PRODUCT_FIELDS:
        if key in raw:
            value = raw[key]
            if key in NEW_PRODUCT_LIST_FIELDS:
                if value is None:
                    value = []
                elif not isinstance(value, list):
                    value = [value]
            out[key] = value
        else:
            out[key] = [] if key in NEW_PRODUCT_LIST_FIELDS else None

    # Forward any extra keys the JS scraper added.
    for key, value in raw.items():
        if key not in out:
            out[key] = value

    try:
        return NewProductRow(**out).model_dump()
    except ValidationError:
        return out


# ---- module-level public entry points ---------------------------------------

# These are the names the agents repo imports:
#     from gli_scrapers.cosme_new_arrivals import trigger, get_result, TOOL_SCHEMA
#
# A fresh client is instantiated per call (stateless). If the agents repo
# wants connection pooling it should construct ``CosmeNewArrivalsClient`` directly
# with a shared httpx.AsyncClient.


async def trigger(
    inputs: CosmeNewArrivalsInputs | dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Module-level convenience for ``CosmeNewArrivalsClient().trigger(...)``."""
    client = CosmeNewArrivalsClient()
    try:
        return await client.trigger(inputs or {})
    finally:
        await client.aclose()


async def get_result(job_id: str) -> dict[str, Any]:
    """Module-level convenience for ``CosmeNewArrivalsClient().get_result(...)``."""
    client = CosmeNewArrivalsClient()
    try:
        return await client.get_result(job_id)
    finally:
        await client.aclose()
