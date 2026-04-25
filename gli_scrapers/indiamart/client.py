"""``IndiamartClient`` — public ``trigger`` / ``get_result`` for the
BrightData ``indiamart`` scraper (``scrapers/indiamart/``).

This module is the only place where:

    1. Public inputs (spec §9 crawl limits) are translated into the JS
       scraper's Stage 1 seed URLs (``dir.indiamart.com/impcat/<slug>.html``
       and ``dir.indiamart.com/indianexporters/ind_<industry>.html``).
    2. Raw BrightData rows (multi-entity: product + supplier) are normalized
       into the envelope's heterogeneous ``data[]`` shape — each row tagged
       with the ``entity`` discriminator and matching the §2 / §4 / §6 field
       catalog exactly.
    3. Post-download filters (``max_products``, ``max_suppliers``,
       ``include_suppliers``) are applied. The scraper does NOT enforce
       these — we do it here (spec §9 catalogs scraper-side caps; the
       middleware caps only on emission).
    4. Free-text country strings are coerced to ISO-2 (spec §2 / §4:
       ``supplier_country`` must be ``"IN"``).

Inherits BrightData REST plumbing (trigger, poll, download) from
``BaseScraperClient``. Dual-mode (v3 + DCA legacy) is picked at construction
time via env vars — see :func:`gli_scrapers.indiamart.config.resolve_mode_and_id`.

WHY the input translation lives here, not in the JS scraper:
    - Stage 1 (``01_state_code``) reads ``input.category_slug`` + ``input.kind``
      to dispatch directly or fan-out all default slugs. The middleware must
      always supply ``category_slug`` to keep control of what is crawled.
    - The public inputs (``mcat_slugs``, ``include_industry_hubs``,
      ``max_products``, ``max_suppliers``) are *agent-facing* semantics.
    - ``max_products`` / ``max_suppliers`` are post-download clipping (the
      scraper has no single knob for them — its hard caps are 1500/300 in
      spec §9).
"""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import ValidationError

from gli_scrapers.core.client import BaseScraperClient
from gli_scrapers.core.envelope import Envelope, _utc_now_iso
from gli_scrapers.core.errors import ScraperError, error_payload

from gli_scrapers.indiamart.config import (
    BLOCK_SATURATION_THRESHOLD,
    CREDENTIAL_HINT,
    DEFAULT_ETA_SECONDS,
    DEFAULT_INDUSTRY_HUBS,
    DEFAULT_MCAT_SLUGS,
    SOURCE_NAME,
    STRUCTURE_CHANGED_THRESHOLD,
    industry_hub_url,
    mcat_listing_url,
    resolve_mode_and_id,
)
from gli_scrapers.indiamart.models import (
    COUNTRY_NAME_TO_ISO2,
    PRODUCT_ALIASES,
    PRODUCT_FIELDS,
    PRODUCT_LIST_FIELDS,
    SUPPLIER_ALIASES,
    SUPPLIER_FIELDS,
    SUPPLIER_LIST_FIELDS,
    IndiamartInputs,
    ProductRow,
    SupplierRow,
)

# ---- Per-scraper error catalog extension ------------------------------------

# indiamart-specific codes. We extend locally (do NOT mutate the base catalog
# in ``core/errors.py``).
#
# STRUCTURE_CHANGED already lives in the base catalog — we do NOT redefine
# it here, we just trigger it when >50% of emitted products look unparseable
# (see ``_maybe_structure_changed``).
#
# REGION_BLOCKED mirrors spec §2 genomma lab: "sostenido 403/503 + Access
# Denied + redirect to /enquiry.html" — IndiaMART blocks non-IN residential
# IPs. The flag lives on the row as ``blocked`` / ``rate_limit_blocked`` and
# we promote >50% to this code.
INDIAMART_ERROR_CODES: dict[str, dict[str, Any]] = {
    "REGION_BLOCKED": {
        "retriable": False,
        "description": (
            "More than 50% of emitted product rows carry 'blocked' or "
            "'rate_limit_blocked' — IndiaMART served its bot-check page "
            "(Access Denied / redirect to /enquiry.html) after 3 retries. "
            "Rotate to a residential IN session pool and re-trigger."
        ),
    },
}


