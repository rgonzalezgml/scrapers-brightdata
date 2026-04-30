"""
load_scrapers_prd.py — Carga emergencia de resultados de scrapers en PRD_STG.GNM.

Scrapers cubiertos:
  1. indiamart       → SRC_INDIAMART_PROV_HIST
  2. made-in-china   → SRC_MADEINCHINA_PROV_HIST
  3. cosme-ranking   → SRC_COSME_RANKING_HIST
  4. cosmetics-design→ SRC_COSMETICDESIGN_ART_HIST
  5. olive-young     → SRC_OLIVEYOUNG_RANK_HIST

Uso: python scripts/load_scrapers_prd.py [--dry-run]
"""

from __future__ import annotations

import json
import os
import sys
import argparse
from pathlib import Path
from datetime import date, datetime

try:
    from dotenv import load_dotenv
    import snowflake.connector
except ImportError:
    print("ERROR: pip install snowflake-connector-python python-dotenv --break-system-packages")
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = REPO_ROOT / ".agents" / "skills" / "gli-snowflake-connect" / "reference" / ".env"
load_dotenv(ENV_PATH)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def jdump(v) -> str | None:
    """Serializa dict/list a JSON string para columnas VARIANT."""
    if v is None:
        return None
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)
    return str(v)

def parse_date(s) -> str | None:
    """Normaliza '2026/4/16' o '2026-04-16' a 'YYYY-MM-DD'."""
    if not s:
        return None
    s = str(s).strip().replace("/", "-")
    parts = s.split("-")
    if len(parts) == 3:
        return f"{parts[0]}-{parts[1].zfill(2)}-{parts[2].zfill(2)}"
    return None

def parse_ts(s) -> str | None:
    """Normaliza timestamp ISO 8601 a string compatible con Snowflake TIMESTAMP_NTZ."""
    if not s:
        return None
    s = str(s).strip()
    # "2026-04-28T05:22:33.969Z" → "2026-04-28 05:22:33.969"
    s = s.replace("Z", "").replace("T", " ")
    return s


