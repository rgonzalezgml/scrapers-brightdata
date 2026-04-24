"""JSON Schema describing the ``indiamart`` middleware as two tools.

The agents repo passes this list directly to Anthropic's ``tools=[...]``
parameter (or to whatever tool framework wraps the LLM). The middleware
itself does NOT call Anthropic — it only declares the shape.

Two tools exposed:

    - ``indiamart_trigger``: kick off a scraper run against indiamart.com.
    - ``indiamart_get_result``: poll / fetch the envelope.

The input_schema for ``trigger`` mirrors :class:`IndiamartInputs`. We write
it by hand (rather than ``model_json_schema()``) to keep the public
contract explicit and reviewable — anything pydantic adds implicitly
($refs, definitions, nested metadata) leaks complexity to the agent.
"""

from __future__ import annotations

from typing import Any

TOOL_TRIGGER_NAME = "indiamart_trigger"
TOOL_GET_RESULT_NAME = "indiamart_get_result"


_TRIGGER_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "mcat_slugs": {
            "type": ["array", "null"],
            "items": {"type": "string"},
            "default": None,
            "description": (
                "Optional explicit list of MCAT category slugs to seed "
                "Stage 1 with (each maps to "
                "https://dir.indiamart.com/impcat/{slug}.html). If null, "
                "uses the 12 default slugs from spec §9 (caustic-soda, "
                "sodium-hydroxide-pellets, hydrochloric-acid, ...)."
            ),
        },
        "industry_hubs": {
            "type": ["array", "null"],
            "items": {"type": "string"},
            "default": None,
            "description": (
                "Optional explicit list of industry hub codes (e.g. "
                "'chem', 'packaging') to seed Stage 1 with. Each maps to "
                "https://dir.indiamart.com/indianexporters/ind_<code>.html. "
                "If null, uses the 2 default hubs from spec §9."
            ),
        },
        "include_industry_hubs": {
            "type": "boolean",
            "default": True,
            "description": (
                "If false, do not emit industry hub seeds. Useful for "
                "tight runs — each hub enumerates ~100 MCATs."
            ),
        },
        "max_products": {
            "type": "integer",
            "minimum": 1,
            "maximum": 1500,
            "default": 500,
            "description": (
                "Hard cap on emitted product rows. Spec §9 caps unique "
                "PRODUCT_ID detail pages at 1500 per run. The middleware "
                "clips post-download — the scraper is not reconfigured."
            ),
        },
        "max_suppliers": {
            "type": "integer",
            "minimum": 0,
            "maximum": 300,
            "default": 150,
            "description": (
                "Hard cap on emitted supplier rows. Spec §9 caps supplier "
                "home visits at 300. 0 suppresses every supplier row."
            ),
        },
        "include_suppliers": {
            "type": "boolean",
            "default": True,
            "description": (
                "If false, drop every entity='supplier' row from the "
                "envelope's data[]. Applied post-download."
            ),
        },
        "mode": {
            "type": "string",
            "enum": ["incremental", "full-refresh"],
            "default": "incremental",
            "description": (
                "'incremental' keeps the default 24h dedup cache on "
                "product_id (spec §9); 'full-refresh' is a hint for the "
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
                "snapshot_id / collection_id returned by indiamart_trigger. "
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
            "Start a scraper run against indiamart.com (Precios: B2B prices "
            "India). The run seeds Stage 1 with MCAT category listings "
            "(caustic-soda, industrial-drums, ...) and optionally industry "
            "hubs (chem, packaging), then fetches product detail pages + "
            "supplier home pages. Third source in the Precios category "
            "alongside alibaba and made-in-china — schema aligned for "
            "cross-source comparison. Returns a job_id to poll with "
            "indiamart_get_result. The run is asynchronous and can take "
            "30–90 minutes depending on seed count."
        ),
        "input_schema": _TRIGGER_INPUT_SCHEMA,
    },
    {
        "name": TOOL_GET_RESULT_NAME,
        "description": (
            "Poll a previously-triggered indiamart run. Returns one of: "
            "{status: 'running', progress_pct: int}, "
            "{status: 'done', data: <envelope>}, "
            "{status: 'failed', error: {code, message, retriable}}. The "
            "envelope's data[] is heterogeneous — each row carries an "
            "'entity' discriminator ('product' | 'supplier'). Currency: "
            "INR converted to USD via price_min_usd / price_max_usd."
        ),
        "input_schema": _GET_RESULT_INPUT_SCHEMA,
    },
]
