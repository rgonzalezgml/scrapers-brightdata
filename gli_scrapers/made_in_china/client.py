"""``MadeInChinaClient`` — public ``trigger`` / ``get_result`` for the
BrightData ``made-in-china`` scraper (``scrapers/made-in-china/``).

This module is the only place where:

    1. Public inputs (spec §2 / §9 of genomma lab) are translated into the
       JS scraper's Stage 1 runtime inputs (``input.url``, ``input.max_pages``,
       ``input.is_rerun``) — one seed per URL.
    2. Raw BrightData rows (multi-entity: product + supplier) are normalized
       into the envelope's heterogeneous ``data[]`` shape — each row tagged
       with the ``entity`` discriminator and matching the §2 / §4 / §6 field
       catalog exactly.
    3. Post-download filters (``max_products``, ``max_suppliers``,
       ``include_suppliers``, ``require_price``) are applied. The scraper
       does NOT enforce these — we do it here (spec §9 describes scraper-side
       caps; middleware clips on top so the envelope is predictable).

Inherits BrightData REST plumbing (trigger, poll, download) from
``BaseScraperClient``. Dual-mode (v3 + DCA legacy) is picked at construction
time via env vars — see :func:`gli_scrapers.made_in_china.config.resolve_mode_and_id`.

WHY input translation lives here, not in the JS scraper:
    - Stage 1 ``input.url`` + ``input.max_pages`` + ``input.is_rerun`` are
      *operational* knobs of the scraper's parallel pagination v5 (spec §9).
    - The public inputs (``urls``, ``max_pages``, ``max_products``,
      ``include_suppliers``, ``require_price``, ``mode``) are *agent-facing*
      semantics.
    - ``max_products`` / ``max_suppliers`` are post-download clipping (the
      scraper caps at spec §9 hard ceilings; middleware refines per run).
"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from gli_scrapers.core.client import BaseScraperClient
from gli_scrapers.core.envelope import Envelope, _utc_now_iso
from gli_scrapers.core.errors import ScraperError, error_payload

from gli_scrapers.made_in_china.config import (
    BLOCK_SATURATION_THRESHOLD,
    CREDENTIAL_HINT,
    DEFAULT_ETA_SECONDS,
    DEFAULT_LISTING_URL,
    DEFAULT_MAX_PAGES,
    KNOWN_PRICE_UNITS,
    SOURCE_NAME,
    STRUCTURE_DEGRADED_THRESHOLD,
    iso2_for_country,
    resolve_mode_and_id,
)
from gli_scrapers.made_in_china.models import (
    PRODUCT_ALIASES,
    PRODUCT_FIELDS,
    PRODUCT_LIST_FIELDS,
    SUPPLIER_ALIASES,
    SUPPLIER_FIELDS,
    SUPPLIER_LIST_FIELDS,
    MadeInChinaInputs,
    ProductRow,
    SupplierRow,
)

# ---- Per-scraper error catalog extension ------------------------------------

# Analogous to cosme's BLOCK_SATURATION and cosmetics-design's
# PAYWALL_SATURATION but tuned to made-in-china's two characteristic failure
# modes documented in ``scrapers/made-in-china/results/errors.md``:
#
#   - BOT_BLOCK_SATURATION: the DOM shrinks to <50 KB and the title contains
#     "Access Denied" / wafCloudflare (spec §2 of genomma lab). Scrapers emit
#     ``blocked`` / ``route_disallowed`` flags; if >50% of emitted rows carry
#     one of those, the run is useless — surface a hard error.
#
#   - STRUCTURE_DEGRADED: if >50% of product rows carry
#     ``jsonld_parse_fallback`` or ``price_unit_unknown`` it signals a
#     vendor-side DOM / JSON-LD shape change (E13-E16 in errors.md showed how
#     a selector rename can wipe an entire field). We map this to the
#     canonical ``STRUCTURE_CHANGED`` base code via a local extension so the
#     agents repo's retry policy works out of the box.
#
# We extend locally (do NOT mutate the base catalog in ``core/errors.py``).
MADE_IN_CHINA_ERROR_CODES: dict[str, dict[str, Any]] = {
    "BOT_BLOCK_SATURATION": {
        "retriable": False,
        "description": (
            "More than 50% of emitted rows carry 'blocked' or "
            "'route_disallowed' — the site served the Access Denied / "
            "Cloudflare challenge sustainedly. Re-running with the same "
            "proxy pool is unlikely to help; escalate to BrightData to "
            "rotate the residential session pool."
        ),
    },
}


class MadeInChinaClient(BaseScraperClient):
    """Stateless wrapper around the made-in-china BrightData scraper.

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
        # Silent backwards-compat alias (dual-mode spec apéndice A §3).
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
        self, public_inputs: MadeInChinaInputs
    ) -> list[dict[str, Any]]:
        """Translate public inputs → Stage 1 JS scraper runtime inputs.

        The deployed Stage 1 (``sc_browser/interaction_code_v8.js``) reads
        only ``input.url`` — one listing URL per seed. The scraper navigates
        the category page, extracts product URLs, and emits one next_stage
        per product URL.

        ``max_pages``, ``mode``, ``max_products``, ``max_suppliers``,
        ``include_suppliers`` and ``require_price`` are middleware-side knobs
        — never forwarded to the seed.
        """
        if public_inputs.search_terms:
            def _kw_to_url(kw: str) -> str:
                # Via-1: /products-search/hot-china-products/{Title_Slug}.html
                # "citric acid anhydrous" → "Citric_Acid_Anhydrous"
                # multi-search URL (/multi-search/…) tried in v11: zero cards — abandoned.
                slug = '_'.join(w.capitalize() for w in kw.strip().split())
                return f"https://www.made-in-china.com/products-search/hot-china-products/{slug}.html"
            return [{"url": _kw_to_url(kw), "search_keyword": kw} for kw in public_inputs.search_terms]

        urls = public_inputs.urls if public_inputs.urls else [DEFAULT_LISTING_URL]
        return [{"url": url} for url in urls]

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
            2. Classify each row into its entity (product / supplier).
            3. Apply aliases (spec §2 canonical names on the wire).
            4. Coerce every row to the canonical entity shape — every §2
               strict key present, lists never null (spec §9).
            5. Apply middleware-side filters:
                 - ``include_suppliers=False`` drops supplier rows.
                 - ``require_price=True`` drops product rows without
                   ``price_min_usd`` / ``price_max_usd``.
                 - ``max_products`` / ``max_suppliers`` caps.
            6. Normalize country names to ISO-2 (emit ``country_unmapped``
               flag if the scraper leaked a free-text country).
            7. Compute ``meta`` counters (rows, emitted, blocked, errors,
               emitted_by_entity, skipped_by_reason, structural flags).

        Rows that cannot be classified are counted under
        ``meta.skipped_by_reason`` but never dropped silently.
        """
        started = started_at or _utc_now_iso()

        include_suppliers = bool(public_inputs.get("include_suppliers", True))
        require_price = bool(public_inputs.get("require_price", False))
        max_products = int(public_inputs.get("max_products") or 400)
        max_suppliers = int(public_inputs.get("max_suppliers") or 100)

        emitted: list[dict[str, Any]] = []
        skipped_by_reason: dict[str, int] = {}
        counts = {"product": 0, "supplier": 0}
        blocked = 0
        errors = 0
        structural_degraded = 0

        products_emitted = 0
        suppliers_emitted = 0

        for raw in rows:
            if not isinstance(raw, dict):
                _bump(skipped_by_reason, "non_dict_row")
                errors += 1
                continue

            entity = _classify_entity(raw)
            if entity is None:
                _bump(skipped_by_reason, "unknown_entity")
                continue

            if entity == "supplier" and not include_suppliers:
                _bump(skipped_by_reason, "suppliers_disabled")
                continue

            if entity == "product":
                normalized = _coerce_product(raw)
                # require_price gate — spec §8 declares price_raw ausente is a
                # skip reason on the scraper side; here we trust the numeric
                # fields the middleware schema exposes.
                if require_price:
                    if (
                        normalized.get("price_min_usd") is None
                        and normalized.get("price_max_usd") is None
                    ):
                        _bump(skipped_by_reason, "price_missing")
                        continue
                # max_products cap.
                if products_emitted >= max_products:
                    _bump(skipped_by_reason, "max_products_cap")
                    continue
                products_emitted += 1
            else:  # supplier
                normalized = _coerce_supplier(raw)
                # max_suppliers cap.
                if suppliers_emitted >= max_suppliers:
                    _bump(skipped_by_reason, "max_suppliers_cap")
                    continue
                suppliers_emitted += 1

            # Shared post-processing: country normalization + flag tracking.
            _normalize_country_inplace(normalized, entity)

            flags = normalized.get("scraper_flags") or []
            if "blocked" in flags or "route_disallowed" in flags:
                blocked += 1
            if (
                "jsonld_parse_fallback" in flags
                or "price_unit_unknown" in flags
                or "metric_unit_missing" in flags
            ):
                structural_degraded += 1

            counts[entity] += 1
            emitted.append(normalized)

        ended = ended_at or _utc_now_iso()

        meta: dict[str, Any] = {
            "rows": len(rows),
            "emitted": len(emitted),
            "emitted_by_entity": counts,
            "skipped_by_reason": skipped_by_reason,
            "blocked": blocked,
            "structural_degraded": structural_degraded,
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
        self, inputs: MadeInChinaInputs | dict[str, Any]
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
        envelope = _maybe_block_saturation(envelope)
        envelope = _maybe_structure_degraded(envelope)
        return envelope

    # ---- public helper for the agents repo --------------------------------

    def build_envelope_for_rows(
        self,
        rows: list[dict[str, Any]],
        public_inputs: dict[str, Any] | MadeInChinaInputs,
    ) -> dict[str, Any]:
        """Build the envelope from already-fetched rows + caller's inputs.

        Useful when the caller (agents repo) cached the snapshot rows and
        public_inputs alongside the job_id and wants to re-derive the
        envelope without another API round-trip.
        """
        if isinstance(public_inputs, MadeInChinaInputs):
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
    inputs: MadeInChinaInputs | dict[str, Any] | None,
) -> MadeInChinaInputs:
    """Coerce/validate caller inputs. Raises ``ScraperError(INVALID_INPUTS)``."""
    if inputs is None:
        return MadeInChinaInputs()
    if isinstance(inputs, MadeInChinaInputs):
        return inputs
    if not isinstance(inputs, dict):
        raise ScraperError(
            "INVALID_INPUTS",
            f"inputs must be a dict or MadeInChinaInputs, got {type(inputs).__name__}.",
        )
    try:
        return MadeInChinaInputs(**inputs)
    except ValidationError as e:
        raise ScraperError(
            "INVALID_INPUTS",
            f"inputs validation failed: {e.errors(include_url=False)}",
        ) from e


def _classify_entity(raw: dict[str, Any]) -> str | None:
    """Decide which entity a raw row represents.

    Priority:
        1. Explicit ``entity`` / ``_entity`` / ``__entity`` / ``type``
           discriminator (string matching one of the two entities) if the
           scraper emitted one.
        2. Heuristic on the keys present:
           - ``product_id`` / ``product_url`` / ``price_raw`` → product.
           - ``supplier_id`` present *without* ``product_id`` and with
             any of the supplier-specific keys (``business_type``,
             ``member_level``, ``employees_raw``, ``audited_supplier``,
             ``management_certifications``, ``year_established``) → supplier.

    The ``type`` column is tricky — in MIC spec §4 the product row carries
    its own ``type`` field (enum chemical/empaque/other). We only treat
    ``type`` as discriminator when its value is literally ``"product"`` or
    ``"supplier"`` and never confuse with the category enum.

    Rows that don't match any bucket → None (counted under
    ``skipped_by_reason['unknown_entity']``).
    """
    # 1. Explicit discriminator.
    explicit_keys = ("entity", "_entity", "__entity")
    for k in explicit_keys:
        v = raw.get(k)
        if isinstance(v, str) and v in ("product", "supplier"):
            return v
    # Special-case ``type`` — MIC product rows carry ``type`` as a category
    # enum, so only accept when value is unambiguous.
    type_v = raw.get("type")
    if isinstance(type_v, str) and type_v in ("product", "supplier"):
        # Extra guard: if both a product_id and a supplier_id exist on the
        # same row, treat the explicit discriminator as authoritative anyway.
        return type_v

    # 2. Heuristic.
    has_product_signal = (
        raw.get("product_id") is not None
        or raw.get("product_url") is not None
        or raw.get("price_raw") is not None
    )
    if has_product_signal:
        return "product"

    has_supplier_signal = raw.get("supplier_id") is not None and any(
        key in raw
        for key in (
            "business_type",
            "member_level",
            "employees_raw",
            "audited_supplier",
            "management_certifications",
            "year_established",
            "supplier_name",
            "main_products",
        )
    )
    if has_supplier_signal:
        return "supplier"

    return None


def _apply_aliases(raw: dict[str, Any], aliases: dict[str, str]) -> dict[str, Any]:
    """Rename keys per the ``aliases`` map, without overwriting canonical values.

    If a row carries *both* the alias source and the canonical target
    (e.g. ``url`` and ``product_url``), the canonical target wins — we do not
    overwrite an explicit value.
    """
    out = dict(raw)
    for src, dst in aliases.items():
        if src not in out:
            continue
        if dst in out and out[dst] is not None:
            # Canonical already set — keep the alias around verbatim under
            # its scraper-native name (forwarded via extra="allow").
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
    """Generic coercer: aliases → fill missing keys → pydantic validate.

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

    # Forward extras (debug keys, future §4/§6 additions).
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
    # spec §2 fixes site_code = "made-in-china" — enforce when missing.
    if not out.get("site_code"):
        out["site_code"] = "made-in-china"
    # Normalize scraper_flags to a list (defensive; _coerce_row already does
    # this via PRODUCT_LIST_FIELDS but we re-check since post-processing
    # mutates the list).
    if not isinstance(out.get("scraper_flags"), list):
        out["scraper_flags"] = []
    # price_unit sanity: if not null and not in the known-units set, flag it.
    unit = out.get("price_unit")
    if unit and isinstance(unit, str) and unit not in KNOWN_PRICE_UNITS:
        flags = out.setdefault("scraper_flags", [])
        if "price_unit_unknown" not in flags:
            flags.append("price_unit_unknown")
    return out


