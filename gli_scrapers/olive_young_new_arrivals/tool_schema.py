"""JSON Schema describing the ``olive_young_new_arrivals`` middleware as two tools.

The agents repo passes this list directly to Anthropic's ``tools=[...]``
parameter (or to whatever tool framework wraps the LLM). The middleware
itself does NOT call Anthropic — it only declares the shape.

Two tools exposed:

    - ``olive_young_new_arrivals_trigger``: kick off a scraper run against
      ``global.oliveyoung.com/display/page/new-arrivals``. No inputs required.
    - ``olive_young_new_arrivals_get_result``: poll / fetch the envelope.

The trigger tool has no required inputs — the scraper always fetches the
complete new-arrivals catalogue.
"""

from __future__ import annotations

from typing import Any

TOOL_TRIGGER_NAME = "olive_young_new_arrivals_trigger"
TOOL_GET_RESULT_NAME = "olive_young_new_arrivals_get_result"


_TRIGGER_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {},
    "required": [],
    "description": (
        "No inputs required. The scraper always fetches the complete "
        "new-arrivals catalogue from "
        "global.oliveyoung.com/display/page/new-arrivals."
    ),
}


_GET_RESULT_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "job_id": {
            "type": "string",
            "description": (
                "snapshot_id / collection_id returned by "
                "olive_young_new_arrivals_trigger. Opaque to the caller; "
                "treat as a black-box token."
            ),
        }
    },
    "required": ["job_id"],
}


TOOL_SCHEMA: list[dict[str, Any]] = [
    {
        "name": TOOL_TRIGGER_NAME,
        "description": (
            "Start a scraper run against "
            "global.oliveyoung.com/display/page/new-arrivals (I+D: K-beauty "
            "new product launches). The run fetches the full new-arrivals "
            "catalogue in a single API call — no pagination, no detail-page "
            "enrichment in v1. Typically 50-200 unique products per run, "
            "organized by editorial corners (collections that rotate weekly). "
            "Returns a job_id to poll with olive_young_new_arrivals_get_result. "
            "The run is asynchronous and typically completes within 20 minutes."
        ),
        "input_schema": _TRIGGER_INPUT_SCHEMA,
    },
    {
        "name": TOOL_GET_RESULT_NAME,
        "description": (
            "Poll a previously-triggered olive-young-new-arrivals run. "
            "Returns one of: "
            "{status: 'running', progress_pct: int}, "
            "{status: 'done', data: <envelope>}, "
            "{status: 'failed', error: {code, message, retriable}}. "
            "The envelope's data[] contains rows of entity 'new_arrival' with "
            "fields: prdt_no, product_url, product_name_en, product_name_kr, "
            "brand_no, brand_name_en, brand_name_kr, sale_amt, nrml_amt, "
            "image_url, is_soldout, is_new, is_best, is_flash, has_coupon, "
            "has_gift, promo_name, corner_name, scraped_date."
        ),
        "input_schema": _GET_RESULT_INPUT_SCHEMA,
    },
]
