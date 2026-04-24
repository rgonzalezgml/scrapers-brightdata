"""JSON Schema describing the ``impi`` middleware as two tools.

The agents repo passes this dict directly to Anthropic's ``tools=[...]``
parameter. Like the other middlewares, we write it by hand (rather than
``model_json_schema()``) so the public contract stays explicit and
reviewable without pydantic's implicit refs leaking in.

Two tools exposed:
    - ``impi_trigger``:   kicks off an IMPI search (synchronous; seconds).
    - ``impi_get_result``: retrieves the stored envelope for a ``job_id``.

Note on ``eta_seconds``: the tool description states that results are
available immediately because ``trigger`` runs the scraper synchronously
in the same call. The agents harness should still call ``get_result`` for
uniformity with the BrightData middlewares.
"""

from __future__ import annotations

from typing import Any

TOOL_TRIGGER_NAME = "impi_trigger"
TOOL_GET_RESULT_NAME = "impi_get_result"


_TRIGGER_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "owner": {
            "type": "string",
            "minLength": 1,
            "maxLength": 200,
            "default": "Genomma",
            "description": (
                "Titular (substring, server-side match) to search in the "
                "IMPI Mexico portal. Default 'Genomma' covers the Genomma "
                "Lab group."
            ),
        },
        "expires_within_days": {
            "type": "integer",
            "minimum": 1,
            "maximum": 3650,
            "default": 90,
            "description": (
                "Expiration window in days from today (UTC) applied to the "
                "portal's DATE_EXPIRY filter."
            ),
        },
        "page_size": {
            "type": "integer",
            "minimum": 1,
            "maximum": 200,
            "default": 50,
            "description": (
                "Page size requested to the portal's 'result' endpoint. The "
                "scraper only fetches the first page; rows beyond this are "
                "flagged as 'paginated' in scraper_flags but not emitted."
            ),
        },
        "mode": {
            "type": "string",
            "enum": ["incremental", "full-refresh"],
            "default": "incremental",
            "description": (
                "Cache-TTL hint for the agents repo. The middleware treats "
                "both values identically (the portal always returns the "
                "full current window)."
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
                "job_id returned by impi_trigger (shape 'local_impi_<hex>'). "
                "The result is cached in-process for the lifetime of the "
                "middleware process."
            ),
        },
    },
    "required": ["job_id"],
}


TOOL_SCHEMA: list[dict[str, Any]] = [
    {
        "name": TOOL_TRIGGER_NAME,
        "description": (
            "Search IMPI Mexico registered trademarks for a given owner "
            "expiring within a time window. Returns immediately with a "
            "job_id (the scraper hits the portal synchronously and is "
            "fast — seconds, not minutes)."
        ),
        "input_schema": _TRIGGER_INPUT_SCHEMA,
    },
    {
        "name": TOOL_GET_RESULT_NAME,
        "description": (
            "Retrieve the result of an IMPI trademark search. Returns the "
            "envelope with data[] of trademarks."
        ),
        "input_schema": _GET_RESULT_INPUT_SCHEMA,
    },
]
