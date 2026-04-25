"""Base runner logic compartida por todos los scrapers.

Flujo:
    trigger() → poll hasta done/failed/timeout → MAPPER.insert() a Snowflake
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any

log = logging.getLogger(__name__)


def _snowflake_conn():
    import snowflake.connector
    return snowflake.connector.connect(
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE", "GENOMMA"),
        database=os.environ.get("SNOWFLAKE_DATABASE", "DEV_STG"),
        schema=os.environ.get("SNOWFLAKE_SCHEMA", "GNM_MEX"),
        role=os.environ.get("SNOWFLAKE_ROLE", "SYSADMIN"),
    )


async def run_scraper(
    *,
    name: str,
    client,
    mapper,
    inputs: dict[str, Any] | None = None,
    poll_interval: int = 30,
    poll_timeout: int = 3600,
) -> dict[str, Any]:
    """Ejecuta un scraper end-to-end y carga el resultado en Snowflake.

    Returns:
        {"status": "ok", "inserted": N, "job_id": str}
        {"status": "failed", "reason": str, "job_id": str | None}
    """
    job_id: str | None = None
    start = datetime.now(timezone.utc)

    # 1. Trigger
    log.info("[%s] triggering...", name)
    result = await client.trigger(inputs or {})
    if result.get("status") == "failed":
        reason = str(result.get("error", "trigger failed"))
        log.error("[%s] trigger failed: %s", name, reason)
        return {"status": "failed", "reason": reason, "job_id": None}

    job_id = result["job_id"]
    log.info("[%s] job_id=%s  eta=%ss", name, job_id, result.get("eta_seconds", "?"))

    # 2. Poll
    elapsed = 0
    while elapsed < poll_timeout:
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval

        res = await client.get_result(job_id)
        status = res.get("status")

        if status == "running":
            pct = res.get("progress_pct", 0)
            log.info("[%s] running %d%%  (%ds elapsed)", name, pct, elapsed)
            continue

        if status == "failed":
            reason = str(res.get("error", "scraper failed"))
            log.error("[%s] failed: %s", name, reason)
            return {"status": "failed", "reason": reason, "job_id": job_id}

        if status == "done":
            envelope = res["data"]
            rows = envelope.get("data", [])
            log.info("[%s] done — %d rows in %.1f min",
                     name, len(rows), elapsed / 60)

            # 3. Insert
            conn = _snowflake_conn()
            try:
                inserted = mapper.insert(rows, conn, job_id=job_id)
                log.info("[%s] inserted %d rows → %s", name, inserted, mapper.table)
            finally:
                conn.close()

            return {"status": "ok", "inserted": inserted, "job_id": job_id}

    # Timeout
    log.error("[%s] timeout after %ds (job_id=%s)", name, poll_timeout, job_id)
    return {"status": "failed", "reason": f"timeout after {poll_timeout}s", "job_id": job_id}
