"""JSON Schema describing the ``cosme_new_arrivals`` middleware as two tools.

The agents repo passes this dict directly to Anthropic's ``tools=[...]`` API
parameter (or to whatever tool framework wraps the LLM). The middleware does
NOT call Anthropic itself — it only declares the shape.

Two tools exposed:
    - ``cosme_new_arrivals_trigger``: kicks off a scraper run.
    - ``cosme_new_arrivals_get_result``: polls/fetches the result.

The input_schema for ``trigger`` mirrors :class:`CosmeNewArrivalsInputs`.
Written by hand (rather than ``model_json_schema()``) to keep the public
contract explicit and free of pydantic's $ref/$defs noise.
"""

from __future__ import annotations

from typing import Any

TOOL_TRIGGER_NAME = "cosme_new_arrivals_trigger"
TOOL_GET_RESULT_NAME = "cosme_new_arrivals_get_result"


_TRIGGER_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "year": {
            "type": "integer",
            "minimum": 2020,
            "maximum": 2030,
            "description": "Año a scrapear (2020-2030). Default: año actual.",
        },
        "month": {
            "type": "integer",
            "minimum": 1,
            "maximum": 12,
            "description": "Mes a scrapear (1-12). Default: mes actual.",
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
                "snapshot_id returned by cosme_new_arrivals_trigger. Opaque to "
                "the caller; treat as a black-box token."
            ),
        }
    },
    "required": ["job_id"],
}


TOOL_SCHEMA: list[dict[str, Any]] = [
    {
        "name": TOOL_TRIGGER_NAME,
        "description": (
            "Start a scraper run against the cosme.net new product launch "
            "calendar (cosme-new-arrivals) for a given year and month. "
            "Returns a job_id to poll with cosme_new_arrivals_get_result. "
            "The run is asynchronous and typically takes 30-60 minutes to "
            "collect all new product entries for the selected month (~31 "
            "day-pages, up to 2000 products). Use this to detect new cosmetic "
            "launches in Japan at their exact market entry date."
        ),
        "input_schema": _TRIGGER_INPUT_SCHEMA,
    },
    {
        "name": TOOL_GET_RESULT_NAME,
        "description": (
            "Poll a previously-triggered cosme-new-arrivals run. Returns "
            "one of: {status: 'running', progress_pct: int}, "
            "{status: 'done', data: <envelope with new_product entries>}, "
            "{status: 'failed', error: {code, message, retriable}}. "
            "Each entry in data[] has: product_id, product_url, product_name, "
            "brand_id, brand_name, brand_url, release_date (YYYY-MM-DD), "
            "shop_url (null if JS modal), scraped_at."
        ),
        "input_schema": _GET_RESULT_INPUT_SCHEMA,
    },
]
