"""``AlibabaClient`` — public ``trigger`` / ``get_result`` for the BrightData
``alibaba`` scraper (``scrapers/alibaba/``).

This module is the only place where:

    1. Public inputs (:class:`AlibabaInputs`) are translated into the JS
       scraper's Stage 1 runtime inputs (``input.url`` / ``input.max_pages``
       / ``input.supplier_country`` / ``input.min_price`` /
       ``input.max_price``). One BrightData seed per search term.
    2. Raw BrightData rows are normalized into the envelope's ``data[]`` —
       aliased to the spec §2 short names, type-coerced, ISO-2 country
       normalized, ``scraper_flags`` harmonized, every row tagged with
       ``entity="product"`` and ``site="alibaba"``.
    3. Post-download filters (``max_products``) are applied. The scraper
       does NOT enforce them — the middleware clips the envelope (spec §10).

Inherits BrightData REST plumbing (trigger, poll, download) from
``BaseScraperClient``. Dual-mode (v3 + DCA legacy) is picked at construction
time via env vars — see :func:`middlewares.alibaba.config.resolve_mode_and_id`.

WHY the input translation lives here, not in the JS scraper:
    - ``input.url`` / ``input.search_keyword`` / ``input.max_pages`` are
      *operational* knobs (what URL to hit, how many listing pages).
    - The public inputs (``search_terms``, ``supplier_country``, ...) are
      *agent-facing* semantics.
    - ``max_products`` is post-download clipping; the scraper has no such
      knob.

WHY the ISO-2 country mapping lives here, not in the JS scraper:
    - The scraper's Stage 1 (listing) already emits ISO-2 from the country
      flag ``<img>`` src (``/<iso>.png``). Stage 2 (detail) reads a human
      label (``"China"``) from the supplier card. Rather than patch the JS
      in two places, the middleware harmonizes with a local table (spec
      §4: "supplier_country string ISO-2").
"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from middlewares.core.client import BaseScraperClient
from middlewares.core.envelope import Envelope, _utc_now_iso
from middlewares.core.errors import ScraperError, error_payload

from middlewares.alibaba.config import (
    BLOCK_SATURATION_THRESHOLD,
    CREDENTIAL_HINT,
    DEFAULT_ETA_SECONDS,
    DEFAULT_MAX_PAGES,
    DEFAULT_MAX_PRICE,
    DEFAULT_MIN_PRICE,
    DEFAULT_SEARCH_TERMS,
    DEFAULT_SUPPLIER_COUNTRY,
    MISSING_PRICE_SATURATION_THRESHOLD,
    SOURCE_NAME,
    country_to_iso2,
    resolve_mode_and_id,
    search_url,
)
from middlewares.alibaba.models import (
    PRODUCT_ALIASES,
    PRODUCT_FIELDS,
    PRODUCT_LIST_FIELDS,
    AlibabaInputs,
    ProductRow,
)

# ---- Per-scraper error catalog extension ------------------------------------

# Adds alibaba-specific codes on top of the base catalog. We extend locally
# (do NOT mutate the base catalog in ``core/errors.py``). Analogous to
# cosmetics-design's PAYWALL_SATURATION and cosme's BLOCK_SATURATION.
#
# Two alibaba-specific failure modes per the spec:
#
#   - ``BLOCK_SATURATION``: the vendor stack often hits captcha / rate-limit
#     pages when proxied residentially (spec §2 genomma lab: "un h1 puede
#     existir en pantalla de bot-check"). If >50% of product rows carry
#     ``captcha_detected`` or ``rate_limit_blocked``, the run is useless.
#
#   - ``PRICE_MISSING_SATURATION``: alibaba's value proposition for the
#     Precios category is price data. If >70% of emitted products lack a
#     ``price_min_usd`` (either because the supplier hides price behind an
#     RFQ form, or the scraper failed to parse ``.price-item``), the
#     envelope has no actionable content and should fail loud rather than
#     be cached by downstream.
ALIBABA_ERROR_CODES: dict[str, dict[str, Any]] = {
    "BLOCK_SATURATION": {
        "retriable": False,
        "description": (
            "More than 50% of emitted product rows carry 'captcha_detected' "
            "or 'rate_limit_blocked' — Alibaba served the bot-check page. "
            "Re-running on the same IP pool is unlikely to help; rotate "
            "the residential session pool and re-trigger."
        ),
    },
    "PRICE_MISSING_SATURATION": {
        "retriable": False,
        "description": (
            "More than 70% of emitted product rows have price_min_usd=null. "
            "The run has no actionable price data — the Precios category "
            "requires price coverage. Likely causes: mass RFQ-gated "
            "suppliers, or the .price-item selector changed. Investigate "
            "before retrying."
        ),
    },
}


class AlibabaClient(BaseScraperClient):
    """Stateless wrapper around the alibaba BrightData scraper.

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
        # Silent backwards-compat alias (dual-mode spec §7 item 5).
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
        self, public_inputs: AlibabaInputs
    ) -> list[dict[str, Any]]:
        """Translate public inputs → Stage 1 JS scraper runtime inputs.

        One seed per search term. Each seed has:

            - ``url``: canonical trade-search URL for the term (page 1).
            - ``search_keyword``: the term itself; the interaction code uses
              it as a fallback if ``url`` parsing fails (vendor line 6-8).
            - ``max_pages``: per-seed listing page budget.
            - ``supplier_country``: optional ISO-2 filter (defaults to
              ``"CN"`` per spec §3 ONLY when the caller explicitly passes
              it; ``None`` means "no filter" and the scraper sees no key).
            - ``min_price`` / ``max_price``: filter bounds (always emitted
              — the scraper has hardcoded defaults if we omit them, but
              being explicit avoids drift).
            - ``min_order_quantity``: optional MOQ filter; emitted only
              when the caller sets it (vendor line 49 propagates it to
              next_stage).
        """
        # Resolve search terms: empty list or None → canonical defaults.
        terms = public_inputs.search_terms or list(DEFAULT_SEARCH_TERMS)

        # Resolve per-seed knobs once; reuse across every term.
        max_pages = int(public_inputs.max_pages or DEFAULT_MAX_PAGES)
        min_price = (
            float(public_inputs.min_price)
            if public_inputs.min_price is not None
            else DEFAULT_MIN_PRICE
        )
        max_price = (
            float(public_inputs.max_price)
            if public_inputs.max_price is not None
            else DEFAULT_MAX_PRICE
        )

        seeds: list[dict[str, Any]] = []
        for term in terms:
            seed: dict[str, Any] = {
                "url": search_url(term),
                "search_keyword": term,
                "max_pages": max_pages,
                "min_price": min_price,
                "max_price": max_price,
            }
            # supplier_country: emit only when the caller asked for one.
            # The scraper's filter branch short-circuits on a falsy value
            # but we keep the payload lean for callers that don't care.
            if public_inputs.supplier_country:
                seed["supplier_country"] = public_inputs.supplier_country
            elif public_inputs.supplier_country is None:
                # Spec §3 default proxy country is CN; we do NOT inject it
                # by default into the per-card filter (that would drop
                # non-CN suppliers from the envelope). The scraper uses
                # country() at the *proxy* level separately.
                pass
            if public_inputs.min_order_quantity is not None:
                seed["min_order_quantity"] = public_inputs.min_order_quantity
            seeds.append(seed)
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
            2. Classify each row — today always ``"product"`` (spec §2 has
               no other entity). Rows with no ``product_url`` AND no
               ``product_name_*`` get counted under ``skipped_by_reason``.
            3. Apply aliases (vendor → spec §2 short names) via
               :data:`PRODUCT_ALIASES`.
            4. Normalize ``supplier_country`` free-text → ISO-2.
            5. Coerce to :class:`ProductRow` — every §2/§5 key present,
               lists never null, ``entity`` + ``site`` injected.
            6. Apply ``max_products`` cap.
            7. Compute ``meta`` counters including ``blocked`` and
               ``missing_price`` for the saturation checks.
        """
        started = started_at or _utc_now_iso()

        max_products = int(public_inputs.get("max_products") or 2000)

        emitted: list[dict[str, Any]] = []
        skipped_by_reason: dict[str, int] = {}
        blocked = 0
        missing_price = 0
        unmapped_country = 0
        errors = 0

        for raw in rows:
            if not isinstance(raw, dict):
                _bump(skipped_by_reason, "non_dict_row")
                errors += 1
                continue

            entity = _classify_entity(raw)
            if entity is None:
                _bump(skipped_by_reason, "unknown_entity")
                continue

            # entity == "product" is the only case today.
            normalized = _coerce_product(raw)

            # Block / rate-limit tracking (saturation checks). We respect
            # the scraper's flags: if the JS parser tagged a row blocked,
            # we count it — the middleware never re-infers.
            flags = normalized.get("scraper_flags") or []
            if "captcha_detected" in flags or "rate_limit_blocked" in flags:
                blocked += 1

            if normalized.get("price_min_usd") is None:
                missing_price += 1

            if "country_unmapped" in flags:
                unmapped_country += 1

            if len(emitted) >= max_products:
                _bump(skipped_by_reason, "max_products_cap")
                continue

            emitted.append(normalized)

        ended = ended_at or _utc_now_iso()

        meta: dict[str, Any] = {
            "rows": len(rows),
            "emitted": len(emitted),
            "emitted_by_entity": {"product": len(emitted)},
            "skipped_by_reason": skipped_by_reason,
            "blocked": blocked,
            "missing_price": missing_price,
            "unmapped_country": unmapped_country,
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
        self, inputs: AlibabaInputs | dict[str, Any]
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
        envelope = _maybe_price_missing_saturation(envelope)
        return envelope

    # ---- public helper for the agents repo --------------------------------

    def build_envelope_for_rows(
        self,
        rows: list[dict[str, Any]],
        public_inputs: dict[str, Any] | AlibabaInputs,
    ) -> dict[str, Any]:
        """Build the envelope from already-fetched rows + caller's inputs.

        Useful when the caller (agents repo) cached the snapshot rows and
        public_inputs alongside the job_id and wants to re-derive the
        envelope without another API round-trip.
        """
        if isinstance(public_inputs, AlibabaInputs):
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
    inputs: AlibabaInputs | dict[str, Any] | None,
) -> AlibabaInputs:
    """Coerce/validate caller inputs. Raises ``ScraperError(INVALID_INPUTS)``."""
    if inputs is None:
        return AlibabaInputs()
    if isinstance(inputs, AlibabaInputs):
        return inputs
    if not isinstance(inputs, dict):
        raise ScraperError(
            "INVALID_INPUTS",
            f"inputs must be a dict or AlibabaInputs, got {type(inputs).__name__}.",
        )
    try:
        return AlibabaInputs(**inputs)
    except ValidationError as e:
        raise ScraperError(
            "INVALID_INPUTS",
            f"inputs validation failed: {e.errors(include_url=False)}",
        ) from e


def _classify_entity(raw: dict[str, Any]) -> str | None:
    """Decide which entity a raw row represents.

    Today spec §2 declares only ``product``. A row is a product if it
    carries any of the obvious product signals:

        - explicit ``entity`` / ``_entity`` / ``type`` discriminator equal
          to ``"product"``  (type is also a §2 field, so the match is
          strict-equal-``"product"``-string; the §9 values ``"chemical"`` /
          ``"packaging"`` are NOT discriminators)
        - ``product_url`` / ``url`` (canonical URL)
        - ``product_name_clean`` / ``product_name_original`` / ``name_raw``
          / ``cleaned_product_name`` (any of the name aliases)

    Rows without any signal => None (counted under
    ``skipped_by_reason['unknown_entity']``).

    Forward-compat: if the spec §2 adds a ``supplier`` entity, extend this
    function; the rest of ``_build_envelope`` already supports heterogeneous
    ``data[]``.
    """
    explicit = raw.get("entity") or raw.get("_entity")
    if isinstance(explicit, str) and explicit == "product":
        return "product"

    # §2 includes a ``type`` key whose values are ``"chemical"`` /
    # ``"packaging"`` (not ``"product"``); we do NOT treat that as a
    # discriminator. But some scrapers emit ``type="product"`` as a type-tag
    # in the dump envelope, so we accept that form too.
    type_val = raw.get("type")
    if isinstance(type_val, str) and type_val == "product":
        return "product"

    if (
        raw.get("product_url") is not None
        or raw.get("url") is not None
        or raw.get("product_name_clean") is not None
        or raw.get("product_name_original") is not None
        or raw.get("cleaned_product_name") is not None
        or raw.get("name_raw") is not None
    ):
        return "product"

    return None


def _apply_aliases(raw: dict[str, Any], aliases: dict[str, str]) -> dict[str, Any]:
    """Rename keys per the ``aliases`` map, respecting canonical precedence.

    If a row carries *both* the alias source and the canonical target
    (e.g. ``product_url`` and a pre-renamed ``url``), the canonical target
    wins and the alias source is kept around under its scraper-native name
    (via ``extra="allow"`` on the pydantic model).
    """
    out = dict(raw)
    for src, dst in aliases.items():
        if src not in out:
            continue
        if dst in out and out[dst] is not None:
            # Canonical already set — keep the alias around verbatim.
            continue
        out[dst] = out.pop(src)
    return out


def _coerce_product(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize a raw row to the canonical :class:`ProductRow` shape.

    Pipeline:

        1. Alias rename (vendor keys → spec §2 short names).
        2. Ensure every §2/§5 key is present with ``None`` / ``[]`` default.
        3. Normalize ``supplier_country`` free-text → ISO-2 + flag when
           unmapped.
        4. Merge/dedupe ``scraper_flags`` (middleware-added flags never
           replace scraper-emitted ones).
        5. Inject ``entity="product"`` + ``site="alibaba"``.
        6. Validate via pydantic; on ValidationError fall back to the
           manually-coerced dict (never drop a row).
    """
    aliased = _apply_aliases(raw, PRODUCT_ALIASES)

    out: dict[str, Any] = {}
    for key in PRODUCT_FIELDS:
        if key in aliased:
            value = aliased[key]
            if key in PRODUCT_LIST_FIELDS:
                if value is None:
                    value = []
                elif not isinstance(value, list):
                    # Defensive: scraper returned a string where we expect
                    # a list. Better than dropping data.
                    value = [value]
            out[key] = value
        else:
            out[key] = [] if key in PRODUCT_LIST_FIELDS else None

    # Forward any extra keys (vendor-only fields like ``cas_number`` /
    # ``purity`` that are not in spec §2 — caller opts in via extra="allow").
    for key, value in aliased.items():
        if key not in out:
            out[key] = value

    # ---- supplier_country: text → ISO-2 -----------------------------------
    # The scraper emits ISO-2 at Stage 1 (from the flag <img> src) but may
    # emit free text at Stage 2 (detail page label). Spec §4 mandates ISO-2.
    iso, unmapped = country_to_iso2(out.get("supplier_country"))
    out["supplier_country"] = iso
    if unmapped:
        flags = out.get("scraper_flags") or []
        if not isinstance(flags, list):
            flags = [flags]
        if "country_unmapped" not in flags:
            flags = list(flags) + ["country_unmapped"]
        out["scraper_flags"] = flags

    # ---- required metadata -------------------------------------------------
    out["entity"] = "product"
    # Spec §1: "Campo site fijo alibaba". Never let the scraper override.
    out["site"] = "alibaba"

    try:
        return ProductRow(**out).model_dump()
    except ValidationError:
        # Pydantic rejected a type. Return the hand-coerced dict so the row
        # still surfaces. The type mismatch becomes visible via
        # ``scraper_flags`` at the downstream analytics layer.
        return out


