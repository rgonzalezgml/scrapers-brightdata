"""JSON Schema describing the ``alibaba`` middleware as two tools.

The agents repo passes this list directly to Anthropic's ``tools=[...]``
parameter (or to whatever tool framework wraps the LLM). The middleware
itself does NOT call Anthropic — it only declares the shape.

Two tools exposed:

    - ``alibaba_trigger``: kick off a scraper run against alibaba.com.
    - ``alibaba_get_result``: poll / fetch the envelope.

The input_schema for ``trigger`` mirrors :class:`AlibabaInputs`. Written by
hand rather than via ``model_json_schema()`` so the public contract is
explicit and reviewable — anything pydantic adds implicitly ($refs,
definitions, nested metadata) leaks complexity to the agent.
"""

from __future__ import annotations

from typing import Any

TOOL_TRIGGER_NAME = "alibaba_trigger"
TOOL_GET_RESULT_NAME = "alibaba_get_result"


_TRIGGER_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "search_terms": {
            "type": ["array", "null"],
            "items": {
                "type": "string",
                "minLength": 1,
                "maxLength": 120,
            },
            "maxItems": 20,
            "default": None,
            "description": (
                "Keywords to feed the Alibaba trade search. null or empty "
                "list => use the 5 canonical default terms (industrial "
                "chemicals, industrial packaging drums barrels, sodium "
                "hydroxide industrial, hydrochloric acid industrial, "
                "chemical packaging containers). Each term triggers one "
                "BrightData seed. Spec §3."
            ),
        },
        "max_pages": {
            "type": "integer",
            "minimum": 1,
            "maximum": 10,
            "default": 5,
            "description": (
                "Listing pages to crawl per search term. The scraper caps "
                "at min(input.max_pages, 10). Spec genomma lab §2/§3."
            ),
        },
        "supplier_country": {
            "type": ["string", "null"],
            "default": None,
            "description": (
                "Optional ISO-2 country filter applied at Stage 1 (e.g. "
                "'CN' for China-only). null => no restriction. The scraper "
                "falls through the filter when the card's flag does not "
                "match. Spec §3."
            ),
        },
        "min_price": {
            "type": ["number", "null"],
            "minimum": 0,
            "default": None,
            "description": (
                "Minimum product price (USD) for the Stage 1 card filter. "
                "null => no lower bound (scraper defaults to 1 USD). "
                "Spec §3."
            ),
        },
        "max_price": {
            "type": ["number", "null"],
            "minimum": 0,
            "default": None,
            "description": (
                "Maximum product price (USD) for the Stage 1 card filter. "
                "null => no upper bound (scraper defaults to 10000 USD). "
                "Spec §3."
            ),
        },
        "max_products": {
            "type": "integer",
            "minimum": 1,
            "maximum": 10000,
            "default": 2000,
            "description": (
                "Hard cap on emitted product rows. Applied post-download "
                "(the scraper has no equivalent knob). Spec §10."
            ),
        },
        "mode": {
            "type": "string",
            "enum": ["incremental", "full-refresh"],
            "default": "incremental",
            "description": (
                "'incremental' => the agents repo may honor its dedup "
                "cache on (product_url + scraped_date). 'full-refresh' => "
                "the agents repo should bypass its cache. The scraper "
                "itself does not differentiate. Spec §10."
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
                "snapshot_id / collection_id returned by alibaba_trigger. "
                "Opaque to the caller; treat as a black-box token."
            ),
        }
    },
    "required": ["job_id"],
}


TOOL_SCHEMA: list[dict[str, Any]] = [
    {
        "name": TOOL_TRIGGER_NAME,
        "description": (
            "Start a scraper run against alibaba.com trade search "
            "(Precios: global B2B prices for industrial chemicals and "
            "packaging). The run crawls up to max_pages listing pages per "
            "search term and fetches each product detail page. Returns a "
            "job_id to poll with alibaba_get_result. The run is "
            "asynchronous and typically takes 8-15 minutes depending on "
            "search coverage."
        ),
        "input_schema": _TRIGGER_INPUT_SCHEMA,
    },
    {
        "name": TOOL_GET_RESULT_NAME,
        "description": (
            "Poll a previously-triggered alibaba run. Returns one of: "
            "{status: 'running', progress_pct: int}, "
            "{status: 'done', data: <envelope>}, "
            "{status: 'failed', error: {code, message, retriable}}. The "
            "envelope's data[] contains product rows (entity='product') "
            "with 16 spec-§2 keys plus 3 optional reputation keys "
            "(supplier_rating, supplier_reviews_count, "
            "supplier_response_rate)."
        ),
        "input_schema": _GET_RESULT_INPUT_SCHEMA,
    },
]
