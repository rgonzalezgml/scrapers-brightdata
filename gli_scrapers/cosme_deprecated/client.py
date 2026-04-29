"""``CosmeClient`` — public ``trigger`` / ``get_result`` for the BrightData
``cosme`` scraper (``scrapers/cosme/``).

This module is the only place where:

    1. Public inputs (spec §2 databrightdata + §10 genomma lab) are
       translated into the JS scraper's Stage 1 runtime inputs
       (``input.award_year``, ``input.category``, ``input.crawl_limit``).
    2. Raw BrightData rows (multi-entity: product + ranking + brand) are
       normalized into the envelope's heterogeneous ``data[]`` shape —
       each row tagged with the ``entity`` discriminator and matching the
       §2 / §4 / §5 field catalog exactly.
    3. Post-download filters (``max_products``, ``include_rankings``,
       ``include_brands``) are applied. The scraper does NOT enforce these
       — we do it here (spec §7).

Inherits BrightData REST plumbing (trigger, poll, download) from
``BaseScraperClient``. Dual-mode (v3 + DCA legacy) is picked at construction
time via env vars — see :func:`gli_scrapers.cosme.config.resolve_mode_and_id`.

WHY the input translation lives here, not in the JS scraper:
    - Stage 1 ``input.award_year`` / ``input.category`` / ``input.crawl_limit``
      are *operational* knobs (what year to crawl, which slugs, how many).
    - The public inputs (``year``, ``max_products``, ``include_rankings``,
      ``mode``) are *agent-facing* semantics.
    - ``max_products`` is post-download clipping (the scraper has no single
      knob for it — its hard cap is 3000 unique in spec §7).
"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from gli_scrapers.core.client import BaseScraperClient
from gli_scrapers.core.envelope import Envelope, _utc_now_iso
from gli_scrapers.core.errors import ScraperError, error_payload

from gli_scrapers.cosme.config import (
    BLOCK_SATURATION_THRESHOLD,
    CREDENTIAL_HINT,
    DEFAULT_ETA_SECONDS,
    DEFAULT_YEAR,
    SOURCE_NAME,
    archive_root_url,
    resolve_mode_and_id,
)
from gli_scrapers.cosme.models import (
    BRAND_ALIASES,
    BRAND_FIELDS,
    BRAND_LIST_FIELDS,
    PRODUCT_ALIASES,
    PRODUCT_FIELDS,
    PRODUCT_LIST_FIELDS,
    RANKING_ALIASES,
    RANKING_FIELDS,
    RANKING_LIST_FIELDS,
    BrandRow,
    CosmeInputs,
    ProductRow,
    RankingRow,
)

# ---- Per-scraper error catalog extension ------------------------------------

# Adds a BLOCK_SATURATION code that mirrors cosmetics-design's
# PAYWALL_SATURATION but tuned to cosme's failure mode: the @cosme.net
# site aggressively blocks proxied IPs (spec §2 of genomma lab: "ご利用の
# 環境からはアクセスできません" + body<10KB). If a majority of emitted
# product rows hit the block, the run is useless — escalate.
#
# We extend locally (do NOT mutate the base catalog in ``core/errors.py``).
COSME_ERROR_CODES: dict[str, dict[str, Any]] = {
    "BLOCK_SATURATION": {
        "retriable": False,
        "description": (
            "More than 50% of emitted product rows carry 'rate_limit_blocked' "
            "or 'name_extract_failed' — the @cosme.net block page was served "
            "after 3 retries. Re-running is unlikely to help; rotate the "
            "residential JP session pool and re-trigger."
        ),
    },
}


class CosmeClient(BaseScraperClient):
    """Stateless wrapper around the cosme BrightData scraper.

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
        # Silent backwards-compat alias (spec §7 item 5 / apéndice A §3).
        dataset_id: str | None = None,
    ) -> None:
        # Resolve mode + resource id from env if caller did not pass overrides.
        # We don't crash on missing values — ``_ensure_credentials()`` does
        # that at trigger time so importing the module never fails.
        if resource_id is None and dataset_id is not None:
            resource_id = dataset_id
        if api_mode is None or resource_id is None:
            env_mode, env_rid = resolve_mode_and_id()
            if api_mode is None:
                api_mode = env_mode
            if resource_id is None:
                resource_id = env_rid
        # Default to v3 if still unresolved so the attribute is a valid
        # Literal; the missing-credential error fires at trigger time.
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
        self, public_inputs: CosmeInputs
    ) -> list[dict[str, Any]]:
        """Translate public inputs → Stage 1 JS scraper runtime inputs.

        The Stage 1 interaction code reads:

            - ``input.url`` — optional; if absent, builds the URL from
              ``input.award_year`` via ``archive/{year}/``.
            - ``input.award_year`` — number, defaulted by the JS code to
              ``new Date().getFullYear()`` when missing (with a
              ``award_year_defaulted`` warn).
            - ``input.category`` — case-insensitive substring filter on
              category URLs (optional).
            - ``input.crawl_limit`` — maximum number of categories to
              follow (optional).

        We emit ONE seed — the archive root for the requested year. The JS
        scraper expands it into grand/hall/rookie + category URLs itself
        (spec §10 Stage 1).
        """
        # Alineado con el payload que el dashboard de BrightData exhibe como
        # "Example Request" del collector cosme (2026-04-23):
        #   [{"url":"https://www.cosme.net/bestcosme/archive/{year}/grand/",
        #     "category":"skincare","crawl_limit":10}]
        # Diferencias vs el builder previo:
        #   - URL termina en `/grand/` (antes: `/{year}/`). El JS del dashboard
        #     arranca directo en el award_group Grand sin discovery de grupos.
        #   - `award_year` removido del seed (el curl no lo incluye; el JS lo
        #     deriva del path con la regex `/bestcosme\/archive\/(\d+)\//`).
        year = public_inputs.year if public_inputs.year is not None else DEFAULT_YEAR
        seed: dict[str, Any] = {
            "url": f"{archive_root_url(year)}grand/",
            "crawl_limit": int(public_inputs.max_categories),
        }
        # if public_inputs.category:
        #     seed["category"] = public_inputs.category
        seed["category"] = public_inputs.category or "skincare"

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
            1. Skip non-dict rows defensively (shape errors).
            2. Classify each row into its entity (product / ranking / brand).
            3. Apply aliases (spec §2 short names on the wire).
            4. Coerce every row to the canonical entity shape — every §2
               strict key present, lists never null (spec §8).
            5. Drop ``ranking`` / ``brand`` rows if disabled by inputs.
            6. Apply ``max_products`` cap on product rows.
            7. Compute ``meta`` counters.

        Rows that cannot be classified are counted under
        ``meta.skipped_by_reason`` but never dropped silently.
        """
        started = started_at or _utc_now_iso()

        include_rankings = bool(public_inputs.get("include_rankings", True))
        include_brands = bool(public_inputs.get("include_brands", True))
        max_products = int(public_inputs.get("max_products") or 1000)

        emitted: list[dict[str, Any]] = []
        skipped_by_reason: dict[str, int] = {}
        counts = {"product": 0, "ranking": 0, "brand": 0}
        blocked = 0
        errors = 0

        products_emitted = 0

        for raw in rows:
            if not isinstance(raw, dict):
                _bump(skipped_by_reason, "non_dict_row")
                errors += 1
                continue

            entity = _classify_entity(raw)
            if entity is None:
                _bump(skipped_by_reason, "unknown_entity")
                continue

            if entity == "ranking" and not include_rankings:
                _bump(skipped_by_reason, "rankings_disabled")
                continue
            if entity == "brand" and not include_brands:
                _bump(skipped_by_reason, "brands_disabled")
                continue

            if entity == "product":
                normalized = _coerce_product(raw)
                # Track block / extraction-failure flags as a debug aid
                # (feeds the BLOCK_SATURATION check).
                flags = normalized.get("scraper_flags") or []
                if "rate_limit_blocked" in flags or "name_extract_failed" in flags:
                    blocked += 1
                # max_products cap — applied only to product rows (rankings
                # and brands are small reference tables; the cap does not
                # apply to them per spec §7).
                if products_emitted >= max_products:
                    _bump(skipped_by_reason, "max_products_cap")
                    continue
                products_emitted += 1
            elif entity == "ranking":
                normalized = _coerce_ranking(raw)
            else:  # brand
                normalized = _coerce_brand(raw)

            counts[entity] += 1
            emitted.append(normalized)

        ended = ended_at or _utc_now_iso()

        meta: dict[str, Any] = {
            "rows": len(rows),
            "emitted": len(emitted),
            "emitted_by_entity": counts,
            "skipped_by_reason": skipped_by_reason,
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
        self, inputs: CosmeInputs | dict[str, Any]
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
            # Defensive: transport guarantees one of {running, ready, failed}
            # but if something weird leaks through, surface as running/0% so
            # the caller keeps polling rather than giving up.
            return {"status": "running", "progress_pct": 0}

        # State == ready: fetch snapshot and build envelope.
        try:
            rows = await self._fetch_snapshot(job_id)
        except ScraperError as e:
            return {"status": "failed", "error": error_payload(e)}

        # Stateless: we do NOT cache the original public_inputs. The agents
        # repo keeps them alongside the job_id and can re-derive the envelope
        # via ``build_envelope_for_rows``. Here we use the model defaults.
        envelope = self.build_envelope_for_rows(rows, public_inputs={})
        return _maybe_block_saturation(envelope)

    # ---- public helper for the agents repo --------------------------------

    def build_envelope_for_rows(
        self,
        rows: list[dict[str, Any]],
        public_inputs: dict[str, Any] | CosmeInputs,
    ) -> dict[str, Any]:
        """Build the envelope from already-fetched rows + caller's inputs.

        Useful when the caller (agents repo) cached the snapshot rows and
        public_inputs alongside the job_id and wants to re-derive the
        envelope without another API round-trip.
        """
        if isinstance(public_inputs, CosmeInputs):
            inputs_dict = public_inputs.model_dump()
        else:
            try:
                inputs_dict = _validate_inputs(public_inputs).model_dump()
            except ScraperError:
                # If even the defaults fail validation, fall back to raw so
                # we never drop data on the floor.
                inputs_dict = dict(public_inputs)
        envelope = self._build_envelope(rows, inputs_dict)
        return {"status": "done", "data": envelope}


# ---- module-level helpers ---------------------------------------------------


def _validate_inputs(
    inputs: CosmeInputs | dict[str, Any] | None,
) -> CosmeInputs:
    """Coerce/validate caller inputs. Raises ``ScraperError(INVALID_INPUTS)``."""
    if inputs is None:
        return CosmeInputs()
    if isinstance(inputs, CosmeInputs):
        return inputs
    if not isinstance(inputs, dict):
        raise ScraperError(
            "INVALID_INPUTS",
            f"inputs must be a dict or CosmeInputs, got {type(inputs).__name__}.",
        )
    try:
        return CosmeInputs(**inputs)
    except ValidationError as e:
        raise ScraperError(
            "INVALID_INPUTS",
            f"inputs validation failed: {e.errors(include_url=False)}",
        ) from e


def _classify_entity(raw: dict[str, Any]) -> str | None:
    """Decide which entity a raw row represents.

    Priority:
        1. Explicit ``entity`` / ``_entity`` / ``type`` discriminator (string
           matching one of the three entities) if emitted by the scraper.
        2. Heuristic on the keys present:
           - ``source_type`` + ``rank``  => ranking
           - ``product_id`` / ``product_url`` => product
           - ``brand_id`` + ``total_products`` (or ``brand_total_products``)
             and no ``product_id`` => brand

    Rows that don't match any bucket => None (counted under
    ``skipped_by_reason['unknown_entity']``).
    """
    explicit = raw.get("entity") or raw.get("_entity") or raw.get("type")
    if isinstance(explicit, str):
        if explicit in ("product", "ranking", "brand"):
            return explicit

    if "source_type" in raw and ("rank" in raw or "product_id" in raw):
        # Heuristic: a row with source_type+rank is a ranking, not a product.
        return "ranking"

    if raw.get("product_id") is not None or raw.get("product_url") is not None:
        return "product"

    if raw.get("brand_id") is not None and (
        "total_products" in raw
        or "brand_total_products" in raw
        or "total_reviews" in raw
        or "brand_total_reviews" in raw
    ):
        # Brand-listing row (not a product): has brand_id + brand-level counters.
        return "brand"

    return None


def _apply_aliases(raw: dict[str, Any], aliases: dict[str, str]) -> dict[str, Any]:
    """Rename keys per the ``aliases`` map, dropping ``None`` collisions.

    If a row carries *both* the alias source and the canonical target
    (e.g. ``product_url`` and ``url``), the canonical target wins (we do not
    overwrite an explicit value).
    """
    out = dict(raw)
    for src, dst in aliases.items():
        if src not in out:
            continue
        if dst in out and out[dst] is not None:
            # Canonical already set — keep the original alias around under
            # its scraper-native name (it's a §4+ extra key, forwarded
            # verbatim via extra="allow").
            continue
        out[dst] = out.pop(src)
    return out


def _coerce_row(
    raw: dict[str, Any],
    fields: tuple[str, ...],
    list_fields: frozenset[str],
    aliases: dict[str, str],
    model: type,
) -> dict[str, Any]:
    """Generic coercer: aliases -> fill missing keys -> pydantic validate.

    Returns a dict with every ``fields`` key present (``None`` or ``[]``
    default) and extra keys forwarded verbatim. On pydantic ValidationError,
    falls back to the manually-coerced dict so rows never get dropped.
    """
    aliased = _apply_aliases(raw, aliases) if aliases else dict(raw)

    out: dict[str, Any] = {}
    for key in fields:
        if key in aliased:
            value = aliased[key]
            if key in list_fields:
                if value is None:
                    value = []
                elif not isinstance(value, list):
                    # Defensive: scraper returned a string where we expect a
                    # list. Better than dropping data.
                    value = [value]
            out[key] = value
        else:
            out[key] = [] if key in list_fields else None

    # Forward extras (e.g. product has category_chains, rankings, scraper_flags
    # in §4 that are already in ``fields``; any *unknown* future key goes
    # through verbatim).
    for key, value in aliased.items():
        if key not in out:
            out[key] = value

    try:
        return model(**out).model_dump()
    except ValidationError:
        return out


def _coerce_product(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize a raw row to the canonical :class:`ProductRow` shape."""
    out = _coerce_row(
        raw,
        PRODUCT_FIELDS,
        PRODUCT_LIST_FIELDS,
        PRODUCT_ALIASES,
        ProductRow,
    )
    out["entity"] = "product"
    return out