class IndiamartClient(BaseScraperClient):
    """Stateless wrapper around the indiamart BrightData scraper.

    Dual-mode: picks Datasets v3 or DCA legacy at construction time based on
    which env var the user populated.
    """

    SOURCE_NAME = SOURCE_NAME
    CREDENTIAL_HINT = CREDENTIAL_HINT
    DCA_TRIGGER_PARAMS: ClassVar[dict[str, str]] = {"confirm_cancel": "1"}

    def __init__(
        self,
        api_key: str | None = None,
        resource_id: str | None = None,
        *,
        api_mode: Any = None,
        http_client: Any = None,
        # Silent backwards-compat alias (per dual-mode apéndice A §3).
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
        self, public_inputs: IndiamartInputs
    ) -> list[dict[str, Any]]:
        """Translate public inputs → Stage 1 JS scraper runtime inputs.

        IndiaMART's Stage 1 is ``01_state_code/interaction_code.js`` — a
        dispatcher that reads ``input.category_slug`` + ``input.kind``:

            - If ``category_slug`` is present → single next_stage passthrough.
            - If absent → fan-out of ALL CATEGORIES[kind] slugs (default mode).

        We emit ONE seed per MCAT slug + (optionally) one seed per industry
        hub so the dispatcher forwards each slug directly to Stage 2 (sc_browser).
        The URL templates for IndiaMART are owned by the scraper; the middleware
        only needs to supply the slug + kind. Helpers mcat_listing_url /
        industry_hub_url are kept for testing/debug only.
        """
        seeds: list[dict[str, Any]] = []

        mcat_slugs = (
            public_inputs.mcat_slugs
            if public_inputs.mcat_slugs is not None
            else list(DEFAULT_MCAT_SLUGS)
        )
        for slug in mcat_slugs:
            seeds.append({"url": mcat_listing_url(slug), "category_slug": "", "kind": "mcat"})

        if public_inputs.include_industry_hubs:
            hubs = (
                public_inputs.industry_hubs
                if public_inputs.industry_hubs is not None
                else list(DEFAULT_INDUSTRY_HUBS)
            )
            for industry in hubs:
                seeds.append({"url": industry_hub_url(industry), "category_slug": "", "kind": "hub"})

        # Defensive: the scraper requires at least one seed. If the caller
        # wiped both lists via empty overrides (legal per pydantic: empty
        # list is not None), we raise INVALID_INPUTS rather than sending a
        # no-op trigger.
        if not seeds:
            raise ScraperError(
                "INVALID_INPUTS",
                "No seeds to send: empty mcat_slugs and industry_hubs. "
                "Provide at least one MCAT slug or set "
                "include_industry_hubs=True with non-empty industry_hubs.",
            )

        return seeds

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
            3. Apply aliases (spec §2 short names on the wire).
            4. Coerce every row to the canonical entity shape — every §2
               strict key present, lists never null (spec §5 / §6).
            5. Drop ``supplier`` rows if disabled by inputs.
            6. Apply ``max_products`` / ``max_suppliers`` caps.
            7. Normalize country to ISO-2 on supplier rows.
            8. Compute ``meta`` counters.

        Rows that cannot be classified are counted under
        ``meta.skipped_by_reason`` but never dropped silently.
        """
        started = started_at or _utc_now_iso()

        include_suppliers = bool(public_inputs.get("include_suppliers", True))
        max_products = int(public_inputs.get("max_products") or 500)
        max_suppliers = int(public_inputs.get("max_suppliers") or 150)

        emitted: list[dict[str, Any]] = []
        skipped_by_reason: dict[str, int] = {}
        counts = {"product": 0, "supplier": 0}
        blocked = 0
        structure_failed = 0
        errors = 0

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
                flags = normalized.get("scraper_flags") or []
                # Track blocked / structure-fail flags as a debug aid.
                if (
                    "blocked" in flags
                    or "rate_limit_blocked" in flags
                    or "blocked_retried" in flags
                ):
                    blocked += 1
                if (
                    "jsonld_parse_fallback" in flags
                    or "breadcrumb_missing" in flags
                    or "spec_table_missing" in flags
                ) or not normalized.get("product_id"):
                    # A product row without product_id is a de-facto parse
                    # failure (§8 says SKIP such rows upstream, but if the
                    # scraper emits one anyway we count it).
                    structure_failed += 1

                if products_emitted >= max_products:
                    _bump(skipped_by_reason, "max_products_cap")
                    continue
                products_emitted += 1
            else:  # supplier
                normalized = _coerce_supplier(raw)
                # ISO-2 country normalization on supplier rows.
                normalized = _normalize_supplier_country(normalized)

                if suppliers_emitted >= max_suppliers:
                    _bump(skipped_by_reason, "max_suppliers_cap")
                    continue
                suppliers_emitted += 1

            counts[entity] += 1
            emitted.append(normalized)

        ended = ended_at or _utc_now_iso()

        meta: dict[str, Any] = {
            "rows": len(rows),
            "emitted": len(emitted),
            "emitted_by_entity": counts,
            "skipped_by_reason": skipped_by_reason,
            "blocked": blocked,
            "structure_failed": structure_failed,
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
        self, inputs: IndiamartInputs | dict[str, Any]
    ) -> dict[str, Any]:
        """Validate inputs, fire the BrightData trigger, return
        ``{job_id, eta_seconds}``.

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
                    ScraperError(
                        "INVALID_INPUTS", "job_id must be a non-empty string."
                    )
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
            # Defensive: transport guarantees {running, ready, failed}.
            return {"status": "running", "progress_pct": 0}

        try:
            rows = await self._fetch_snapshot(job_id)
        except ScraperError as e:
            return {"status": "failed", "error": error_payload(e)}

        # Stateless: we do NOT cache the original public_inputs. The agents
        # repo keeps them alongside the job_id and can re-derive the
        # envelope via ``build_envelope_for_rows``.
        envelope = self.build_envelope_for_rows(rows, public_inputs={})
        envelope = _maybe_region_blocked(envelope)
        envelope = _maybe_structure_changed(envelope)
        return envelope

    # ---- public helper for the agents repo --------------------------------

    def build_envelope_for_rows(
        self,
        rows: list[dict[str, Any]],
        public_inputs: dict[str, Any] | IndiamartInputs,
    ) -> dict[str, Any]:
        """Build the envelope from already-fetched rows + caller's inputs.

        Useful when the caller (agents repo) cached the snapshot rows and
        public_inputs alongside the job_id and wants to re-derive the
        envelope without another API round-trip.
        """
        if isinstance(public_inputs, IndiamartInputs):
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
    inputs: IndiamartInputs | dict[str, Any] | None,
) -> IndiamartInputs:
    """Coerce/validate caller inputs. Raises ``ScraperError(INVALID_INPUTS)``."""
    if inputs is None:
        return IndiamartInputs()
    if isinstance(inputs, IndiamartInputs):
        return inputs
    if not isinstance(inputs, dict):
        raise ScraperError(
            "INVALID_INPUTS",
            f"inputs must be a dict or IndiamartInputs, got "
            f"{type(inputs).__name__}.",
        )
    try:
        return IndiamartInputs(**inputs)
    except ValidationError as e:
        raise ScraperError(
            "INVALID_INPUTS",
            f"inputs validation failed: {e.errors(include_url=False)}",
        ) from e


