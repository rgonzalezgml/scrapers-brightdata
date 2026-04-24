"""
connector.py — CLI connector para Snowflake GLI.

Consulta las tablas HIST + RESULT_HIST configuradas en el .env y muestra
un resumen del job más reciente (o el indicado con --job-id).
Si se pasa --tc y --test-cases, ofrece actualizar la fila del caso de prueba.

Uso:
    python .agents/skills/gli-snowflake-connect/scripts/connector.py
    python .agents/skills/gli-snowflake-connect/scripts/connector.py --job-id <UUID>
    python .agents/skills/gli-snowflake-connect/scripts/connector.py --tc TC-ONB-026
    python .agents/skills/gli-snowflake-connect/scripts/connector.py \\
        --job-id <UUID> --tc TC-ONB-008 --test-cases docs/qa/onboarding/test_cases.md

Prerequisitos:
    pip install snowflake-connector-python python-dotenv --break-system-packages
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import date
from pathlib import Path

# ---------------------------------------------------------------------------
# Dependencias opcionales — mensajes de error amigables
# ---------------------------------------------------------------------------
try:
    from dotenv import load_dotenv
except ImportError:
    print("ERROR: python-dotenv no instalado.")
    print("       pip install python-dotenv --break-system-packages")
    sys.exit(1)

try:
    import snowflake.connector
except ImportError:
    print("ERROR: snowflake-connector-python no instalado.")
    print("       pip install snowflake-connector-python --break-system-packages")
    sys.exit(1)

# .env por defecto: reference/.env dentro del skill (auto-contenido)
_SKILL_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ENV = _SKILL_ROOT / "reference" / ".env"

_REQUIRED_VARS = [
    "SNOWFLAKE_USER",
    "SNOWFLAKE_PASSWORD",
    "SNOWFLAKE_ACCOUNT",
    "SNOWFLAKE_WAREHOUSE",
    "SNOWFLAKE_DATABASE",
    "SNOWFLAKE_SCHEMA",
    "SNOWFLAKE_ROLE",
    "SNOWFLAKE_HIST_TABLE",
    "SNOWFLAKE_RESULT_TABLE",
]


# ---------------------------------------------------------------------------
# Conexión
# ---------------------------------------------------------------------------
def build_connection(env_path: Path) -> snowflake.connector.SnowflakeConnection:
    load_dotenv(env_path)

    missing = [v for v in _REQUIRED_VARS if not os.getenv(v)]
    if missing:
        print(f"ERROR: Variables faltantes en {env_path}:")
        for v in missing:
            print(f"  {v}")
        sys.exit(1)

    return snowflake.connector.connect(
        user=os.getenv("SNOWFLAKE_USER"),
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
        database=os.getenv("SNOWFLAKE_DATABASE"),
        schema=os.getenv("SNOWFLAKE_SCHEMA"),
        role=os.getenv("SNOWFLAKE_ROLE"),
    )


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------
def fetch_job(cur, job_id: str | None, user: str) -> dict | None:
    hist = os.getenv("SNOWFLAKE_HIST_TABLE")
    if job_id:
        cur.execute(
            f"""
            SELECT ALTA_ID, STATUS, METRIC, SOURCE, FILE_NAME,
                   RECEIVED, INSERTED, FAILED, ERROR_MESSAGE,
                   CREATED_AT, FINISHED_AT
            FROM {hist}
            WHERE ALTA_ID = %s
            """,
            (job_id,),
        )
    else:
        cur.execute(
            f"""
            SELECT ALTA_ID, STATUS, METRIC, SOURCE, FILE_NAME,
                   RECEIVED, INSERTED, FAILED, ERROR_MESSAGE,
                   CREATED_AT, FINISHED_AT
            FROM {hist}
            WHERE CREATED_BY = %s
            ORDER BY CREATED_AT DESC
            LIMIT 1
            """,
            (user,),
        )

    row = cur.fetchone()
    if not row:
        return None

    cols = [
        "alta_id", "status", "metric", "source", "file_name",
        "received", "inserted", "failed", "error_message",
        "created_at", "finished_at",
    ]
    return dict(zip(cols, row))


def fetch_failed_rows(cur, alta_id: str) -> list[dict]:
    result = os.getenv("SNOWFLAKE_RESULT_TABLE")
    cur.execute(
        f"""
        SELECT ROW_SEQ, STATUS, CODE, MESSAGE, IDENTIFIER, ENTITY_ID
        FROM {result}
        WHERE ALTA_ID = %s
          AND STATUS = 'FAILED'
        ORDER BY ROW_SEQ ASC
        """,
        (alta_id,),
    )
    cols = ["row_seq", "status", "code", "message", "identifier", "entity_id"]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def fetch_row_summary(cur, alta_id: str) -> dict[str, int]:
    result = os.getenv("SNOWFLAKE_RESULT_TABLE")
    cur.execute(
        f"""
        SELECT STATUS, COUNT(*) AS CNT
        FROM {result}
        WHERE ALTA_ID = %s
        GROUP BY STATUS
        """,
        (alta_id,),
    )
    return {row[0]: row[1] for row in cur.fetchall()}


# ---------------------------------------------------------------------------
# Presentación
# ---------------------------------------------------------------------------
def print_report(
    job: dict,
    failed_rows: list[dict],
    row_summary: dict[str, int],
    tc: str | None,
) -> None:
    sep = "=" * 60
    print(sep)
    print("VERIFICACION QA — Snowflake GLI")
    print(sep)
    if tc:
        print(f"Caso de prueba : {tc}")
    print(f"ALTA_ID        : {job['alta_id']}")
    print(f"STATUS         : {job['status']}")
    print(f"METRIC         : {job['metric'] or '—'}")
    print(f"SOURCE         : {job['source'] or '—'}")
    print(f"FILE_NAME      : {job['file_name'] or '—'}")
    print(f"RECEIVED       : {job['received']}")
    print(f"INSERTED       : {job['inserted']}")
    print(f"FAILED         : {job['failed']}")
    print(f"CREATED_AT     : {job['created_at']}")
    print(f"FINISHED_AT    : {job['finished_at'] or '—'}")

    if job["error_message"]:
        print(f"\nERROR TECNICO  : {job['error_message']}")

    if row_summary:
        print(f"\nRESUMEN FILAS  : {dict(row_summary)}")

    print("-" * 60)
    if failed_rows:
        print("FILAS FALLIDAS:")
        for r in failed_rows:
            print(f"  ROW {r['row_seq']} | CODE: {r['code'] or '—'}")
            if r["message"]:
                print(f"         MESSAGE: {r['message']}")
            if r["identifier"]:
                print(f"         IDENTIFIER: {r['identifier']}")
    else:
        print("Sin filas FAILED en la tabla de resultados.")

    print(sep)


# ---------------------------------------------------------------------------
# Actualizar test_cases.md
# ---------------------------------------------------------------------------
def build_evidence(job: dict, failed_rows: list[dict]) -> str:
    today = date.today().isoformat()
    parts = [
        f"BD ({today}): job `{job['status']}`",
        f"INSERTED={job['inserted']}",
        f"FAILED={job['failed']}",
    ]
    codes = ", ".join(
        f"`{r['code']}`" for r in failed_rows[:3] if r.get("code")
    )
    if codes:
        parts.append(f"Códigos: {codes}")
    return ". ".join(parts) + f". ALTA_ID: `{job['alta_id']}`."


def update_test_cases(tc_id: str, evidence: str, estado: str, path: Path) -> bool:
    """
    Edita la fila del caso de prueba en test_cases.md.
    Actualiza las dos últimas columnas (Resultado real + Estado).
    Retorna True si encontró y actualizó la fila.
    """
    if not path.exists():
        print(f"AVISO: No se encontró {path}. Actualiza manualmente.")
        return False

    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    pattern = re.compile(rf"^\|\s*{re.escape(tc_id)}\s*\|")
    updated = False

    for i, line in enumerate(lines):
        if pattern.match(line):
            cols = line.rstrip("\n").split("|")
            # Formato: | ID | Desc | Precond | Pasos | Esperado | Real | Estado |
            if len(cols) >= 8:
                cols[-3] = f" {evidence} "
                cols[-2] = f" {estado} "
                lines[i] = "|".join(cols) + "\n"
                updated = True
                break

    if updated:
        path.write_text("".join(lines), encoding="utf-8")
        print(f"Actualizado: {tc_id} → {estado} en {path}")
    else:
        print(f"AVISO: Fila '{tc_id}' no encontrada en {path}.")
        print("       Actualiza manualmente las columnas 'Resultado real' y 'Estado'.")

    return updated


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verifica el resultado de un job en Snowflake GLI.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--job-id",
        metavar="UUID",
        help="ID del job a inspeccionar. Si se omite, toma el más reciente del usuario.",
    )
    parser.add_argument(
        "--tc",
        metavar="TC-XXX-NNN",
        help="ID del caso de prueba (ej: TC-ONB-026). Contexto y actualización opcional.",
    )
    parser.add_argument(
        "--test-cases",
        metavar="PATH",
        help="Ruta a test_cases.md. Si se omite, no se ofrece actualizar.",
    )
    parser.add_argument(
        "--env",
        default=str(DEFAULT_ENV),
        metavar="PATH",
        help=f"Ruta al archivo .env (default: {DEFAULT_ENV}).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    env_path = Path(args.env)

    if not env_path.exists():
        print(f"ERROR: No se encontró el archivo .env en: {env_path}")
        print(f"       Ajusta --env o crea {DEFAULT_ENV}")
        sys.exit(1)

    conn = build_connection(env_path)
    user = os.getenv("SNOWFLAKE_USER", "").upper()

    try:
        cur = conn.cursor()

        job = fetch_job(cur, args.job_id, user)
        if not job:
            target = f"job_id={args.job_id}" if args.job_id else f"usuario={user}"
            print(f"ERROR: No se encontró ningún job en Snowflake para {target}.")
            sys.exit(1)

        failed_rows = fetch_failed_rows(cur, job["alta_id"])
        row_summary = fetch_row_summary(cur, job["alta_id"])

        print_report(job, failed_rows, row_summary, args.tc)

        if args.tc and args.test_cases:
            answer = input(f"\nMarcar {args.tc} como APROBADO en {args.test_cases}? [s/N]: ").strip().lower()
            if answer == "s":
                evidence = build_evidence(job, failed_rows)
                update_test_cases(args.tc, evidence, "APROBADO", Path(args.test_cases))
            else:
                print("Sin cambios en test_cases.md.")
        elif args.tc and not args.test_cases:
            print("\nPasa --test-cases <ruta> para actualizar el archivo automáticamente.")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
