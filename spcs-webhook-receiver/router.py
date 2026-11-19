from __future__ import annotations

import asyncio
import gzip
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, Callable, Union

from fastapi import APIRouter, Body, HTTPException, Query, Request, Response
from fastapi.routing import APIRoute

import snowflake_writer

from etl import extract_rows, run_etl
from registry import REGISTRY

log = logging.getLogger(__name__)


class GzipRequestRoute(APIRoute):
    """Custom route: descomprime body si Content-Encoding=gzip, antes de que FastAPI lo parsee.
    Por default BrightData envia gzip a menos que se setee uncompressed_webhook=true.
    Tambien loguea info diagnostica del body recibido para ayudar a debuggear
    payloads inesperados (ej. tests de BrightData con formato distinto).
    """

    def get_route_handler(self) -> Callable:
        original_handler = super().get_route_handler()

        async def handler(request: Request) -> Response:
            encoding = request.headers.get("content-encoding", "").lower()
            if "gzip" in encoding:
                raw = await request.body()
                try:
                    decompressed = gzip.decompress(raw)
                except OSError as e:
                    raise HTTPException(
                        status_code=400,
                        detail={"error": "invalid_gzip", "detail": str(e)},
                    )
                # Reemplaza el body para que FastAPI lo lea descomprimido
                request._body = decompressed

            # Log diagnostico de body + headers solo para /webhook/*.
            # El handler parsea el body manualmente (no depende de Content-Type),
            # asi que BrightData puede mandar sin header y aun asi procesamos.
            if request.url.path.startswith("/webhook/"):
                body = await request.body()
                preview = body[:300].decode("utf-8", errors="replace") if body else ""
                log.info(
                    "[webhook-raw] path=%s ct=%s ce=%s len=%d "
                    "x-brd-delivery-id=%s preview=%r",
                    request.url.path,
                    request.headers.get("content-type"),
                    request.headers.get("content-encoding"),
                    len(body),
                    request.headers.get("x-brd-delivery-id"),
                    preview,
                )

            return await original_handler(request)

        return handler


router = APIRouter(route_class=GzipRequestRoute)

# Enum dinamico derivado del REGISTRY -> FastAPI lo renderea como dropdown en Swagger
# y valida 422 si el cliente manda un nombre invalido (antes incluso de entrar al handler).
ScraperName = Enum("ScraperName", {name: name for name in REGISTRY}, type=str)


# Body del webhook: BrightData manda tipicamente un array de objetos, pero algunos
# datasets envuelven en {"data": [...]} / {"results": [...]} / {"items": [...]}.
# `extract_rows` (etl.py) normaliza ambos casos a list[dict].
WebhookBody = Annotated[
    Union[list[dict[str, Any]], dict[str, Any]],
    Body(
        description=(
            "Payload de webhook de BrightData. Normalmente un array de objetos "
            "(una fila por producto/articulo). Tambien acepta un objeto con la "
            "clave 'data', 'results' o 'items' conteniendo el array.\n\n"
            "**Compresion:** acepta `Content-Encoding: gzip` (default de BrightData). "
            "Si el header esta presente el body se descomprime automaticamente antes "
            "de parsear el JSON. Para enviar sin comprimir, usar `uncompressed_webhook=true` "
            "en el trigger de BrightData (no se manda el header)."
        ),
        examples=[
            [{"product_url": "https://example.com/p/1", "name": "Sample", "price": "9.99"}],
            {"data": [{"product_url": "https://example.com/p/1", "name": "Sample"}]},
        ],
    ),
]


@router.get(
    "/health",
    summary="Health check + lista de scrapers registrados",
    tags=["health"],
)
def health() -> dict[str, Any]:
    """Usado por el `readinessProbe` de SPCS. Devuelve 200 si el SERVICE arranco OK."""
    return {"status": "ok", "version": "1.0.0", "scrapers": list(REGISTRY.keys())}