def _classify_entity(raw: dict[str, Any]) -> str | None:
    """Decide which entity a raw row represents.

    Priority:
        1. Explicit ``entity`` / ``_entity`` / ``type`` discriminator (string
           matching one of the two entities) if emitted by the scraper.
           Caveat: ``type`` is also a product *field* (chemical/packaging/
           other per spec §8); we only treat it as the discriminator when it
           equals one of the known entity names.
        2. Heuristic on the keys present:
           - ``product_id`` / ``product_url`` / ``price_currency`` =>
             product (a supplier row never carries a price).
           - ``supplier_id`` present AND no product-signal AND
             ``business_type`` / ``member_since_year`` / ``trustseal`` /
             ``year_established`` present => supplier.

    Rows that don't match any bucket => None (counted under
    ``skipped_by_reason['unknown_entity']``).
    """
    explicit = raw.get("entity") or raw.get("_entity")
    if isinstance(explicit, str) and explicit in ("product", "supplier"):
        return explicit

    # ``type`` is ambiguous (it's also a product field: chemical|packaging|
    # other). Only accept as discriminator if it is literally one of our
    # entity names.
    tdisc = raw.get("type")
    if isinstance(tdisc, str) and tdisc in ("product", "supplier"):
        return tdisc

    # Product heuristics — any one of these is decisive (a supplier row
    # would never carry them).
    if (
        raw.get("product_id") is not None
        or raw.get("product_url") is not None
        or raw.get("price_currency") is not None
        or raw.get("price_min_usd") is not None
        or raw.get("moq_quantity") is not None
    ):
        return "product"

    # Supplier heuristics — supplier_id present, no product signal, plus at
    # least one supplier-specific field.
    if raw.get("supplier_id") is not None:
        for key in (
            "business_type",
            "member_since_year",
            "trustseal",
            "trustseal_verified",
            "year_established",
            "verified_exporter",
            "gst",
            "annual_turnover",
        ):
            if key in raw:
                return "supplier"
        # If all we have is supplier_id alone, conservatively refuse to
        # classify; it's probably an orphan reference, not a full row.

    return None


