"""``CosmeticsDesignClient`` — public ``trigger`` / ``get_result`` for the
``cosmetics-design`` BrightData scraper.

This module is the only place where:

    1. Public inputs (handoff §2.3) are translated into the JS scraper's
       runtime inputs (spec §10: ``max_pages``, ``supplier``).
    2. The raw BrightData snapshot rows are normalized into the envelope's
       ``data[]`` shape (spec §2 + §4).
    3. ``window_days`` and ``mode`` are applied (the JS scraper does NOT
       window; the spec §7 says windowing happens out-of-band).

The class is stateless and inherits the BrightData REST plumbing from
``BaseScraperClient``.

WHY translation lives here, not in the JS scraper:
    - The JS scraper's runtime inputs (``max_pages``, ``supplier``) are
      operational knobs (page-budget, attribution string).
    - The middleware's public inputs (``window_days``, ``max_articles``,
      ``region_filter``, ``mode``) are agent-facing semantics.
    - Mapping is non-trivial: ``max_articles`` becomes a ``max_pages``
      heuristic, ``window_days`` becomes post-hoc filtering, ``mode`` toggles
      whether we apply that filter, and ``region_filter`` is left for the
      agents repo (the scraper does not pre-filter; spec §3 §6).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import ValidationError

from middlewares.core.client import BaseScraperClient
from middlewares.core.envelope import Envelope, _utc_now_iso
from middlewares.core.errors import ScraperError, error_payload

from middlewares.cosmetics_design.config import (
    ARTICLES_PER_PAGE,
    CREDENTIAL_HINT,
    DEFAULT_ETA_SECONDS,
    DEFAULT_SUPPLIER,
    MAX_PAGES_HARD_CAP,
    SOURCE_LANDING_URL,
    SOURCE_NAME,
    resolve_mode_and_id,
)
from middlewares.cosmetics_design.models import (
    ARTICLE_FIELDS,
    ARTICLE_LIST_FIELDS,
    Article,
    CosmeticsDesignInputs,
)


# ---- Per-scraper error catalog extension ------------------------------------

# Adds the ``PAYWALL_SATURATION`` code listed in handoff §6 (cosmetics-design
# specific). We intentionally do NOT mutate the base catalog here; the
# extension is local to this module so other middlewares stay isolated.
COSMETICS_DESIGN_ERROR_CODES = {
    "PAYWALL_SATURATION": {
        "retriable": False,
        "description": (
            "More than 50% of emitted articles were behind a paywall — the "
            "site's metering tightened. Re-running will not help; escalate."
        ),
    },
}

# Threshold above which we surface PAYWALL_SATURATION instead of returning
# data. Per handoff §6 ("PAYWALL_SATURATION: >50% with paywall_hit").
_PAYWALL_SATURATION_THRESHOLD = 0.5


class CosmeticsDesignClient(BaseScraperClient):
    """Stateless wrapper around the cosmetics-design BrightData scraper.

    Dual-mode: the client picks the BrightData transport (Datasets v3 or DCA
    legacy) at construction time based on which env var the user populated.
    See ``docs/fase3/middleware-dual-mode.md`` and ``config.resolve_mode_and_id``.
    """

    SOURCE_NAME = SOURCE_NAME
    CREDENTIAL_HINT = CREDENTIAL_HINT
    # API_MODE intentionally left at the base default ("v3"). The effective
    # mode for cosmetics-design is decided per-instance via env vars, so we
    # pass ``api_mode=...`` explicitly to ``super().__init__`` instead of
    # pinning it at class level.

    def __init__(
        self,
        api_key: str | None = None,
        resource_id: str | None = None,
        *,
        api_mode: Any = None,
        http_client: Any = None,
        # Silent backwards-compat alias (spec §7 item 5 / apéndice A §3).
        dataset_id: str | None = None,
    ) -> None:
        # Resolve mode + resource id from env if caller did not pass overrides.
        # We don't crash on missing values — _ensure_credentials() does that
        # at trigger time so importing the module never fails (e.g. tests
        # running without env vars).
        if resource_id is None and dataset_id is not None:
            resource_id = dataset_id
        if api_mode is None or resource_id is None:
            env_mode, env_rid = resolve_mode_and_id()
            if api_mode is None:
                api_mode = env_mode
            if resource_id is None:
                resource_id = env_rid
        # Default to v3 if still unresolved so the attribute is a valid
        # Literal; the missing-credential error will fire at trigger time.
        if api_mode is None:
            api_mode = "v3"
        super().__init__(
            api_key=api_key,
            resource_id=resource_id,
            api_mode=api_mode,
            http_client=http_client,
        )

    # ---- input translation -------------------------------------------------

    def _build_brightdata_inputs(
        self, public_inputs: CosmeticsDesignInputs
    ) -> list[dict[str, Any]]:
        """Translate public inputs → JS scraper runtime inputs.

        The vendor interaction code currently deployed in the BrightData
        collector only declares ``input.url``; passing ``max_pages`` or
        ``supplier`` causes BrightData to reject the seed (shows as
        ``0/1 pages`` in the run log) because the input schema does not list
        them. Until v1 is deployed to the dashboard (spec §10), the middleware
        sends only ``url`` so the trigger matches the vendor's accepted shape.

        ``max_articles`` is still respected — applied post-download as a cap
        on emitted rows (see ``_build_envelope``). ``supplier`` falls back to
        the hardcoded default in the vendor. Once v1 is deployed, this can
        revert to sending all three fields.
        """
        seed: dict[str, Any] = {
            "url": SOURCE_LANDING_URL,
        }
        return [seed]

    # ---- envelope construction --------------------------------------------

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
            1. Skip non-article rows defensively (BrightData sometimes
               interleaves listing-stage rows; the cosmetics-design scraper
               emits only detail rows but we guard).
            2. Apply ``window_days`` filter (only when mode=incremental).
            3. Apply ``max_articles`` hard cap.
            4. Apply ``region_filter`` if requested.
            5. Coerce every row to the canonical ``Article`` shape — every
               key present, lists never null (spec §8).
            6. Compute ``meta`` counters.
        """
        started = started_at or _utc_now_iso()
        # Mode + window_days: filter rows whose display_date is older than
        # the cutoff. The scraper does not enforce the window itself
        # (spec §7), so we do it here.
        cutoff_iso: str | None = None
        if public_inputs.get("mode") == "incremental":
            cutoff = datetime.now(timezone.utc) - timedelta(
                days=int(public_inputs["window_days"])
            )
            cutoff_iso = cutoff.isoformat().replace("+00:00", "Z")

        emitted: list[dict[str, Any]] = []
        skipped_by_reason: dict[str, int] = {}
        paywalled = 0
        blocked = 0
        errors = 0

        for raw in rows:
            if not isinstance(raw, dict):
                _bump(skipped_by_reason, "non_dict_row")
                errors += 1
                continue

            # 1. Defensive: skip rows without article_id (e.g. listing stage
            #    leaked through, or scraper emitted a debug row).
            if not raw.get("article_id") and not raw.get("url"):
                _bump(skipped_by_reason, "no_article_id")
                continue

            # 2. Window filter (incremental only).
            if cutoff_iso is not None:
                disp = raw.get("display_date")
                if disp and isinstance(disp, str) and disp < cutoff_iso:
                    _bump(skipped_by_reason, "out_of_window")
                    continue

            # 3. region_filter (handoff §2.3 says agents repo applies it; we
            #    apply it here as a convenience so the envelope is already
            #    filtered when it lands in the agents repo's cache).
            region_filter = public_inputs.get("region_filter")
            if region_filter:
                tags = raw.get("region_tags") or []
                if region_filter not in tags:
                    _bump(skipped_by_reason, "region_filtered")
                    continue

            # 4. Coerce to canonical Article shape.
            normalized = _coerce_article(raw)

            if normalized.get("paywalled"):
                paywalled += 1

            # 5. Track scraper_flags counters as a debug aid.
            flags = normalized.get("scraper_flags") or []
            if "blocked" in flags:
                blocked += 1

            emitted.append(normalized)

            # 6. max_articles cap.
            if len(emitted) >= int(public_inputs["max_articles"]):
                _bump(skipped_by_reason, "max_articles_cap")
                break

        ended = ended_at or _utc_now_iso()

        meta: dict[str, Any] = {
            "rows": len(rows),
            "emitted": len(emitted),
            "skipped_by_reason": skipped_by_reason,
            "paywalled": paywalled,
            "blocked": blocked,
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

    # ---- public flow -------------------------------------------------------

    async def trigger(
        self, inputs: CosmeticsDesignInputs | dict[str, Any]
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

        # The transport normalizes BrightData's native status strings to our
        # 3-state contract — we only consume the normalized shape here.
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
            # Defensive: transport guarantees one of {running, ready, failed}
            # but if something weird leaks through, surface as running/0% so
            # the caller keeps polling rather than giving up.
            return {"status": "running", "progress_pct": 0}

        # State == ready: fetch snapshot and build envelope.
        try:
            rows = await self._fetch_snapshot(job_id)
        except ScraperError as e:
            return {"status": "failed", "error": error_payload(e)}

        # We do NOT have the original public_inputs cached (stateless!).
        # The agents repo MUST keep them alongside the job_id and pass them
        # back via build_envelope_for_rows() if it wants the full envelope.
        # For the get_result happy path we reconstruct with defaults; the
        # caller can re-shape using the public helper below.
        envelope = self.build_envelope_for_rows(rows, public_inputs={})
        return _maybe_paywall_saturation(envelope)

    # ---- public helper for the agents repo --------------------------------

    def build_envelope_for_rows(
        self,
        rows: list[dict[str, Any]],
        public_inputs: dict[str, Any] | CosmeticsDesignInputs,
    ) -> dict[str, Any]:
        """Build the envelope from already-fetched rows + caller's inputs.

        Useful when the caller (agents repo) cached the snapshot rows and
        public_inputs alongside the job_id and wants to re-derive the
        envelope without another API round-trip.
        """
        if isinstance(public_inputs, CosmeticsDesignInputs):
            inputs_dict = public_inputs.model_dump()
        else:
            # Apply pydantic defaults for any missing keys so meta logic
            # downstream gets sane values.
            try:
                inputs_dict = _validate_inputs(public_inputs).model_dump()
            except ScraperError:
                # If even the defaults fail validation, fall back to raw.
                inputs_dict = dict(public_inputs)
        envelope = self._build_envelope(rows, inputs_dict)
        return {"status": "done", "data": envelope}


# ---- module-level helpers ---------------------------------------------------


def _validate_inputs(
    inputs: CosmeticsDesignInputs | dict[str, Any] | None,
) -> CosmeticsDesignInputs:
    """Coerce/validate caller inputs. Raises ``ScraperError(INVALID_INPUTS)``."""
    if inputs is None:
        return CosmeticsDesignInputs()
    if isinstance(inputs, CosmeticsDesignInputs):
        return inputs
    if not isinstance(inputs, dict):
        raise ScraperError(
            "INVALID_INPUTS",
            f"inputs must be a dict or CosmeticsDesignInputs, got {type(inputs).__name__}.",
        )
    try:
        return CosmeticsDesignInputs(**inputs)
    except ValidationError as e:
        raise ScraperError(
            "INVALID_INPUTS",
            f"inputs validation failed: {e.errors(include_url=False)}",
        ) from e


def _coerce_article(raw: dict[str, Any]) -> dict[str, Any]:
    """Force every spec §2/§4 key to be present.

    We use the pydantic model to apply defaults / type coercion (lists never
    null, etc.), then dump to dict. ``extra="allow"`` on the model means any
    extra keys BrightData / future scraper versions emit are forwarded
    verbatim — defensive forward-compat.
    """
    # Pydantic raises on type mismatches; we want a permissive coercion that
    # never fails (the middleware never reinterprets data — bad rows surface
    # as-is). Build the dict manually and only validate via the model when
    # types match.
    out: dict[str, Any] = {}
    for key in ARTICLE_FIELDS:
        if key in raw:
            value = raw[key]
            # Force list-typed fields to be lists, never None.
            if key in ARTICLE_LIST_FIELDS:
                if value is None:
                    value = []
                elif not isinstance(value, list):
                    # Defensive: if BrightData returns a string where we
                    # expect a list, wrap it. Better than dropping data.
                    value = [value]
            out[key] = value
        else:
            out[key] = [] if key in ARTICLE_LIST_FIELDS else None

    # Forward any extra keys the JS scraper added (so future-proofed without
    # a middleware release).
    for key, value in raw.items():
        if key not in out:
            out[key] = value

    # Run through pydantic for shallow type validation; on failure, return
    # the raw-coerced dict so the row still surfaces.
    try:
        return Article(**out).model_dump()
    except ValidationError:
        return out


def _bump(d: dict[str, int], key: str) -> None:
    d[key] = d.get(key, 0) + 1


def _maybe_paywall_saturation(envelope_resp: dict[str, Any]) -> dict[str, Any]:
    """Surface PAYWALL_SATURATION if >50% of emitted rows hit the paywall.

    Per handoff §6. We do this *after* successful envelope construction so
    the caller can still inspect the data via the error.details.
    """
    if envelope_resp.get("status") != "done":
        return envelope_resp
    env = envelope_resp.get("data", {})
    meta = env.get("meta", {})
    emitted = int(meta.get("emitted", 0) or 0)
    paywalled = int(meta.get("paywalled", 0) or 0)
    if emitted > 0 and (paywalled / emitted) > _PAYWALL_SATURATION_THRESHOLD:
        return {
            "status": "failed",
            "error": {
                "code": "PAYWALL_SATURATION",
                "message": (
                    f"{paywalled}/{emitted} emitted articles are paywalled "
                    f"(> {int(_PAYWALL_SATURATION_THRESHOLD * 100)}% threshold)."
                ),
                "retriable": False,
                "details": {"emitted": emitted, "paywalled": paywalled},
            },
        }
    return envelope_resp


# ---- module-level public entry points ---------------------------------------

# These are the names the agents repo imports:
#     from middlewares.cosmetics_design import trigger, get_result, TOOL_SCHEMA
#
# We instantiate a fresh client per call (stateless) so concurrent callers do
# not share an httpx connection pool unexpectedly. If the agents repo wants
# pooling, it should construct ``CosmeticsDesignClient`` directly with a
# shared httpx.AsyncClient.


async def trigger(
    inputs: CosmeticsDesignInputs | dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Module-level convenience for ``CosmeticsDesignClient().trigger(...)``."""
    client = CosmeticsDesignClient()
    try:
        return await client.trigger(inputs or {})
    finally:
        await client.aclose()


async def get_result(job_id: str) -> dict[str, Any]:
    """Module-level convenience for ``CosmeticsDesignClient().get_result(...)``."""
    client = CosmeticsDesignClient()
    try:
        return await client.get_result(job_id)
    finally:
        await client.aclose()