@router.get(
    "/snowflake/whoami",
    summary="Devuelve el contexto Snowflake con el que se conecta el SERVICE",
    tags=["diagnostics"],
)
def whoami(request: Request) -> dict[str, Any]:
    """Abre una conexion a Snowflake y devuelve el contexto actual.

    Con `executeAsCaller: true` en el spec, SPCS inyecta el header HTTP
    `Sf-Context-Current-User-Token` con el token del caller. Si esta presente
    se usa para que la sesion se autentique como el caller (no como el service user).

    - `current_user`: el usuario dueno del PAT que llamo (ej. `RGONZALEZA`).
    - `current_role`: el rol del PAT (`ROLE_RESTRICTION`, ej. `DEVELOPER_ROLE`).
    - `current_database` / `current_schema` / `current_warehouse`: contexto default del PAT
      o lo que diga el spec (`SNOWFLAKE_DATABASE`, etc.).
    - `caller_token_present`: True si SPCS inyecto el header (executeAsCaller activo).

    Util para validar que caller mode esta activo end-to-end.
    """
    caller_token = request.headers.get("Sf-Context-Current-User-Token")
    conn = snowflake_writer.connect(caller_token=caller_token)
    try:
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT CURRENT_USER(), CURRENT_ROLE(), "
                "CURRENT_DATABASE(), CURRENT_SCHEMA(), CURRENT_WAREHOUSE(), "
                "CURRENT_ACCOUNT(), CURRENT_SESSION()"
            )
            row = cur.fetchone()
            result = {
                "current_user": row[0],
                "current_role": row[1],
                "current_database": row[2],
                "current_schema": row[3],
                "current_warehouse": row[4],
                "current_account": row[5],
                "current_session": str(row[6]) if row[6] is not None else None,
                "caller_token_present": caller_token is not None,
            }

            # Probes diagnosticos para entender el restricted caller's rights context.
            probes: list[dict[str, Any]] = []

            def probe(label: str, sql: str) -> None:
                try:
                    cur.execute(sql)
                    rows = cur.fetchall()
                    probes.append({
                        "label": label, "sql": sql, "ok": True,
                        "rows_count": len(rows),
                        "first_row": [str(c) for c in rows[0]] if rows else None,
                    })
                except Exception as e:
                    probes.append({
                        "label": label, "sql": sql, "ok": False,
                        "error_type": type(e).__name__, "error": str(e),
                    })

            probe("basic", "SELECT 1")
            probe("available_roles", "SELECT CURRENT_AVAILABLE_ROLES()")
            probe("secondary_roles_before", "SELECT CURRENT_SECONDARY_ROLES()")
            probe("show_databases_before", "SHOW DATABASES LIKE 'DEV_STG'")
            probe("set_secondary_roles_all", "USE SECONDARY ROLES ALL")
            probe("secondary_roles_after", "SELECT CURRENT_SECONDARY_ROLES()")
            probe("show_databases_after", "SHOW DATABASES LIKE 'DEV_STG'")
            probe("count_oliveyoung_rank",
                  "SELECT COUNT(*) FROM DEV_STG.GNM_MEX.SRC_OLIVEYOUNG_RANK_HIST")
            result["probes"] = probes
            return result
        finally:
            cur.close()
    finally:
        conn.close()


@router.post(
    "/webhook/{scraper_name}",
    summary="Recibe payload de BrightData y lo persiste en SRC_*_HIST",
    response_description="Resumen del ETL: filas insertadas, errores, descartadas y filtradas",
    tags=["webhook"],
)
async def webhook(
    scraper_name: ScraperName,
    request: Request,
    clean: bool = Query(default=False, description="Si true, borra la tabla antes de insertar (replace en lugar de append)."),
) -> dict[str, Any]:
    """Endpoint principal del receptor de webhooks.

    **Flujo:**
    1. Si el body llega con `Content-Encoding: gzip`, se descomprime.
    2. El JSON se normaliza a una lista de filas (acepta array o {data/results/items: [...]}).
    3. Se delega el ETL al cliente `gli_scrapers.<scraper>.client` correspondiente.
    4. Las filas validas se insertan en `DEV_STG.GNM_MEX.SRC_<scraper>_HIST` (o el destino
       configurado por el spec del SERVICE).

    **Codigos de error:**
    - `400 invalid_gzip`: header `Content-Encoding: gzip` pero el body no es gzip valido.
    - `422`: body JSON malformado, `scraper_name` no esta en el enum, o la estructura del
      payload no coincide con lo esperado (`validation_error`).
    - `500 internal_error`: error en el ETL o en el insert.
    - `503 snowflake_unavailable`: Snowflake no respondio tras reintentos.
    """
    # FastAPI ya valido que scraper_name esta en REGISTRY -> el lookup nunca falla
    name = scraper_name.value
    handler = REGISTRY[name]

    # Parsear el body manualmente (BrightData no envia Content-Type, FastAPI
    # rechazaria con 422 si dependieramos del schema declarativo del request body).
    raw_body = await request.body()
    try:
        import json as _json
        body = _json.loads(raw_body) if raw_body else []
    except (ValueError, UnicodeDecodeError) as e:
        raise HTTPException(status_code=400, detail={"error": "invalid_json", "detail": str(e)})

    try:
        raw_rows = extract_rows(body)
    except ValueError as e:
        raise HTTPException(status_code=422, detail={"error": "validation_error", "detail": str(e)})

    job_id = f"{name}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    log.info("[%s] webhook received — %d raw rows (job_id=%s)", name, len(raw_rows), job_id)

    try:
        normalized_rows, error_count, skipped_count, filtered_count = run_etl(raw_rows, handler)
    except Exception as e:
        log.exception("[%s] ETL failed", name)
        raise HTTPException(status_code=500, detail={"error": "internal_error", "detail": str(e)})

    caller_token = request.headers.get("Sf-Context-Current-User-Token")
    try:
        inserted = await asyncio.to_thread(
            snowflake_writer.write_with_retry,
            normalized_rows, handler.mapper, job_id=job_id,
            caller_token=caller_token, clean=clean,
        )
    except RuntimeError as e:
        log.error("[%s] Snowflake unavailable: %s", name, e)
        raise HTTPException(status_code=503, detail={"error": "snowflake_unavailable", "detail": str(e)})
    except Exception as e:
        log.exception("[%s] insert failed", name)
        raise HTTPException(status_code=500, detail={"error": "internal_error", "detail": str(e)})

    log.info(
        "[%s] done — inserted=%d errors=%d skipped=%d filtered=%d",
        name, inserted, error_count, skipped_count, filtered_count,
    )
    return {
        "inserted": inserted,
        "errors": error_count,
        "skipped": skipped_count,
        "filtered": filtered_count,
        "job_id": job_id,
    }