def _apply_aliases(
    raw: dict[str, Any], aliases: dict[str, str]
) -> dict[str, Any]:
    """Rename keys per the ``aliases`` map, preserving explicit canonical values.

    If a row carries *both* the alias source and the canonical target
    (e.g. ``supplier_url`` and ``url``), the canonical target wins — we do
    not overwrite an explicit value.
    """
    out = dict(raw)
    for src, dst in aliases.items():
        if src not in out:
            continue
        if dst in out and out[dst] is not None:
            # Canonical already set — keep the original alias around under
            # its scraper-native name so nothing is dropped.
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

    # Forward extras verbatim (spec §5 "never omit claves"; ``extra="allow"``
    # on the models lets us pass future fields without a middleware release).
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
    return out


def _normalize_supplier_country(row: dict[str, Any]) -> dict[str, Any]:
    """Force supplier ``country`` to ISO-2. Spec §2 / §6: ``country = "IN"``.

    The JS scraper emits ``"IN"`` by design (spec §4 says "supplier_country
    fijo IN"), but if a future version of the scraper — or a row fed through
    the ``build_envelope_for_rows`` helper — carries free text like
    ``"India"``, we coerce. Unknown values surface as-is with a
    ``country_not_iso2`` flag appended to ``scraper_flags`` so the agents
    repo can triage.
    """
    country = row.get("country")
    if country is None or not isinstance(country, str):
        return row
    stripped = country.strip()
    if len(stripped) == 2 and stripped.isalpha() and stripped.isupper():
        row["country"] = stripped  # already ISO-2
        return row
    iso = COUNTRY_NAME_TO_ISO2.get(stripped.lower())
    if iso:
        row["country"] = iso
        return row
    # Unknown value — keep original, flag it.
    flags = list(row.get("scraper_flags") or [])
    if "country_not_iso2" not in flags:
        flags.append("country_not_iso2")
    row["scraper_flags"] = flags
    return row


def _bump(d: dict[str, int], key: str) -> None:
    d[key] = d.get(key, 0) + 1


def _maybe_region_blocked(envelope_resp: dict[str, Any]) -> dict[str, Any]:
    """Surface REGION_BLOCKED if >50% of emitted product rows hit the block.

    IndiaMART serves a bot-check page (Access Denied + redirect to
    /enquiry.html) to non-IN residential IPs. Spec §2 genomma lab flow:
    "3 retries then emit blocked=true". The flag lives on the product row;
    we gate on ``meta.blocked``.
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
                "code": "REGION_BLOCKED",
                "message": (
                    f"{blocked}/{products} emitted product rows are blocked "
                    f"(> {int(BLOCK_SATURATION_THRESHOLD * 100)}% threshold). "
                    "IndiaMART served its bot-check page."
                ),
                "retriable": False,
                "details": {"products": products, "blocked": blocked},
            },
        }
    return envelope_resp


def _maybe_structure_changed(envelope_resp: dict[str, Any]) -> dict[str, Any]:
    """Surface STRUCTURE_CHANGED if >50% of emitted product rows failed to parse.

    Per user contract: "STRUCTURE_CHANGED if the parser could not extract
    >50% of expected rows". We key on ``meta.structure_failed`` (which
    counts rows missing product_id, or carrying parse-fallback flags such as
    ``jsonld_parse_fallback`` / ``breadcrumb_missing`` / ``spec_table_missing``).
    """
    if envelope_resp.get("status") != "done":
        return envelope_resp
    env = envelope_resp.get("data", {})
    meta = env.get("meta", {})
    emitted_by_entity = meta.get("emitted_by_entity") or {}
    products = int(emitted_by_entity.get("product", 0) or 0)
    failed = int(meta.get("structure_failed", 0) or 0)
    if products > 0 and (failed / products) > STRUCTURE_CHANGED_THRESHOLD:
        return {
            "status": "failed",
            "error": {
                "code": "STRUCTURE_CHANGED",
                "message": (
                    f"{failed}/{products} emitted product rows look "
                    f"unparseable (> {int(STRUCTURE_CHANGED_THRESHOLD * 100)}% "
                    "threshold). IndiaMART JSON-LD / breadcrumb / spec table "
                    "likely changed — rebase the parser."
                ),
                "retriable": False,
                "details": {"products": products, "structure_failed": failed},
            },
        }
    return envelope_resp


# ---- module-level public entry points ---------------------------------------

# Names the agents repo imports:
#     from gli_scrapers.indiamart import trigger, get_result, TOOL_SCHEMA


async def trigger(
    inputs: IndiamartInputs | dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Module-level convenience for ``IndiamartClient().trigger(...)``."""
    client = IndiamartClient()
    try:
        return await client.trigger(inputs or {})
    finally:
        await client.aclose()


async def get_result(job_id: str) -> dict[str, Any]:
    """Module-level convenience for ``IndiamartClient().get_result(...)``."""
    client = IndiamartClient()
    try:
        return await client.get_result(job_id)
    finally:
        await client.aclose()
