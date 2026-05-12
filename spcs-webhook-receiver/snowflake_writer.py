from __future__ import annotations

import logging
import os
import time
from typing import Any

log = logging.getLogger(__name__)

_RETRIES = 3
_BACKOFF = [2, 5]
_TOKEN_PATH = "/snowflake/session/token"


def connect(caller_token: str | None = None):
    """Connect to Snowflake (open new connection — caller is responsible for closing).

    Strategy selection — env SNOWFLAKE_AUTH_STRATEGY (ajustable via ALTER SERVICE):
      spcs        → OAuth session token (service user). IGNORA caller_token aunque
                    venga el header. INSERTs aparecen como service user en QUERY_HISTORY.
      spcs-caller → Combined token (service_token + '.' + caller_token). Requiere
                    `executeAsCaller: true` en el spec. INSERTs aparecen como caller real.
                    Sin caller grants previos en Snowflake la sesion queda restringida.
      local       → user+password (dev local).
      (unset)     → auto-detect: spcs si /snowflake/session/token existe, sino local.

    El handler HTTP siempre extrae `Sf-Context-Current-User-Token` y lo pasa como
    `caller_token`. Esta funcion decide usarlo o no segun la strategy — asi el
    comportamiento se puede cambiar runtime con ALTER SERVICE + nuevo upload-spec,
    sin rebuild de imagen.
    """
    import snowflake.connector

    strategy = os.environ.get("SNOWFLAKE_AUTH_STRATEGY", "").strip().lower()
    use_spcs = strategy in ("spcs", "spcs-caller") or (not strategy and os.path.exists(_TOKEN_PATH))
    use_caller = strategy == "spcs-caller" and bool(caller_token)

    common = {
        "warehouse": os.environ.get("SNOWFLAKE_WAREHOUSE", "DEV_STREAMLIT_WH"),
        "database":  os.environ.get("SNOWFLAKE_DATABASE", "DEV_STG"),
        "schema":    os.environ.get("SNOWFLAKE_SCHEMA",   "GNM_MEX"),
    }

    if use_spcs:
        with open(_TOKEN_PATH, "r", encoding="ascii") as f:
            token = f.read().strip()
        if use_caller:
            token = f"{token}.{caller_token}"
        return snowflake.connector.connect(
            account       = os.environ["SNOWFLAKE_ACCOUNT"],
            host          = os.environ["SNOWFLAKE_HOST"],
            authenticator = "oauth",
            token         = token,
            **common,
        )

    return snowflake.connector.connect(
        user     = os.environ["SNOWFLAKE_USER"],
        password = os.environ["SNOWFLAKE_PASSWORD"],
        account  = os.environ["SNOWFLAKE_ACCOUNT"],
        role     = os.environ.get("SNOWFLAKE_ROLE"),
        **common,
    )


def write_with_retry(
    rows: list[dict[str, Any]],
    mapper: Any,
    job_id: str,
    caller_token: str | None = None,
    clean: bool = False,
) -> int:
    """Insert rows via mapper with up to 3 retries. Raises on final failure.

    Si `clean=True`, borra toda la tabla antes de insertar (mismo comportamiento
    que runner_base._clean_insert). DELETE + INSERT van en la misma transaccion;
    si el INSERT falla se hace rollback y la tabla queda intacta.

    Si `caller_token` viene seteado, la conexion se hace como el caller (executeAsCaller).
    """
    if not rows:
        return 0

    last_exc: Exception | None = None
    for attempt in range(_RETRIES):
        try:
            conn = connect(caller_token=caller_token)
            try:
                if clean:
                    cur = conn.cursor()
                    cur.execute(f"DELETE FROM {mapper.table}")
                    deleted = cur.rowcount if cur.rowcount is not None else 0
                    log.info("clean: deleted %d rows from %s", deleted, mapper.table)
                inserted = mapper.insert(rows, conn, job_id=job_id)
                conn.commit()
                return inserted
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()
        except Exception as e:
            last_exc = e
            log.warning("Snowflake attempt %d/%d failed: %s", attempt + 1, _RETRIES, e)
            if attempt < len(_BACKOFF):
                time.sleep(_BACKOFF[attempt])

    raise RuntimeError(f"Snowflake unavailable after {_RETRIES} attempts: {last_exc}") from last_exc
