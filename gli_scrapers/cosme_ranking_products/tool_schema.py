"""JSON Schema describing the ``cosme_ranking_products`` middleware as two tools.

The agents repo passes this dict directly to Anthropic's ``tools=[...]`` API
parameter (or to whatever tool framework wraps the LLM). The middleware does
NOT call Anthropic itself — it only declares the shape.

Two tools exposed:
    - ``cosme_ranking_trigger``: kicks off a scraper run.
    - ``cosme_ranking_get_result``: polls/fetches the result.

The input_schema for ``trigger`` mirrors :class:`CosmeRankingInputs`. Written
by hand (rather than ``model_json_schema()``) to keep the public contract
explicit and free of pydantic's $ref/$defs noise.
"""

from __future__ import annotations

from typing import Any

TOOL_TRIGGER_NAME = "cosme_ranking_trigger"
TOOL_GET_RESULT_NAME = "cosme_ranking_get_result"


_TRIGGER_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "max_pages": {
            "type": "integer",
            "minimum": 1,
            "maximum": 10,
            "default": 10,
            "description": (
                "Number of listing pages to scrape (10 products per page). "
                "Default 10 = full ranking of 100 products. The cosme.net "
                "weekly ranking has exactly 10 pages."
            ),
        },
        "mode": {
            "type": "string",
            "enum": ["incremental", "full-refresh"],
            "default": "incremental",
            "description": (
                "Run mode. Both values produce the same output for this scraper "
                "(the ranking is always the current week's data). Kept for "
                "parity with other middlewares."
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
                "snapshot_id returned by cosme_ranking_trigger. Opaque to "
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
            "Start a scraper run against cosme.net weekly beauty product "
            "ranking (cosme-ranking-products). Returns a job_id to poll with "
            "cosme_ranking_get_result. The run is asynchronous and typically "
            "takes 10-15 minutes to collect 100 products (10 pages x 10 items). "
            "The ranking updates weekly."
        ),
        "input_schema": _TRIGGER_INPUT_SCHEMA,
    },
    {
        "name": TOOL_GET_RESULT_NAME,
        "description": (
            "Poll a previously-triggered cosme-ranking-products run. Returns "
            "one of: {status: 'running', progress_pct: int}, "
            "{status: 'done', data: <envelope with 100 ranking entries>}, "
            "{status: 'failed', error: {code, message, retriable}}."
        ),
        "input_schema": _GET_RESULT_INPUT_SCHEMA,
    },
]