def load_json(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else [data]


def insert_rows(cur, table: str, col_types: list[tuple], rows: list[dict], dry_run: bool = False) -> int:
    """
    col_types: [(col_name, type_hint)]
      type_hint: 'variant' | 'date' | 'ts' | 'str' | 'num' | 'bool'
    Usa INSERT INTO … SELECT para soportar PARSE_JSON (no permitido en VALUES).
    """
    if not rows:
        return 0

    cols = [c for c, _ in col_types]
    # PARSE_JSON sólo es válido en SELECT, nunca en VALUES
    selects = ["PARSE_JSON(%s)" if t == "variant" else "%s" for _, t in col_types]
    sql = (
        f"INSERT INTO PRD_STG.GNM.{table} "
        f"({', '.join(cols)}) "
        f"SELECT {', '.join(selects)}"
    )

    def transform(row: dict) -> list:
        vals = []
        for col, hint in col_types:
            v = row.get(col)
            if hint == "variant":
                vals.append(jdump(v))
            elif hint == "date":
                vals.append(parse_date(v))
            elif hint == "ts":
                vals.append(parse_ts(v))
            elif hint == "bool":
                vals.append(bool(v) if v is not None else None)
            elif hint == "num":
                vals.append(v)
            else:
                vals.append(str(v) if v is not None else None)
        return vals

    if dry_run:
        batch_size = 500
        for i in range(0, len(rows), batch_size):
            batch = rows[i : i + batch_size]
            print(f"    [DRY-RUN] INSERT {table} → {len(batch)} filas (batch {i//batch_size + 1})")
        return len(rows)

    # execute() por fila (executemany no puede combinar INSERT…SELECT)
    for row in rows:
        cur.execute(sql, transform(row))
    return len(rows)


# ---------------------------------------------------------------------------
# Mapeos por scraper
# ---------------------------------------------------------------------------

def map_indiamart(rows: list[dict]) -> list[dict]:
    """Renombra keys del JSON al nombre de columna DDL."""
    out = []
    for r in rows:
        out.append({
            "ID_PRODUCTO":          r.get("product_id"),
            "URL_PRODUCTO":         r.get("product_url"),
            "NM_PRODUCTO_ORIGINAL": r.get("product_name_original"),
            "NM_PRODUCTO_CLEAN":    r.get("product_name_clean"),
            "TX_DESCRIPCION":       r.get("product_description"),
            "TX_TIPO":              r.get("type"),
            "TX_CATEGORIA_MIC":     r.get("category_mic"),
            "DS_CATEGORIA_PATH":    r.get("category_path"),
            "DS_PRECIO_MIN_USD":    r.get("price_min_usd"),
            "DS_PRECIO_MAX_USD":    r.get("price_max_usd"),
            "TX_PRECIO_RAW":        r.get("price_raw"),
            "TX_PRECIO_VALOR_RAW":  r.get("price_value_raw"),
            "TX_UNIDAD_PRECIO":     r.get("price_unit"),
            "TX_MONEDA":            r.get("price_currency"),
            "TX_DISPONIBILIDAD":    r.get("availability"),
            "ID_PROVEEDOR":         r.get("supplier_id"),
            "NM_PROVEEDOR":         r.get("supplier_name"),
            "URL_PROVEEDOR":        r.get("supplier_url"),
            "TX_CIUDAD_PROVEEDOR":  r.get("supplier_city"),
            "TX_PAIS_PROVEEDOR":    r.get("supplier_country"),
            "FL_VERIFICADO":        r.get("verified"),
            "FL_TRUSTSEAL":         r.get("trustseal"),
            "NU_ANIO_MIEMBRO":      r.get("member_since_year"),
            "URL_IMAGEN":           r.get("image_primary"),
            "TX_SITIO":             r.get("site_code"),
            "DS_FLAGS":             r.get("scraper_flags"),
            "DT_SCRAPING":          r.get("scraped_date"),
            "FT_FUENTE":            "indiamart",
        })
    return out

INDIAMART_COLS = [
    ("ID_PRODUCTO",          "str"),
    ("URL_PRODUCTO",         "str"),
    ("NM_PRODUCTO_ORIGINAL", "str"),
    ("NM_PRODUCTO_CLEAN",    "str"),
    ("TX_DESCRIPCION",       "str"),
    ("TX_TIPO",              "str"),
    ("TX_CATEGORIA_MIC",     "str"),
    ("DS_CATEGORIA_PATH",    "variant"),
    ("DS_PRECIO_MIN_USD",    "variant"),
    ("DS_PRECIO_MAX_USD",    "variant"),
    ("TX_PRECIO_RAW",        "str"),
    ("TX_PRECIO_VALOR_RAW",  "str"),
    ("TX_UNIDAD_PRECIO",     "str"),
    ("TX_MONEDA",            "str"),
    ("TX_DISPONIBILIDAD",    "str"),
    ("ID_PROVEEDOR",         "str"),
    ("NM_PROVEEDOR",         "str"),
    ("URL_PROVEEDOR",        "str"),
    ("TX_CIUDAD_PROVEEDOR",  "str"),
    ("TX_PAIS_PROVEEDOR",    "str"),
    ("FL_VERIFICADO",        "bool"),
    ("FL_TRUSTSEAL",         "bool"),
    ("NU_ANIO_MIEMBRO",      "num"),
    ("URL_IMAGEN",           "str"),
    ("TX_SITIO",             "str"),
    ("DS_FLAGS",             "variant"),
    ("DT_SCRAPING",          "date"),
    ("FT_FUENTE",            "str"),
]


def map_made_in_china(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        out.append({
            "ID_PRODUCTO":          r.get("product_id"),
            "TX_SKU":               r.get("sku"),
            "URL_PRODUCTO":         r.get("product_url"),
            "NM_PRODUCTO_ORIGINAL": r.get("product_name_original"),
            "NM_PRODUCTO_CLEAN":    r.get("product_name_clean"),
            "TX_TIPO":              r.get("type"),
            "TX_CATEGORIA_MIC":     r.get("category_mic"),
            "DS_CATEGORIA_PATH":    r.get("category_path"),
            "DS_PRECIO_MIN_USD":    r.get("price_min_usd"),
            "DS_PRECIO_MAX_USD":    r.get("price_max_usd"),
            "TX_PRECIO_RAW":        r.get("price_raw"),
            "TX_MONEDA":            r.get("price_currency"),
            "NU_MOQ_CANTIDAD":      r.get("moq_quantity"),
            "TX_MOQ_UNIDAD":        r.get("moq_unit"),
            "TX_CAS":               r.get("cas_no"),
            "TX_FORMULA":           r.get("formula"),
            "TX_EINECS":            r.get("einecs"),
            "TX_GRADO":             r.get("grade"),
            "TX_APARIENCIA":        r.get("appearance"),
            "ID_PROVEEDOR":         r.get("supplier_id"),
            "NM_PROVEEDOR_RAW":     r.get("supplier_name_raw"),
            "URL_IMAGEN":           r.get("image_primary"),
            "TX_SITIO":             r.get("site_code"),
            "DS_FLAGS":             r.get("scraper_flags"),
            "DT_SCRAPING":          r.get("scraped_date"),
            "FT_FUENTE":            "made_in_china",
        })
    return out

MADE_IN_CHINA_COLS = [
    ("ID_PRODUCTO",          "str"),
    ("TX_SKU",               "str"),
    ("URL_PRODUCTO",         "str"),
    ("NM_PRODUCTO_ORIGINAL", "str"),
    ("NM_PRODUCTO_CLEAN",    "str"),
    ("TX_TIPO",              "str"),
    ("TX_CATEGORIA_MIC",     "str"),
    ("DS_CATEGORIA_PATH",    "variant"),
    ("DS_PRECIO_MIN_USD",    "variant"),
    ("DS_PRECIO_MAX_USD",    "variant"),
    ("TX_PRECIO_RAW",        "str"),
    ("TX_MONEDA",            "str"),
    ("NU_MOQ_CANTIDAD",      "num"),
    ("TX_MOQ_UNIDAD",        "str"),
    ("TX_CAS",               "str"),
    ("TX_FORMULA",           "str"),
    ("TX_EINECS",            "str"),
    ("TX_GRADO",             "str"),
    ("TX_APARIENCIA",        "str"),
    ("ID_PROVEEDOR",         "str"),
    ("NM_PROVEEDOR_RAW",     "str"),
    ("URL_IMAGEN",           "str"),
    ("TX_SITIO",             "str"),
    ("DS_FLAGS",             "variant"),
    ("DT_SCRAPING",          "date"),
    ("FT_FUENTE",            "str"),
]


def map_cosme(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        out.append({
            "NU_RANK":              r.get("rank"),
            "TX_RANK_CAMBIO":       r.get("rank_change"),
            "ID_PRODUCTO":          r.get("product_id"),
            "NM_PRODUCTO":          r.get("product_name"),
            "URL_IMG_PRINCIPAL":    r.get("product_img"),
            "ID_MARCA":             r.get("brand_id"),
            "NM_MARCA":             r.get("brand_name"),
            "URL_MARCA":            r.get("brand_url"),
            "NM_CATEGORIA":         r.get("category"),
            "URL_CATEGORIA":        r.get("category_url"),
            "TX_PRECIO_RAW":        r.get("price_text"),
            "NU_PRECIO_YEN":        r.get("price_yen"),
            "FL_PRECIO_ABIERTO":    r.get("is_open_price"),
            "FL_INCLUYE_IVA":       r.get("tax_included"),
            "NU_RATING":            r.get("rating"),
            "NU_RESENAS":           r.get("review_count"),
            "TX_FECHA_LANZAMIENTO": r.get("release_date"),
            "FL_BEST_COSME":        r.get("is_best_cosme"),
            "FL_NUEVO":             r.get("is_new"),
            "TX_DESCRIPCION":       r.get("description"),
            "DS_IMAGENES":          r.get("all_images"),
            "TX_INGREDIENTES":      r.get("ingredients"),
            "URL_TIENDA":           r.get("shop_url"),
            "DT_PERIODO_INICIO":    r.get("period_start"),
            "DT_PERIODO_FIN":       r.get("period_end"),
            "DT_SCRAPING":          r.get("scraped_at"),
            "NU_TOTAL_RANKING":     r.get("total_products"),
            "FT_FUENTE":            "cosme_ranking_products",
        })
    return out

COSME_COLS = [
    ("NU_RANK",              "num"),
    ("TX_RANK_CAMBIO",       "str"),
    ("ID_PRODUCTO",          "str"),
    ("NM_PRODUCTO",          "str"),
    ("URL_IMG_PRINCIPAL",    "str"),
    ("ID_MARCA",             "str"),
    ("NM_MARCA",             "str"),
    ("URL_MARCA",            "str"),
    ("NM_CATEGORIA",         "str"),
    ("URL_CATEGORIA",        "str"),
    ("TX_PRECIO_RAW",        "str"),
    ("NU_PRECIO_YEN",        "num"),
    ("FL_PRECIO_ABIERTO",    "bool"),
    ("FL_INCLUYE_IVA",       "bool"),
    ("NU_RATING",            "num"),
    ("NU_RESENAS",           "num"),
    ("TX_FECHA_LANZAMIENTO", "str"),
    ("FL_BEST_COSME",        "bool"),
    ("FL_NUEVO",             "bool"),
    ("TX_DESCRIPCION",       "str"),
    ("DS_IMAGENES",          "variant"),
    ("TX_INGREDIENTES",      "str"),
    ("URL_TIENDA",           "str"),
    ("DT_PERIODO_INICIO",    "date"),
    ("DT_PERIODO_FIN",       "date"),
    ("DT_SCRAPING",          "ts"),
    ("NU_TOTAL_RANKING",     "num"),
    ("FT_FUENTE",            "str"),
]


def map_cosmetics_design(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        out.append({
            "TX_TITULO":      r.get("article_title"),
            "URL_ARTICULO":   r.get("article_url"),
            "DT_PUBLICACION": r.get("publication_date"),
            "TX_RESUMEN":     r.get("article_summary"),
            "TX_CONTENIDO":   r.get("article_content"),
            "FL_PAYWALL":     r.get("paywalled"),
            "URL_IMAGEN":     r.get("lead_image_url"),
            "TX_PIE_IMAGEN":  r.get("image_caption"),
            "DS_TEMAS":       r.get("related_topics"),
            "FT_FUENTE":      "cosmetics_design",
        })
    return out

COSMETICS_DESIGN_COLS = [
    ("TX_TITULO",      "str"),
    ("URL_ARTICULO",   "str"),
    ("DT_PUBLICACION", "ts"),
    ("TX_RESUMEN",     "str"),
    ("TX_CONTENIDO",   "str"),
    ("FL_PAYWALL",     "bool"),
    ("URL_IMAGEN",     "str"),
    ("TX_PIE_IMAGEN",  "str"),
    ("DS_TEMAS",       "variant"),
    ("FT_FUENTE",      "str"),
]


def map_olive_young(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        out.append({
            "NU_RANK":           r.get("rank"),
            "ID_PRODUCTO":       r.get("prdtNo"),
            "NM_MARCA":          r.get("brand"),
            "NM_PRODUCTO":       r.get("name"),
            "NM_PRODUCTO_KR":    r.get("name_kr"),
            "TX_PRECIO_ORIGINAL":r.get("original_price"),
            "TX_PRECIO_OFERTA":  r.get("sale_price"),
            "NU_RATING":         r.get("rating"),
            "URL_IMAGEN":        r.get("image"),
            "FL_SIN_STOCK":      r.get("out_of_stock"),
            "FT_FUENTE":         "olive_young",
        })
    return out

OLIVE_YOUNG_COLS = [
    ("NU_RANK",            "num"),
    ("ID_PRODUCTO",        "str"),
    ("NM_MARCA",           "str"),
    ("NM_PRODUCTO",        "str"),
    ("NM_PRODUCTO_KR",     "str"),
    ("TX_PRECIO_ORIGINAL", "str"),
    ("TX_PRECIO_OFERTA",   "str"),
    ("NU_RATING",          "num"),
    ("URL_IMAGEN",         "str"),
    ("FL_SIN_STOCK",       "bool"),
    ("FT_FUENTE",          "str"),
]


# ---------------------------------------------------------------------------
# Archivos a cargar por scraper
# ---------------------------------------------------------------------------

SCRAPERS = [
    {
        "name":    "indiamart",
        "table":   "SRC_INDIAMART_PROV_HIST",
        "files":   [
            REPO_ROOT / "bd_scrapers/indiamart/results/j_mocayt2k6lpm93mtj.json",
        ],
        "mapper":  map_indiamart,
        "cols":    INDIAMART_COLS,
    },
    {
        "name":    "made-in-china",
        "table":   "SRC_MADEINCHINA_PROV_HIST",
        "files":   [
            REPO_ROOT / "bd_scrapers/made-in-china/results/03-made_in_china_20260429_213259.json",
            REPO_ROOT / "bd_scrapers/made-in-china/results/j_mo8omwb11xys1f1359.json",
        ],
        "mapper":  map_made_in_china,
        "cols":    MADE_IN_CHINA_COLS,
    },
    {
        "name":    "cosme-ranking",
        "table":   "SRC_COSME_RANKING_HIST",
        "files":   [
            REPO_ROOT / "bd_scrapers/cosme-ranking-products/results/cosme_ranking_products_20260428_152532.json",
            REPO_ROOT / "bd_scrapers/cosme-ranking-products/results/j_moi6iped88egk7mwf.json",
        ],
        "mapper":  map_cosme,
        "cols":    COSME_COLS,
    },
    {
        "name":    "cosmetics-design",
        "table":   "SRC_COSMETICDESIGN_ART_HIST",
        "files":   [
            REPO_ROOT / "bd_scrapers/cosmetics-design/results/cosmetics_design_20260425_014114.json",
            REPO_ROOT / "bd_scrapers/cosmetics-design/results/j_mocx43622cgfa4j15n.json",
        ],
        "mapper":  map_cosmetics_design,
        "cols":    COSMETICS_DESIGN_COLS,
    },
    {
        "name":    "olive-young",
        "table":   "SRC_OLIVEYOUNG_RANK_HIST",
        "files":   [
            REPO_ROOT / "bd_scrapers/olive-young/results/j_mocl5j9j2ai7fdut4w.json",
            REPO_ROOT / "bd_scrapers/olive-young/results/j_moclf6ac278t2h3bpn.json",
            REPO_ROOT / "bd_scrapers/olive-young/results/j_mocm38z62orfikp3nx.json",
        ],
        "mapper":  map_olive_young,
        "cols":    OLIVE_YOUNG_COLS,
    },
]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="No ejecutar INSERT, solo mostrar plan")
    args = parser.parse_args()

    conn = snowflake.connector.connect(
        user=os.getenv("SNOWFLAKE_USER"),
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
        role="SYSADMIN",
        database="PRD_STG",
        schema="GNM",
    )
    cur = conn.cursor()

    sep = "=" * 68
    print(sep)
    print(f"CARGA EMERGENCIA — PRD_STG.GNM  {'[DRY-RUN]' if args.dry_run else ''}")
    print(sep)

    grand_total = 0
    results = []

    for cfg in SCRAPERS:
        name  = cfg["name"]
        table = cfg["table"]
        print(f"\n[{name}] → {table}")

        all_rows: list[dict] = []
        for fpath in cfg["files"]:
            fpath = Path(fpath)
            if not fpath.exists():
                print(f"  SKIP {fpath.name} — no encontrado")
                continue
            rows = load_json(str(fpath))
            mapped = cfg["mapper"](rows)
            all_rows.extend(mapped)
            print(f"  {fpath.name}: {len(mapped)} filas leídas")

        if not all_rows:
            print(f"  Sin filas para insertar.")
            continue

        try:
            n = insert_rows(cur, table, cfg["cols"], all_rows, dry_run=args.dry_run)
            print(f"  {'[DRY] ' if args.dry_run else ''}INSERT OK: {n} filas → {table}")
            grand_total += n
            results.append((name, table, n, "OK"))
        except Exception as e:
            print(f"  ERROR: {e}")
            results.append((name, table, 0, f"ERR: {e}"))

    print(f"\n{sep}")
    print(f"RESUMEN:")
    for name, table, n, status in results:
        print(f"  {status:4s}  {name:<20} {n:>5} filas → {table}")
    print(f"  TOTAL: {grand_total} filas")
    print(sep)

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
