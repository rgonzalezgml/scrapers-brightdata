"""JSON Schema describing the ``cosme`` middleware as two tools.

The agents repo passes this list directly to Anthropic's ``tools=[...]``
parameter (or to whatever tool framework wraps the LLM). The middleware
itself does NOT call Anthropic — it only declares the shape.

Two tools exposed:

    - ``cosme_trigger``: kick off a scraper run against @cosme.net.
    - ``cosme_get_result``: poll / fetch the envelope.

The input_schema for ``trigger`` mirrors :class:`CosmeInputs`. We write it
by hand (rather than ``model_json_schema()``) to keep the public contract
explicit and reviewable — anything pydantic adds implicitly ($refs,
definitions, nested metadata) leaks complexity to the agent.
"""

from __future__ import annotations

from typing import Any

TOOL_TRIGGER_NAME = "cosme_trigger"
TOOL_GET_RESULT_NAME = "cosme_get_result"


_TRIGGER_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "year": {
            "type": ["integer", "null"],
            "minimum": 2000,
            "maximum": 2100,
            "default": None,
            "description": (
                "Award / ranking year to crawl. None = current year. The JS "
                "scraper derives the bestcosme archive URL from this "
                "(https://www.cosme.net/bestcosme/archive/{year}/). Spec §10."
            ),
        },
        "max_products": {
            "type": "integer",
            "minimum": 1,
            "maximum": 3000,
            "default": 1000,
            "description": (
                "Hard cap on emitted product rows. Spec §7 caps unique "
                "product detail pages at 3000 per run. The middleware clips "
                "post-download — the scraper is not reconfigured."
            ),
        },
        "max_categories": {
            "type": "integer",
            "minimum": 1,
            "maximum": 30,
            "default": 24,
            "description": (
                "Maximum number of bestcosme category slugs to crawl at "
                "Stage 1. Mapped to the JS input 'crawl_limit'. Spec §4 "
                "lists 24+ known slugs (serum, toner, lipstick, ...)."
            ),
        },
        "category": {
            "type": ["string", "null"],
            "default": None,
            "description": (
                "Optional case-insensitive substring filter on discovered "
                "category URLs (spec §10 Stage 1 input.category). Example: "
                "'skin' limits to skincare-adjacent slugs."
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
        "mode": {
            "type": "string",
            "enum": ["incremental", "full-refresh"],
            "default": "incremental",
            "description": (
                "'incremental' keeps the default 24h dedup cache on "
                "product_id (spec §7); 'full-refresh' is a hint for the "
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
                "snapshot_id / collection_id returned by cosme_trigger. "
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
            "Start a scraper run against @cosme.net (I+D: Japan beauty "
            "trends). The run discovers bestcosme award pages "
            "(grand/hall/rookie + 24 category slugs) for the given year "
            "and fetches each referenced product detail. Returns a job_id "
            "to poll with cosme_get_result. The run is asynchronous and "
            "can take 30–90 minutes depending on category coverage."
        ),
        "input_schema": _TRIGGER_INPUT_SCHEMA,
    },
    {
        "name": TOOL_GET_RESULT_NAME,
        "description": (
            "Poll a previously-triggered cosme run. Returns one of: "
            "{status: 'running', progress_pct: int}, "
            "{status: 'done', data: <envelope>}, "
            "{status: 'failed', error: {code, message, retriable}}. The "
            "envelope's data[] is heterogeneous — each row carries an "
            "'entity' discriminator ('product' | 'ranking' | 'brand')."
        ),
        "input_schema": _GET_RESULT_INPUT_SCHEMA,
    },
]