def _coerce_ranking(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize a raw row to the canonical :class:`RankingRow` shape."""
    out = _coerce_row(
        raw,
        RANKING_FIELDS,
        RANKING_LIST_FIELDS,
        RANKING_ALIASES,
        RankingRow,
    )
    out["entity"] = "ranking"
    return out


def _coerce_brand(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize a raw row to the canonical :class:`BrandRow` shape."""
    out = _coerce_row(
        raw,
        BRAND_FIELDS,
        BRAND_LIST_FIELDS,
        BRAND_ALIASES,
        BrandRow,
    )
    out["entity"] = "brand"
    return out


def _bump(d: dict[str, int], key: str) -> None:
    d[key] = d.get(key, 0) + 1


def _maybe_block_saturation(envelope_resp: dict[str, Any]) -> dict[str, Any]:
    """Surface BLOCK_SATURATION if >50% of emitted product rows hit the block.

    Analogous to cosmetics-design's PAYWALL_SATURATION. We gate on
    ``meta.blocked`` (which counts rows with ``rate_limit_blocked`` or
    ``name_extract_failed`` flags — see ``_build_envelope``). Only product
    rows contribute to the denominator; rankings/brands are passthrough.
    """
    if envelope_resp.get("status") != "done":
        return envelope_resp
    env = envelope_resp.get("data", {})
    meta = env.get("meta", {})
    emitted_by_entity = meta.get("emitted_by_entity") or {}
    products = int(emitted_by_entity.get("product", 0) or 0)
    blocked = int(meta.get("blocked", 0) or 0)
    if products > 0 and (blocked / products) > BLOCK_SATURATION_THRESHOLD:
        return {
            "status": "failed",
            "error": {
                "code": "BLOCK_SATURATION",
                "message": (
                    f"{blocked}/{products} emitted product rows are blocked "
                    f"(> {int(BLOCK_SATURATION_THRESHOLD * 100)}% threshold)."
                ),
                "retriable": False,
                "details": {"products": products, "blocked": blocked},
            },
        }
    return envelope_resp


# ---- module-level public entry points ---------------------------------------

# Names the agents repo imports:
#     from gli_scrapers.cosme import trigger, get_result, TOOL_SCHEMA


async def trigger(
    inputs: CosmeInputs | dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Module-level convenience for ``CosmeClient().trigger(...)``."""
    client = CosmeClient()
    try:
        return await client.trigger(inputs or {})
    finally:
        await client.aclose()


async def get_result(job_id: str) -> dict[str, Any]:
    """Module-level convenience for ``CosmeClient().get_result(...)``."""
    client = CosmeClient()
    try:
        return await client.get_result(job_id)
    finally:
        await client.aclose()