def _bump(d: dict[str, int], key: str) -> None:
    d[key] = d.get(key, 0) + 1


def _maybe_block_saturation(envelope_resp: dict[str, Any]) -> dict[str, Any]:
    """Surface BLOCK_SATURATION if >50% of product rows hit the bot-check.

    Analogous to cosmetics-design's PAYWALL_SATURATION and cosme's
    BLOCK_SATURATION. We gate on ``meta.blocked`` (rows with
    ``captcha_detected`` or ``rate_limit_blocked`` flags — see
    ``_build_envelope``).
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


def _maybe_price_missing_saturation(
    envelope_resp: dict[str, Any],
) -> dict[str, Any]:
    """Surface PRICE_MISSING_SATURATION if >70% of products have no price.

    The Precios category value proposition is price data. An envelope with
    no prices is materially useless — the agents repo should fail loud
    rather than cache an empty run.
    """
    if envelope_resp.get("status") != "done":
        return envelope_resp
    env = envelope_resp.get("data", {})
    meta = env.get("meta", {})
    emitted_by_entity = meta.get("emitted_by_entity") or {}
    products = int(emitted_by_entity.get("product", 0) or 0)
    missing = int(meta.get("missing_price", 0) or 0)
    if products > 0 and (missing / products) > MISSING_PRICE_SATURATION_THRESHOLD:
        return {
            "status": "failed",
            "error": {
                "code": "PRICE_MISSING_SATURATION",
                "message": (
                    f"{missing}/{products} emitted product rows have "
                    f"price_min_usd=null (> "
                    f"{int(MISSING_PRICE_SATURATION_THRESHOLD * 100)}% "
                    "threshold). Likely mass RFQ gating or selector drift."
                ),
                "retriable": False,
                "details": {"products": products, "missing_price": missing},
            },
        }
    return envelope_resp


# ---- module-level public entry points ---------------------------------------

# Names the agents repo imports:
#     from middlewares.alibaba import trigger, get_result, TOOL_SCHEMA


async def trigger(
    inputs: AlibabaInputs | dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Module-level convenience for ``AlibabaClient().trigger(...)``."""
    client = AlibabaClient()
    try:
        return await client.trigger(inputs or {})
    finally:
        await client.aclose()


async def get_result(job_id: str) -> dict[str, Any]:
    """Module-level convenience for ``AlibabaClient().get_result(...)``."""
    client = AlibabaClient()
    try:
        return await client.get_result(job_id)
    finally:
        await client.aclose()
