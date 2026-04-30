"""
alter_defaults.py — Aplica DEFAULT a columnas de auditoría en tablas DEV_STG.GNM_MEX.

Tablas 1-5 (owner SYSADMIN): SERVICIO_GENOMMA_01
Tabla 6 (owner DEVELOPER_ROLE): RGONZALEZA

Prueba en orden:
  1. ALTER TABLE ... ALTER COLUMN ... SET DEFAULT ...
  2. ALTER TABLE ... MODIFY COLUMN ... DEFAULT ...
  3. ALTER TABLE ... MODIFY COLUMN ... SET DEFAULT ...  (variante 3)
"""

from __future__ import annotations

import snowflake.connector

ACCOUNT   = "qob68501-genommalab"
WAREHOUSE = "GENOMMA"
DATABASE  = "DEV_STG"
SCHEMA    = "GNM_MEX"

GROUPS = [
    {
        "label": "SYSADMIN (SERVICIO_GENOMMA_01)",
        "user":     "SERVICIO_GENOMMA_01",
        "password": "Mu2lQitHa2",
        "role":     "SYSADMIN",
        "tables": [
            "SRC_ALIBABA_PROV_HIST",
            "SRC_INDIAMART_PROV_HIST",
            "SRC_MADEINCHINA_PROV_HIST",
            "SRC_OLIVEYOUNG_RANK_HIST",
            "SRC_COSMETICDESIGN_ART_HIST",
        ],
    },
    {
        "label": "DEVELOPER_ROLE (RGONZALEZA)",
        "user":     "RGONZALEZA",
        "password": "S@msungXboom2025*",
        "role":     "DEVELOPER_ROLE",
        "tables": [
            "SRC_COSME_RANKING_HIST",
        ],
    },
]

# Sintaxis a probar, en orden. Se detiene en la primera que no arroje error.
SYNTAX_VARIANTS = [
    # Variante 1 — ALTER COLUMN ... SET DEFAULT
    lambda tbl, col, val: (
        f"ALTER TABLE {DATABASE}.{SCHEMA}.{tbl} ALTER COLUMN {col} SET DEFAULT {val}"
    ),
    # Variante 2 — MODIFY COLUMN ... DEFAULT (sin SET)
    lambda tbl, col, val: (
        f"ALTER TABLE {DATABASE}.{SCHEMA}.{tbl} MODIFY COLUMN {col} DEFAULT {val}"
    ),
    # Variante 3 — MODIFY COLUMN ... SET DEFAULT
    lambda tbl, col, val: (
        f"ALTER TABLE {DATABASE}.{SCHEMA}.{tbl} MODIFY COLUMN {col} SET DEFAULT {val}"
    ),
]

COLUMNS = [
    ("CREATED_AT",  "CURRENT_TIMESTAMP()"),
    ("UPDATED_AT",  "CURRENT_TIMESTAMP()"),
    ("CREATED_USR", "CURRENT_USER()"),
    ("UPDATED_USR", "CURRENT_USER()"),
]


def connect(group: dict) -> snowflake.connector.SnowflakeConnection:
    return snowflake.connector.connect(
        user=group["user"],
        password=group["password"],
        account=ACCOUNT,
        warehouse=WAREHOUSE,
        database=DATABASE,
        schema=SCHEMA,
        role=group["role"],
    )


def try_variants(cur, table: str, col: str, val: str) -> tuple[int | None, str]:
    """
    Intenta cada variante de sintaxis.
    Devuelve (variant_index_1based, result_msg).
    """
    last_err = ""
    for idx, build_sql in enumerate(SYNTAX_VARIANTS, start=1):
        sql = build_sql(table, col, val)
        try:
            cur.execute(sql)
            return idx, "OK"
        except snowflake.connector.errors.ProgrammingError as e:
            last_err = f"[v{idx}] {e.msg}"
    return None, last_err


def process_group(group: dict) -> None:
    print(f"\n{'='*70}")
    print(f"GRUPO: {group['label']}")
    print(f"{'='*70}")

    try:
        conn = connect(group)
    except Exception as e:
        print(f"  ERROR de conexion: {e}")
        return

    cur = conn.cursor()

    for table in group["tables"]:
        print(f"\n  Tabla: {table}")
        for col, val in COLUMNS:
            variant_ok, msg = try_variants(cur, table, col, val)
            status = f"VARIANTE {variant_ok}" if variant_ok else "FALLO TODAS"
            print(f"    {col:<15} -> {status} | {msg}")

    conn.close()


def main() -> None:
    for group in GROUPS:
        process_group(group)
    print(f"\n{'='*70}")
    print("Listo.")


if __name__ == "__main__":
    main()
