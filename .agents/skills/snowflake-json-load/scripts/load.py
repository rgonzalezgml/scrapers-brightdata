"""
load.py — Carga de emergencia JSON → Snowflake.

Lee un archivo JSON (array de objetos), detecta el mapping campo→columna y
usa write_pandas para insertar. Tres modos de mapping:

  1. Auto-detect     (sin --map ni --map-from-config)
     Compara claves JSON contra columnas de la tabla (útil cuando coinciden).

  2. Config AST      (--map-from-config gli_scrapers/<name>/config.py)
     Lee el field_map del SnowflakeMapper en el config.py del middleware.
     Es el modo canónico para scrapers de este repo.

  3. JSON explícito  (--map mapping.json)
     {"json_key": "COLUMN_NAME"} — máximo control.

Uso:
    python .agents/skills/snowflake-json-load/scripts/load.py \\
        --file bd_scrapers/cosme-ranking-products/results/j_xxx.json \\
        --table DEV_STG.GNM_MEX.SRC_COSME_RANKING_HIST \\
        --map-from-config gli_scrapers/cosme_ranking_products/config.py \\
        --job-id j_xxx

Prerequisitos:
    pip install "snowflake-connector-python[pandas]" python-dotenv pandas \\
        --break-system-packages
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Dependencias opcionales
# ---------------------------------------------------------------------------
try:
    from dotenv import load_dotenv
except ImportError:
    print("ERROR: pip install python-dotenv --break-system-packages")
    sys.exit(1)

try:
    import snowflake.connector
    from snowflake.connector.pandas_tools import write_pandas
except ImportError:
    print("ERROR: pip install 'snowflake-connector-python[pandas]' --break-system-packages")
    sys.exit(1)

try:
    import pandas as pd
except ImportError:
    print("ERROR: pip install pandas --break-system-packages")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Helpers de tipo
# ---------------------------------------------------------------------------

DATE_FORMATS = ["%Y/%m/%d", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"]


def _try_parse_date(value: str):
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except (ValueError, TypeError):
            continue
    return value


def _try_parse_ts(value: str):
    if not isinstance(value, str):
        return value
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return value


def _coerce(value, sf_type: str):
    """Convierte un valor Python al tipo Snowflake esperado."""
    t = sf_type.upper()
    if value is None:
        return None
    if "VARIANT" in t:
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        return value
    if t.startswith("DATE"):
        if isinstance(value, str):
            return _try_parse_date(value)
        return value
    if "TIMESTAMP" in t:
        if isinstance(value, str):
            return _try_parse_ts(value)
        return value
    if t in ("BOOLEAN", "BOOL"):
        if isinstance(value, str):
            return value.lower() in ("true", "1", "yes", "sí", "si")
        return bool(value)
    return value


# ---------------------------------------------------------------------------
# Schema de la tabla
# ---------------------------------------------------------------------------

def fetch_schema(cur, table: str) -> dict[str, str]:
    """Retorna {COLUMN_NAME: DATA_TYPE} desde DESCRIBE TABLE."""
    cur.execute(f"DESCRIBE TABLE {table}")
    rows = cur.fetchall()
    return {r[0].upper(): r[1].upper() for r in rows}


# ---------------------------------------------------------------------------
# Modos de mapping
# ---------------------------------------------------------------------------

def _normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def build_auto_mapping(json_keys: list[str], schema: dict[str, str]) -> dict[str, str]:
    """Auto-detecta {json_key: COLUMN} comparando nombres."""
    col_norm = {_normalize(col): col for col in schema}
    mapping: dict[str, str] = {}
    unmatched: list[str] = []
    for key in json_keys:
        col = None
        if key.upper() in schema:
            col = key.upper()
        elif key.upper().replace("-", "_") in schema:
            col = key.upper().replace("-", "_")
        elif _normalize(key) in col_norm:
            col = col_norm[_normalize(key)]
        if col:
            mapping[key] = col
        else:
            unmatched.append(key)
    if unmatched:
        print(f"  [AVISO] Sin match (ignorados): {unmatched}")
    return mapping


def load_mapping_from_json(path: str) -> dict[str, str]:
    """Lee mapping desde un JSON {json_key: COLUMN_NAME}."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_mapping_from_config(path: str) -> dict[str, str]:
    """
    Extrae el field_map del SnowflakeMapper en un config.py de middleware.

    Parsea el AST sin importar el módulo (no necesita dependencias del proyecto).
    Busca la primera llamada a SnowflakeMapper(...) y extrae el kwarg field_map.
    """
    source = Path(path).read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        print(f"ERROR: No se pudo parsear {path}: {e}")
        sys.exit(1)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        # SnowflakeMapper(...) o alias.SnowflakeMapper(...)
        func = node.func
        is_mapper = (
            (isinstance(func, ast.Name) and func.id == "SnowflakeMapper")
            or (isinstance(func, ast.Attribute) and func.attr == "SnowflakeMapper")
        )
        if not is_mapper:
            continue
        for kw in node.keywords:
            if kw.arg == "field_map":
                try:
                    raw = ast.literal_eval(kw.value)
                    # raw: {json_key: column_name}
                    return {k: v.upper() for k, v in raw.items()}
                except ValueError as e:
                    print(f"ERROR: field_map no es un literal evaluable: {e}")
                    sys.exit(1)

    print(f"ERROR: No se encontró SnowflakeMapper con field_map en {path}")
    sys.exit(1)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Carga de emergencia JSON → Snowflake")
    p.add_argument("--file",            required=True, help="Ruta al JSON (array de objetos)")
    p.add_argument("--table",           required=True, help="Tabla destino: DB.SCHEMA.TABLE")
    p.add_argument("--map",             help="JSON con mapping explícito {json_key: COLUMN}")
    p.add_argument("--map-from-config", help="Path a config.py del middleware (extrae field_map del SnowflakeMapper)")
    p.add_argument("--job-id",          help="Valor para ID_JOB (si la columna existe)")
    p.add_argument("--role",            default="DEVELOPER_ROLE", help="Rol Snowflake (default: DEVELOPER_ROLE)")
    p.add_argument("--env",             default=".env", help="Ruta al .env (default: .env)")
    p.add_argument("--dry-run",         action="store_true", help="Muestra el plan sin insertar")
    p.add_argument("--overwrite",       action="store_true", help="Trunca la tabla antes de insertar")
    return p.parse_args()


