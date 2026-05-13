from __future__ import annotations

import logging
from typing import Any

from registry import ScraperHandler

log = logging.getLogger(__name__)


def extract_rows(body: Any) -> list[dict[str, Any]]:
    """Normalize BrightData webhook body to a plain list of row dicts."""
    if isinstance(body, list):
        return body
    if isinstance(body, dict):
        for key in ("data", "results", "items"):
            if isinstance(body.get(key), list):
                return body[key]
    raise ValueError(f"unexpected webhook body shape: {type(body)}")


def run_etl(
    raw_rows: list[dict[str, Any]],
    handler: ScraperHandler,
) -> tuple[list[dict[str, Any]], int, int, int]:
    """Apply handler's row_filter to raw BrightData rows, then return them for the mapper.

    Returns (rows, error_count, skipped_count, filtered_count).
    """
    rows = raw_rows

    if handler.row_filter is not None:
        before = len(rows)
        rows = [r for r in rows if handler.row_filter(r)]
        filtered_count = before - len(rows)
        if filtered_count:
            log.info("row_filter dropped %d/%d rows", filtered_count, before)
    else:
        filtered_count = 0

    log.info("ETL done — %d rows, %d filtered", len(rows), filtered_count)
    return rows, 0, 0, filtered_count
