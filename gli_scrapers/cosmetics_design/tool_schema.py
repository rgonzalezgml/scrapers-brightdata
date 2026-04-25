"""JSON Schema describing the ``cosmetics_design`` middleware as two tools.

The agents repo passes this dict directly to Anthropic's ``tools=[...]`` API
parameter (or to whatever tool framework wraps the LLM). The middleware does
NOT call Anthropic itself — it only declares the shape.

Two tools exposed:
    - ``cosmetics_design_trigger``: kicks off a scraper run.
    - ``cosmetics_design_get_result``: polls/fetches the result.

The input_schema for ``trigger`` mirrors :class:`CosmeticsDesignInputs`. We
write it by hand (rather than ``model_json_schema()``) to keep the public
contract explicit and reviewable in code review — anything pydantic adds
implicitly (definitions, $refs) leaks complexity to the agent.
"""

from __future__ import annotations

from typing import Any

TOOL_TRIGGER_NAME = "cosmetics_design_trigger"
TOOL_GET_RESULT_NAME = "cosmetics_design_get_result"


_TRIGGER_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "window_days": {
            "type": "integer",
            "minimum": 1,
            "maximum": 365,
            "default": 180,
            "description": (
                "Days back from now to keep articles (computed on "
                "display_date). Spec §7. Out-of-window articles are counted "
                "in meta but not emitted unless mode='full-refresh'."
            ),
        },
        "max_articles": {
            "type": "integer",
            "minimum": 1,
            "maximum": 5000,
            "default": 1000,
            "description": (
                "Hard cap on emitted rows. Also bounded by BrightData's "
                "global 5000-request / 90-minute cap."
            ),
        },
        "region_filter": {
            "type": ["string", "null"],
            "enum": [
                "North-America",
                "Europe",
                "Asia-Pacific",
                "Latin-America",
                None,
            ],
            "default": None,
            "description": (
                "Optional region tag to filter on (the JS scraper does not "
                "pre-filter; the agents repo applies this filter on the "
                "envelope's data[])."
            ),
        },
        "mode": {
            "type": "string",
            "enum": ["incremental", "full-refresh"],
            "default": "incremental",
            "description": (
                "incremental honors window_days; full-refresh emits all "
                "articles regardless of display_date."
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
                "snapshot_id returned by cosmetics_design_trigger. Opaque to "
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
            "Start a scraper run against nutraingredients.com Beauty & "
            "wellness section (cosmetics-design). Returns a job_id to poll "
            "with cosmetics_design_get_result. The run is asynchronous and "
            "may take 10–60 minutes."
        ),
        "input_schema": _TRIGGER_INPUT_SCHEMA,
    },
    {
        "name": TOOL_GET_RESULT_NAME,
        "description": (
            "Poll a previously-triggered cosmetics-design run. Returns one "
            "of: {status: 'running', progress_pct: int}, "
            "{status: 'done', data: <envelope>}, "
            "{status: 'failed', error: {code, message, retriable}}."
        ),
        "input_schema": _GET_RESULT_INPUT_SCHEMA,
    },
]