def _coerce_supplier(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize a raw row to the canonical :class:`SupplierRow` shape."""
    out = _coerce_row(
        raw,
        SUPPLIER_FIELDS,
        SUPPLIER_LIST_FIELDS,
        SUPPLIER_ALIASES,
        SupplierRow,
    )
    out["entity"] = "supplier"
    if not isinstance(out.get("scraper_flags"), list):
        out["scraper_flags"] = []
    return out


def _normalize_country_inplace(row: dict[str, Any], entity: str) -> None:
    """ISO-2 normalize a supplier row's ``supplier_country`` in place.

    The parser v3 already applies the map (``COUNTRY_ISO`` in
    ``sc_code/parser_code_v3.js``) so most rows arrive as ``"CN"``. This is
    a safety net: if the value is NOT a 2-letter uppercase code we try the
    middleware's canonical map (:func:`iso2_for_country`). On miss we set
    ``supplier_country`` to ``None`` and append ``country_unmapped`` to
    ``scraper_flags`` (spec-compatible flag name, parallel to the
    ``country_iso_unknown`` the parser emits).

    Only runs on supplier rows — ``origin_country`` on product rows is a
    free-text field per spec §5 (the breadcrumb / JSON-LD additionalProperty),
    so we do NOT rewrite it.
    """
    if entity != "supplier":
        return
    value = row.get("supplier_country")
    if value is None or value == "":
        return
    if isinstance(value, str) and len(value) == 2 and value.isupper():
        # Already ISO-2.
        return
    iso = iso2_for_country(value) if isinstance(value, str) else None
    if iso:
        row["supplier_country"] = iso
        return
    # Unmappable — null out and flag so downstream doesn't confuse the raw
    # name with a country code.
    row["supplier_country"] = None
    flags = row.setdefault("scraper_flags", [])
    if "country_unmapped" not in flags:
        flags.append("country_unmapped")


def _bump(d: dict[str, int], key: str) -> None:
    d[key] = d.get(key, 0) + 1


def _maybe_block_saturation(envelope_resp: dict[str, Any]) -> dict[str, Any]:
    """Surface BOT_BLOCK_SATURATION if >50% of emitted rows hit the bot block.

    Analogous to cosme's BLOCK_SATURATION. Denominator is total emitted rows
    (product + supplier). The ``blocked`` counter is incremented in
    ``_build_envelope`` when a row carries ``blocked`` or ``route_disallowed``
    flags.
    """
    if envelope_resp.get("status") != "done":
        return envelope_resp
    env = envelope_resp.get("data", {})
    meta = env.get("meta", {})
    emitted = int(meta.get("emitted", 0) or 0)
    blocked = int(meta.get("blocked", 0) or 0)
    if emitted > 0 and (blocked / emitted) > BLOCK_SATURATION_THRESHOLD:
        return {
            "status": "failed",
            "error": {
                "code": "BOT_BLOCK_SATURATION",
                "message": (
                    f"{blocked}/{emitted} emitted rows are blocked "
                    f"(> {int(BLOCK_SATURATION_THRESHOLD * 100)}% threshold)."
                ),
                "retriable": False,
                "details": {"emitted": emitted, "blocked": blocked},
            },
        }
    return envelope_resp


def _maybe_structure_degraded(envelope_resp: dict[str, Any]) -> dict[str, Any]:
    """Surface STRUCTURE_CHANGED if >50% of product rows show parser regressions.

    The ``structural_degraded`` counter tracks rows carrying any of
    ``jsonld_parse_fallback``, ``price_unit_unknown`` or
    ``metric_unit_missing``. When the share of degraded rows exceeds the
    threshold we treat the snapshot as structurally stale — the vendor site
    changed shape and the parser needs a ``_vN+1`` iteration.

    Denominator is product rows only (supplier rows do not carry the
    JSON-LD / price-unit flags).
    """
    if envelope_resp.get("status") != "done":
        return envelope_resp
    env = envelope_resp.get("data", {})
    meta = env.get("meta", {})
    emitted_by_entity = meta.get("emitted_by_entity") or {}
    products = int(emitted_by_entity.get("product", 0) or 0)
    degraded = int(meta.get("structural_degraded", 0) or 0)
    if products > 0 and (degraded / products) > STRUCTURE_DEGRADED_THRESHOLD:
        return {
            "status": "failed",
            "error": {
                "code": "STRUCTURE_CHANGED",
                "message": (
                    f"{degraded}/{products} emitted product rows carry "
                    "parser-degradation flags (jsonld_parse_fallback / "
                    "price_unit_unknown / metric_unit_missing) "
                    f"(> {int(STRUCTURE_DEGRADED_THRESHOLD * 100)}% threshold)."
                ),
                "retriable": False,
                "details": {"products": products, "degraded": degraded},
            },
        }
    return envelope_resp


# ---- module-level public entry points ---------------------------------------

# Names the agents repo imports:
#     from gli_scrapers.made_in_china import trigger, get_result, TOOL_SCHEMA


async def trigger(
    inputs: MadeInChinaInputs | dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Module-level convenience for ``MadeInChinaClient().trigger(...)``."""
    client = MadeInChinaClient()
    try:
        return await client.trigger(inputs or {})
    finally:
        await client.aclose()


async def get_result(job_id: str) -> dict[str, Any]:
    """Module-level convenience for ``MadeInChinaClient().get_result(...)``."""
    client = MadeInChinaClient()
    try:
        return await client.get_result(job_id)
    finally:
        await client.aclose()
