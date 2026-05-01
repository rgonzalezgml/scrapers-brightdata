"""
ddl_gnm_mex.py — Ejecuta los cambios DDL aprobados sobre DEV_STG.GNM_MEX.

Operaciones:
  1. DROP TABLE SRC_COSME_AWARD_HIST
  2. DROP columnas legacy (DS_INPUT, DT_CARGA, ID_JOB) en 6 tablas
  3. ADD columnas de auditoria GLI en 5 tablas (excepto SRC_COSME_RANKING_HIST)
  4. ADD 27 columnas faltantes en SRC_COSME_RANKING_HIST
  5. DESCRIBE TABLE en cada tabla para validacion final
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
import snowflake.connector

# ---------------------------------------------------------------------------
# Configuracion
# ---------------------------------------------------------------------------
_ENV_PATH = Path(__file__).resolve().parent.parent / "reference" / ".env"
load_dotenv(_ENV_PATH)

CONN_PARAMS = dict(
    user=os.getenv("SNOWFLAKE_USER"),
    password=os.getenv("SNOWFLAKE_PASSWORD"),
    account=os.getenv("SNOWFLAKE_ACCOUNT"),
    warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
    database="DEV_STG",
    schema="GNM_MEX",
    role="DEVELOPER_ROLE",
)

# 6 tablas con columnas legacy
TABLES_6 = [
    "SRC_ALIBABA_PROV_HIST",
    "SRC_INDIAMART_PROV_HIST",
    "SRC_MADEINCHINA_PROV_HIST",
    "SRC_OLIVEYOUNG_RANK_HIST",
    "SRC_COSMETICDESIGN_ART_HIST",
    "SRC_COSME_RANKING_HIST",
]

# 5 tablas que necesitan columnas de auditoria GLI
TABLES_5 = [t for t in TABLES_6 if t != "SRC_COSME_RANKING_HIST"]

# 27 columnas faltantes en SRC_COSME_RANKING_HIST (tipos y COMMENTs del DDL)
COSME_NEW_COLS = [
    ("NM_PRODUCTO_JP",          "VARCHAR(16777216)",  "Nombre original del producto en japones (product_name_jp)"),
    ("URL_PRODUCTO",            "VARCHAR(16777216)",  "URL del producto en cosme.net (cosme.net/products/{id}/)"),
    ("NM_MARCA_JP",             "VARCHAR(16777216)",  "Nombre de la marca en japones (brand_name_jp)"),
    ("NM_FABRICANTE",           "VARCHAR(16777216)",  "Nombre del fabricante del producto (メーカー)"),
    ("URL_FABRICANTE",          "VARCHAR(16777216)",  "URL del perfil del fabricante en cosme.net (manufacturer_url)"),
    ("TX_CATEGORIA_FULL",       "VARCHAR(16777216)",  "Jerarquia completa de la categoria en texto (e.g. A > B > C) (category_full)"),
    ("DS_CATEGORIA_PATH",       "VARIANT",            "Jerarquia de categorias como array de objetos [{name, url}] (category_path)"),
    ("FL_PRECIO_ABIERTO",       "BOOLEAN",            "Indica si el precio es abierto (el fabricante no fija precio de venta) (is_open_price)"),
    ("FL_INCLUYE_IVA",          "BOOLEAN",            "Indica si el precio mostrado incluye impuesto (tax_included)"),
    ("NU_RATING_DETAIL",        "NUMBER(5,2)",         "Calificacion promedio detallada del producto obtenida en Stage 2 (p.average)"),
    ("NU_PUNTOS",               "NUMBER(5,2)",         "Puntaje del producto en el ranking de cosme.net (p.point, e.g. 59.1)"),
    ("NU_RANK_CATEGORIA",       "NUMBER(5,0)",         "Posicion del producto dentro de su propia categoria (cat_rank)"),
    ("NM_CATEGORIA_RANK",       "VARCHAR(16777216)",  "Nombre de la categoria en la que el producto tiene posicion de ranking (cat_rank_name)"),
    ("DS_RANKING_EN",           "VARIANT",            "Lista de rankings en los que aparece el producto como array de strings (e.g. Ranking 1 ) (ranking_in)"),
    ("NU_FOTOS",                "NUMBER(12,0)",        "Cantidad de fotos de usuarias asociadas al producto (photo_count)"),
    ("NU_QA",                   "NUMBER(12,0)",        "Cantidad de preguntas y respuestas de la comunidad (qa_count)"),
    ("NU_LIKES",                "NUMBER(12,0)",        "Cantidad de likes del producto en la comunidad"),
    ("NU_HAVES",                "NUMBER(12,0)",        "Cantidad de usuarias que marcaron el producto como que lo tienen (haves)"),
    ("TX_MODO_USO",             "VARCHAR(16777216)",  "Instrucciones de uso del producto (使い方) (how_to_use)"),
    ("TX_CLASIFICACION",        "VARCHAR(16777216)",  "Clasificacion regulatoria del producto (e.g. Iyakubuhin) (classification)"),
    ("TX_JAN_CODE",             "VARCHAR(16777216)",  "Codigo JAN (codigo de barras japones) del producto (jan_code)"),
    ("URL_OFICIAL",             "VARCHAR(16777216)",  "URL del sitio oficial del producto o fabricante (oficial_url)"),
    ("DS_IMAGENES",             "VARIANT",            "Array con todas las URLs de imagenes del producto (all_images)"),
    ("DS_TIENDAS",              "VARIANT",            "Lista de nombres de tiendas fisicas donde se vende el producto como array (stores)"),
    ("DS_PRODUCTOS_RELACIONADOS", "VARIANT",          "Productos relacionados sugeridos por cosme.net como array de objetos [{name, url}] (related_products)"),
    ("TX_SOURCE",               "VARCHAR(100)",        "Identificador de la fuente dentro del sitio (e.g. cosme.net/ranking/products) (source)"),
    ("TX_PAIS",                 "VARCHAR(10)",         "Codigo de pais ISO-2 del sitio scrapeado (e.g. JP) (country)"),
    ("TX_RANKING_POR",          "VARCHAR(20)",         "Criterio de agrupacion del ranking (e.g. product) (ranking_by)"),
]

AUDIT_COLS = [
    ("CREATED_AT",  "TIMESTAMP_NTZ(9)", "DEFAULT CURRENT_TIMESTAMP()", "Fecha y hora de creacion del registro"),
    ("UPDATED_AT",  "TIMESTAMP_NTZ(9)", "DEFAULT CURRENT_TIMESTAMP()", "Fecha y hora de ultima actualizacion del registro"),
    ("CREATED_USR", "VARCHAR(100)",     "DEFAULT CURRENT_USER()",      "Usuario que creo el registro"),
    ("UPDATED_USR", "VARCHAR(100)",     "DEFAULT CURRENT_USER()",      "Usuario que realizo la ultima actualizacion del registro"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def run(cur, sql: str, label: str) -> None:
    print(f"\n  >> {label}")
    print(f"     SQL: {sql[:120]}{'...' if len(sql) > 120 else ''}")
    try:
        cur.execute(sql)
        print(f"     OK")
    except Exception as e:
        msg = str(e)
        # IF EXISTS semantics — Snowflake returns error when col not found;
        # tolerate "does not exist" gracefully
        if "does not exist" in msg.lower() or "invalid identifier" in msg.lower():
            print(f"     SKIP (col/table ya no existe o nunca existio): {msg[:120]}")
        else:
            print(f"     ERROR: {msg}")
            raise


def describe_table(cur, table: str) -> list[tuple]:
    cur.execute(f"DESCRIBE TABLE DEV_STG.GNM_MEX.{table}")
    return cur.fetchall()


def col_names_from_describe(rows: list[tuple]) -> list[str]:
    return [r[0].upper() for r in rows]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    print("=" * 70)
    print("DDL GNM_MEX — cambios aprobados 2026-04-29")
    print("=" * 70)

    conn = snowflake.connector.connect(**CONN_PARAMS)
    cur = conn.cursor()

    # -----------------------------------------------------------------------
    # 1. DROP TABLE SRC_COSME_AWARD_HIST
    # -----------------------------------------------------------------------
    print("\n[1] DROP TABLE SRC_COSME_AWARD_HIST")
    run(cur,
        "DROP TABLE IF EXISTS DEV_STG.GNM_MEX.SRC_COSME_AWARD_HIST",
        "DROP TABLE SRC_COSME_AWARD_HIST")

    # -----------------------------------------------------------------------
    # 2. DROP columnas legacy en 6 tablas
    # -----------------------------------------------------------------------
    print("\n[2] DROP columnas legacy (DS_INPUT, DT_CARGA, ID_JOB)")
    legacy_cols = ["DS_INPUT", "DT_CARGA", "ID_JOB"]
    for table in TABLES_6:
        # Snowflake no tiene DROP COLUMN IF EXISTS — necesitamos verificar existencia
        # Usamos DESCRIBE para saber qué columnas existen
        desc = describe_table(cur, table)
        existing = col_names_from_describe(desc)
        for col in legacy_cols:
            if col in existing:
                run(cur,
                    f"ALTER TABLE DEV_STG.GNM_MEX.{table} DROP COLUMN {col}",
                    f"{table} DROP COLUMN {col}")
            else:
                print(f"  >> SKIP  {table}.{col} — no existe")

    # -----------------------------------------------------------------------
    # 3. ADD columnas de auditoria GLI en 5 tablas
    # -----------------------------------------------------------------------
    print("\n[3] ADD columnas de auditoria GLI en 5 tablas")
    for table in TABLES_5:
        desc = describe_table(cur, table)
        existing = col_names_from_describe(desc)
        for col_name, col_type, col_default, col_comment in AUDIT_COLS:
            if col_name in existing:
                print(f"  >> SKIP  {table}.{col_name} — ya existe")
            else:
                sql = (
                    f"ALTER TABLE DEV_STG.GNM_MEX.{table} "
                    f"ADD COLUMN {col_name} {col_type} {col_default} "
                    f"COMMENT '{col_comment}'"
                )
                run(cur, sql, f"{table} ADD {col_name}")

    # -----------------------------------------------------------------------
    # 4. ADD 27 columnas faltantes en SRC_COSME_RANKING_HIST
    # -----------------------------------------------------------------------
    print("\n[4] ADD 27 columnas faltantes en SRC_COSME_RANKING_HIST")
    desc_cosme = describe_table(cur, "SRC_COSME_RANKING_HIST")
    existing_cosme = col_names_from_describe(desc_cosme)

    for col_name, col_type, col_comment in COSME_NEW_COLS:
        if col_name in existing_cosme:
            print(f"  >> SKIP  SRC_COSME_RANKING_HIST.{col_name} — ya existe")
        else:
            sql = (
                f"ALTER TABLE DEV_STG.GNM_MEX.SRC_COSME_RANKING_HIST "
                f"ADD COLUMN {col_name} {col_type} "
                f"COMMENT '{col_comment}'"
            )
            run(cur, sql, f"SRC_COSME_RANKING_HIST ADD {col_name}")

    # -----------------------------------------------------------------------
    # 5. DESCRIBE TABLE — validacion final
    # -----------------------------------------------------------------------
    print("\n[5] DESCRIBE TABLE — validacion final")
    print("=" * 70)

    all_tables = TABLES_6  # includes SRC_COSME_RANKING_HIST
    for table in all_tables:
        desc = describe_table(cur, table)
        cols = col_names_from_describe(desc)
        print(f"\n  TABLE: DEV_STG.GNM_MEX.{table}  ({len(desc)} columnas)")
        for r in desc:
            # r[0]=name, r[1]=type, r[3]=nullable, r[8]=comment
            name  = r[0]
            dtype = r[1]
            comment = r[8] if len(r) > 8 else ""
            print(f"    {name:<40} {dtype:<30} {comment[:60] if comment else ''}")

    cur.close()
    conn.close()
    print("\n" + "=" * 70)
    print("DONE — todos los cambios aplicados.")
    print("=" * 70)


if __name__ == "__main__":
    main()
