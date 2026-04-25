"""JSON Schema describing the ``made_in_china`` middleware as two tools.

The agents repo passes this list directly to Anthropic's ``tools=[...]``
parameter (or to whatever tool framework wraps the LLM). The middleware
itself does NOT call Anthropic — it only declares the shape.

Two tools exposed:

    - ``made_in_china_trigger``: kick off a scraper run against
      made-in-china.com (category Precios — B2B chinese material quotes).
    - ``made_in_china_get_result``: poll / fetch the envelope.

The input_schema for ``trigger`` mirrors
:class:`gli_scrapers.made_in_china.models.MadeInChinaInputs`. We write it by
hand (rather than ``model_json_schema()``) to keep the public contract
explicit and reviewable — anything pydantic adds implicitly (definitions,
$refs, nested metadata) leaks complexity to the agent.
"""

from __future__ import annotations

from typing import Any

TOOL_TRIGGER_NAME = "made_in_china_trigger"
TOOL_GET_RESULT_NAME = "made_in_china_get_result"


_TRIGGER_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "urls": {
            "type": ["array", "null"],
            "items": {"type": "string"},
            "minItems": 1,
            "maxItems": 50,
            "default": None,
            "description": (
                "Optional list of seed URLs (spec §3). Each may be a listing "
                "(via-1 /products-search/... or via-2 Chemicals/Packaging-"
                "Printing catalog), a detail (.../product/{ID}/...), or a "
                "supplier home ({slug}.en.made-in-china.com/). When null, the "
                "middleware seeds with the default industrial-chemicals via-1 "
                "listing."
            ),
        },
        "max_pages": {
            "type": "integer",
            "minimum": -1,
            "maximum": 500,
            "default": 3,
            "description": (
                "Pagination budget forwarded to the JS scraper (spec §9 v5): "
                "-1 = process every page up to total_pages; N>0 = process "
                "min(N, total_pages); 0 is normalized to -1 by the "
                "interaction code. Applies only to listing URLs."
            ),
        },
        "max_products": {
            "type": "integer",
            "minimum": 1,
            "maximum": 800,
            "default": 400,
            "description": (
                "Hard cap on emitted product rows. Spec §9 caps unique "
                "product detail pages at 800 per run. The middleware clips "
                "post-download — the scraper is not reconfigured."
            ),
        },
        "max_suppliers": {
            "type": "integer",
            "minimum": 1,
            "maximum": 200,
            "default": 100,
            "description": (
                "Hard cap on emitted supplier rows. Spec §9 caps unique "
                "supplier home pages at 200 per run."
            ),
        },
        "include_suppliers": {
            "type": "boolean",
            "default": True,
            "description": (
                "If false, drop all entity='supplier' rows from the "
                "envelope's data[]. Applied post-download."
            ),
        },
        "require_price": {
            "type": "boolean",
            "default": False,
            "description": (
                "If true, drop product rows whose price_min_usd AND "
                "price_max_usd are both null. Spec §8 lists missing "
                "price_raw as a skip reason on the scraper side; this flag "
                "is a middleware-side belt-and-suspenders for parser "
                "regressions."
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
                "snapshot_id / collection_id returned by "
                "made_in_china_trigger. Opaque to the caller; treat as a "
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
            "Start a scraper run against made-in-china.com (category "
            "Precios: B2B quotes for chinese industrial chemicals and "
            "packaging materials — alternative source comparable against "
            "alibaba). The run discovers products via-1 (keyword search), "
            "via-2 (native category catalog) and via-3 (supplier detail), "
            "then fetches JSON-LD + DOM for each referenced product and "
            "supplier home. Returns a job_id to poll with "
            "made_in_china_get_result. The run is asynchronous and can take "
            "20–90 minutes depending on urls/max_pages coverage."
        ),
        "input_schema": _TRIGGER_INPUT_SCHEMA,
    },
    {
        "name": TOOL_GET_RESULT_NAME,
        "description": (
            "Poll a previously-triggered made-in-china run. Returns one of: "
            "{status: 'running', progress_pct: int}, "
            "{status: 'done', data: <envelope>}, "
            "{status: 'failed', error: {code, message, retriable}}. The "
            "envelope's data[] is heterogeneous — each row carries an "
            "'entity' discriminator ('product' | 'supplier'). Product rows "
            "follow spec §2 (29 fields); supplier rows follow spec §2 / §6 "
            "(14 fields)."
        ),
        "input_schema": _GET_RESULT_INPUT_SCHEMA,
    },
]
