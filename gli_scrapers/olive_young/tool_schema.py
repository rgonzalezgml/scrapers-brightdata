"""JSON Schema describing the ``olive_young`` middleware as two tools.

The agents repo passes this list directly to Anthropic's ``tools=[...]``
parameter (or to whatever tool framework wraps the LLM). The middleware
itself does NOT call Anthropic — it only declares the shape.

Two tools exposed:

    - ``olive_young_trigger``: kick off a scraper run against
      ``global.oliveyoung.com`` + ``product-ranking-service.oliveyoung.com``.
    - ``olive_young_get_result``: poll / fetch the envelope.

The input_schema for ``trigger`` mirrors :class:`OliveYoungInputs`. We write
it by hand (rather than ``model_json_schema()``) to keep the public contract
explicit and reviewable — anything pydantic adds implicitly ($refs,
definitions, nested metadata) leaks complexity to the agent.
"""

from __future__ import annotations

from typing import Any

TOOL_TRIGGER_NAME = "olive_young_trigger"
TOOL_GET_RESULT_NAME = "olive_young_get_result"


_TRIGGER_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "regions": {
            "type": "array",
            "items": {"type": "string", "enum": ["KR", "USA"]},
            "minItems": 1,
            "maxItems": 2,
            "default": ["KR", "USA"],
            "description": (
                "Which Olive Young ranking regions to crawl. Only 'KR' and "
                "'USA' are valid — 'Global' and 'ko' language return 400 / "
                "empty arrays (spec §3 / errors.md E3)."
            ),
        },
        "max_products": {
            "type": "integer",
            "minimum": 1,
            "maximum": 3000,
            "default": 1000,
            "description": (
                "Hard cap on emitted product rows. Spec §8: up to 100 detail "
                "enrichments via Scraping Browser per run. The middleware "
                "clips post-download — the scraper is not reconfigured."
            ),
        },
        "max_brand_visits": {
            "type": "integer",
            "minimum": 0,
            "maximum": 100,
            "default": 20,
            "description": (
                "Cap on brand-page visits (spec §8: top-20 brands by "
                "brand_total_products_in_rankings). Setting 0 disables the "
                "brand-page visit step entirely."
            ),
        },
        "include_rankings": {
            "type": "boolean",
            "default": True,
            "description": (
                "If false, drop all entity='ranking' rows from the "
                "envelope's data[]. Applied post-download."
            ),
        },
        "include_brands": {
            "type": "boolean",
            "default": True,
            "description": (
                "If false, drop all entity='brand' rows from the envelope's "
                "data[]. Applied post-download."
            ),
        },
        "include_products": {
            "type": "boolean",
            "default": True,
            "description": (
                "If false, drop all entity='product' rows from the "
                "envelope's data[]. Useful when the caller only wants the "
                "ranking signal (rank + prdt_no)."
            ),
        },
        "categories": {
            "type": ["array", "null"],
            "items": {"type": "string"},
            "default": None,
            "description": (
                "Optional whitelist of ranking API category-id values "
                "(spec §9: e.g. '1000000001' All, '1000000008' Skincare, "
                "'1000000031' Makeup). None => scraper discovers from the "
                "/v1/pages/ranking/sales/categories endpoint."
            ),
        },
        "mode": {
            "type": "string",
            "enum": ["incremental", "full-refresh"],
            "default": "incremental",
            "description": (
                "'incremental' keeps the default 24h dedup cache on "
                "prdt_no (spec §8); 'full-refresh' is a hint for the "
                "agents repo to bypass its own cache."
            ),
        },
    },
    "required": [],
}


_GET_RESULT_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "job_id": {
            "type": "string",
            "description": (
                "snapshot_id / collection_id returned by "
                "olive_young_trigger. Opaque to the caller; treat as a "
                "black-box token."
            ),
        }
    },
    "required": ["job_id"],
}


TOOL_SCHEMA: list[dict[str, Any]] = [
    {
        "name": TOOL_TRIGGER_NAME,
        "description": (
            "Start a scraper run against global.oliveyoung.com + "
            "product-ranking-service.oliveyoung.com (I+D: K-beauty Korea "
            "trends and bestseller rankings). The run crawls 11 KR + 12 "
            "USA ranking categories, enriches up to 100 product detail "
            "pages (via Scraping Browser) and up to 20 brand pages. "
            "Returns a job_id to poll with olive_young_get_result. The "
            "run is asynchronous and can take 20-40 minutes."
        ),
        "input_schema": _TRIGGER_INPUT_SCHEMA,
    },
    {
        "name": TOOL_GET_RESULT_NAME,
        "description": (
            "Poll a previously-triggered olive-young run. Returns one of: "
            "{status: 'running', progress_pct: int}, "
            "{status: 'done', data: <envelope>}, "
            "{status: 'failed', error: {code, message, retriable}}. The "
            "envelope's data[] is heterogeneous — each row carries an "
            "'entity' discriminator ('ranking' | 'product' | 'brand')."
        ),
        "input_schema": _GET_RESULT_INPUT_SCHEMA,
    },
]