def main():
    args = parse_args()

    # Credenciales
    env_path = Path(args.env)
    if not env_path.exists():
        print(f"ERROR: .env no encontrado en {env_path}")
        sys.exit(1)
    load_dotenv(env_path)

    for k in ["SNOWFLAKE_USER", "SNOWFLAKE_PASSWORD", "SNOWFLAKE_ACCOUNT", "SNOWFLAKE_WAREHOUSE"]:
        if not os.getenv(k):
            print(f"ERROR: Falta {k} en .env")
            sys.exit(1)

    # Leer JSON
    file_path = Path(args.file)
    if not file_path.exists():
        print(f"ERROR: Archivo no encontrado: {file_path}")
        sys.exit(1)
    with open(file_path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list) or not data:
        print("ERROR: El JSON debe ser un array no vacío de objetos.")
        sys.exit(1)
    print(f"Archivo  : {file_path}  ({len(data)} registros)")

    # Parsear tabla
    table_parts = args.table.split(".")
    if len(table_parts) == 3:
        database, schema, table_name = table_parts
    elif len(table_parts) == 1:
        database   = os.getenv("SNOWFLAKE_DATABASE", "")
        schema     = os.getenv("SNOWFLAKE_SCHEMA", "")
        table_name = table_parts[0]
    else:
        print("ERROR: --table debe ser DB.SCHEMA.TABLE")
        sys.exit(1)
    full_table = f"{database}.{schema}.{table_name}"
    print(f"Tabla    : {full_table}")

    # Conectar
    print(f"Rol      : {args.role}")
    conn = snowflake.connector.connect(
        user=os.getenv("SNOWFLAKE_USER"),
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
        database=database or os.getenv("SNOWFLAKE_DATABASE", ""),
        schema=schema or os.getenv("SNOWFLAKE_SCHEMA", ""),
        role=args.role,
    )
    cur = conn.cursor()

    # Schema de la tabla
    try:
        sf_schema = fetch_schema(cur, full_table)
    except Exception as e:
        print(f"ERROR describiendo tabla: {e}")
        conn.close()
        sys.exit(1)
    print(f"Columnas : {len(sf_schema)} en la tabla\n")

    # Mapping
    all_keys = list({k for row in data for k in row})
    if args.map_from_config:
        print(f"Modo     : field_map desde {args.map_from_config}")
        raw_map = load_mapping_from_config(args.map_from_config)
        # Filtrar columnas que no existen en la tabla (esquema puede diferir)
        mapping = {jk: col for jk, col in raw_map.items() if col in sf_schema}
        missing_cols = {col for col in raw_map.values() if col not in sf_schema}
        if missing_cols:
            print(f"  [AVISO] Columnas del config ausentes en la tabla: {missing_cols}")
    elif args.map:
        print(f"Modo     : mapping explícito desde {args.map}")
        raw_map = load_mapping_from_json(args.map)
        mapping = {jk: col.upper() for jk, col in raw_map.items() if col.upper() in sf_schema}
    else:
        print("Modo     : auto-detect")
        mapping = build_auto_mapping(all_keys, sf_schema)

    print(f"Mapeados : {len(mapping)} campo(s)")
    for jk, col in sorted(mapping.items()):
        print(f"  {jk:35s} → {col} ({sf_schema.get(col, '?')})")

    if not mapping:
        print("\nERROR: Ningún campo mapeado. Usa --map-from-config o --map.")
        conn.close()
        sys.exit(1)

    # Construir DataFrame
    rows = []
    for r in data:
        row: dict = {}
        for jk, col in mapping.items():
            row[col] = _coerce(r.get(jk), sf_schema[col])
        if args.job_id and "ID_JOB" in sf_schema:
            row["ID_JOB"] = args.job_id
        rows.append(row)

    df = pd.DataFrame(rows)
    print(f"\nDataFrame: {len(df)} filas × {len(df.columns)} columnas")

    if args.dry_run:
        print("\n[DRY RUN] Primera fila (valores coercidos):")
        print(json.dumps({k: str(v) for k, v in rows[0].items()}, indent=2, ensure_ascii=False))
        conn.close()
        return

    if args.overwrite:
        print(f"\nTruncando {full_table}...")
        cur.execute(f"TRUNCATE TABLE {full_table}")

    print("Insertando...")
    success, nchunks, nrows, _ = write_pandas(
        conn, df, table_name.upper(),
        database=database.upper(),
        schema=schema.upper(),
        quote_identifiers=False,
    )

    if success:
        print(f"OK — {nrows} filas insertadas en {nchunks} chunk(s).")
    else:
        print("ERROR: write_pandas reportó fallo.")
        sys.exit(1)

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
