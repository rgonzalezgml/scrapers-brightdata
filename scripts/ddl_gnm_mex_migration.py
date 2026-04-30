"""
ddl_gnm_mex_migration.py — Crea 5 tablas SRC_* en PRD_STG.GNM.

Tablas objetivo (CREATE OR REPLACE):
  1. PRD_STG.GNM.SRC_ALIBABA_PROV_HIST
  2. PRD_STG.GNM.SRC_INDIAMART_PROV_HIST
  3. PRD_STG.GNM.SRC_MADEINCHINA_PROV_HIST
  4. PRD_STG.GNM.SRC_COSMETICDESIGN_ART_HIST
  5. PRD_STG.GNM.SRC_COSME_RANKING_HIST

NO toca: PRD_STG.GNM.SRC_OLIVEYOUNG_RANK_HIST (ya existe, creada por otro usuario)

Credenciales: .agents/skills/gli-snowflake-connect/reference/.env
Usuario/Rol  : SERVICIO_GENOMMA_01 / SYSADMIN
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    print("ERROR: pip install python-dotenv --break-system-packages")
    sys.exit(1)

try:
    import snowflake.connector
except ImportError:
    print("ERROR: pip install snowflake-connector-python --break-system-packages")
    sys.exit(1)

_REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = _REPO_ROOT / ".agents" / "skills" / "gli-snowflake-connect" / "reference" / ".env"

# ---------------------------------------------------------------------------
# DDL statements — schema PRD_STG.GNM, exactamente como los aprobó el usuario
# ---------------------------------------------------------------------------
STATEMENTS = [
    (
        "SRC_ALIBABA_PROV_HIST",
        """CREATE OR REPLACE TABLE PRD_STG.GNM.SRC_ALIBABA_PROV_HIST (
    URL_PRODUCTO             VARCHAR(16777216)  COMMENT 'URL del producto en alibaba.com',
    NM_PRODUCTO              VARCHAR(16777216)  COMMENT 'Nombre del producto normalizado (cleaned_product_name)',
    NM_PROVEEDOR             VARCHAR(16777216)  COMMENT 'Nombre del proveedor tal como aparece en el listing',
    TX_PRECIO_RAW            VARCHAR(16777216)  COMMENT 'Precio tal como aparece en la pagina, sin procesar',
    NU_PRECIO_MIN_USD        NUMBER(18,4)       COMMENT 'Precio minimo en dolares USD (extremo inferior del rango)',
    NU_PRECIO_MAX_USD        NUMBER(18,4)       COMMENT 'Precio maximo en dolares USD (extremo superior del rango)',
    TX_UNIDAD_PRECIO         VARCHAR(16777216)  COMMENT 'Unidad de medida del precio (e.g. "per kilogram")',
    TX_MOQ                   VARCHAR(16777216)  COMMENT 'Cantidad minima de pedido en texto libre (minimum_order_quantity)',
    TX_CAS                   VARCHAR(16777216)  COMMENT 'Numero CAS del compuesto quimico',
    TX_PUREZA                VARCHAR(16777216)  COMMENT 'Pureza del compuesto (e.g. "40%")',
    NU_STATUS_CODE           NUMBER(5,0)        COMMENT 'Codigo HTTP de respuesta del scraper',
    FT_FUENTE                VARCHAR(200)       DEFAULT 'alibaba'             COMMENT 'Identificador del scraper que origino la fila',
    CREATED_AT  TIMESTAMP_NTZ(9) DEFAULT CURRENT_TIMESTAMP() COMMENT 'Fecha y hora de creacion del registro',
    UPDATED_AT  TIMESTAMP_NTZ(9) DEFAULT CURRENT_TIMESTAMP() COMMENT 'Fecha y hora de ultima actualizacion del registro',
    CREATED_USR VARCHAR(100)     DEFAULT CURRENT_USER()      COMMENT 'Usuario que creo el registro',
    UPDATED_USR VARCHAR(100)     DEFAULT CURRENT_USER()      COMMENT 'Usuario que realizo la ultima actualizacion del registro'
)
COMMENT = 'Historico de productos de proveedores quimicos scrapeados de alibaba.com. Fuente: scraper alibaba (BrightData). Granularidad: 1 fila = 1 producto listado. Tabla append-only (cada carga inserta, no sobreescribe).'""",
    ),
    (
        "SRC_INDIAMART_PROV_HIST",
        """CREATE OR REPLACE TABLE PRD_STG.GNM.SRC_INDIAMART_PROV_HIST (
    ID_PRODUCTO              VARCHAR(16777216)  COMMENT 'Identificador unico del producto en indiamart.com',
    URL_PRODUCTO             VARCHAR(16777216)  COMMENT 'URL del producto en indiamart.com',
    NM_PRODUCTO_ORIGINAL     VARCHAR(16777216)  COMMENT 'Nombre del producto tal como aparece en la fuente, sin normalizar',
    NM_PRODUCTO_CLEAN        VARCHAR(16777216)  COMMENT 'Nombre del producto normalizado por el scraper',
    TX_DESCRIPCION           VARCHAR(16777216)  COMMENT 'Descripcion del producto en texto libre',
    TX_TIPO                  VARCHAR(16777216)  COMMENT 'Tipo de producto (e.g. "other")',
    TX_CATEGORIA_MIC         VARCHAR(16777216)  COMMENT 'Categoria del producto segun la hoja MIC del catalogo interno',
    DS_CATEGORIA_PATH        VARIANT            COMMENT 'Jerarquia de categorias como array de strings',
    DS_PRECIO_MIN_USD        VARIANT            COMMENT 'Objeto JSON con precio minimo: {value, currency, symbol}',
    DS_PRECIO_MAX_USD        VARIANT            COMMENT 'Objeto JSON con precio maximo: {value, currency, symbol}',
    TX_PRECIO_RAW            VARCHAR(16777216)  COMMENT 'Precio tal como aparece en la pagina, sin procesar',
    TX_PRECIO_VALOR_RAW      VARCHAR(16777216)  COMMENT 'Valor numerico del precio en texto (price_value_raw)',
    TX_UNIDAD_PRECIO         VARCHAR(16777216)  COMMENT 'Unidad de medida del precio',
    TX_MONEDA                VARCHAR(16777216)  COMMENT 'Codigo de moneda del precio (e.g. "INR", "USD")',
    TX_DISPONIBILIDAD        VARCHAR(16777216)  COMMENT 'Disponibilidad del producto (availability)',
    ID_PROVEEDOR             VARCHAR(16777216)  COMMENT 'Identificador unico del proveedor en indiamart.com',
    NM_PROVEEDOR             VARCHAR(16777216)  COMMENT 'Nombre del proveedor',
    URL_PROVEEDOR            VARCHAR(16777216)  COMMENT 'URL del perfil del proveedor en indiamart.com',
    TX_CIUDAD_PROVEEDOR      VARCHAR(16777216)  COMMENT 'Ciudad donde se ubica el proveedor',
    TX_PAIS_PROVEEDOR        VARCHAR(16777216)  COMMENT 'Pais del proveedor en codigo ISO-2 (e.g. "IN", "CN")',
    FL_VERIFICADO            BOOLEAN            COMMENT 'Indica si el proveedor fue verificado por indiamart',
    FL_TRUSTSEAL             BOOLEAN            COMMENT 'Indica si el proveedor tiene sello de confianza TrustSeal',
    NU_ANIO_MIEMBRO          NUMBER(4,0)        COMMENT 'Anio desde el que el proveedor es miembro de indiamart (member_since_year)',
    URL_IMAGEN               VARCHAR(16777216)  COMMENT 'URL de la imagen principal del producto',
    TX_SITIO                 VARCHAR(50)        DEFAULT 'indiamart'  COMMENT 'Identificador del sitio fuente del scraper',
    DS_FLAGS                 VARIANT            COMMENT 'Flags internos del scraper (array)',
    DT_SCRAPING              DATE               COMMENT 'Fecha en que se realizo el scraping del producto',
    FT_FUENTE                VARCHAR(200)       DEFAULT 'indiamart'           COMMENT 'Identificador del scraper que origino la fila',
    CREATED_AT  TIMESTAMP_NTZ(9) DEFAULT CURRENT_TIMESTAMP() COMMENT 'Fecha y hora de creacion del registro',
    UPDATED_AT  TIMESTAMP_NTZ(9) DEFAULT CURRENT_TIMESTAMP() COMMENT 'Fecha y hora de ultima actualizacion del registro',
    CREATED_USR VARCHAR(100)     DEFAULT CURRENT_USER()      COMMENT 'Usuario que creo el registro',
    UPDATED_USR VARCHAR(100)     DEFAULT CURRENT_USER()      COMMENT 'Usuario que realizo la ultima actualizacion del registro'
)
COMMENT = 'Historico de productos y proveedores scrapeados de indiamart.com. Fuente: scraper indiamart (BrightData). Granularidad: 1 fila = 1 producto/proveedor listado. Tabla append-only (cada carga inserta, no sobreescribe).'""",
    ),
    (
        "SRC_MADEINCHINA_PROV_HIST",
        """CREATE OR REPLACE TABLE PRD_STG.GNM.SRC_MADEINCHINA_PROV_HIST (
    ID_PRODUCTO              VARCHAR(16777216)  COMMENT 'Identificador unico del producto en made-in-china.com (product_id)',
    TX_SKU                   VARCHAR(16777216)  COMMENT 'SKU del producto; coincide con product_id en la version v8 del scraper',
    URL_PRODUCTO             VARCHAR(16777216)  COMMENT 'URL del producto en made-in-china.com',
    NM_PRODUCTO_ORIGINAL     VARCHAR(16777216)  COMMENT 'Nombre del producto tal como aparece en la fuente, sin normalizar',
    NM_PRODUCTO_CLEAN        VARCHAR(16777216)  COMMENT 'Nombre del producto normalizado por el scraper',
    TX_TIPO                  VARCHAR(16777216)  COMMENT 'Tipo de producto (e.g. "chemical")',
    TX_CATEGORIA_MIC         VARCHAR(16777216)  COMMENT 'Categoria del producto segun la hoja MIC del catalogo interno',
    DS_CATEGORIA_PATH        VARIANT            COMMENT 'Jerarquia de categorias como array de strings',
    DS_PRECIO_MIN_USD        VARIANT            COMMENT 'Objeto JSON con precio minimo: {value, currency, symbol}',
    DS_PRECIO_MAX_USD        VARIANT            COMMENT 'Objeto JSON con precio maximo: {value, currency, symbol}',
    TX_PRECIO_RAW            VARCHAR(16777216)  COMMENT 'Precio tal como aparece en la pagina, sin procesar',
    TX_MONEDA                VARCHAR(16777216)  COMMENT 'Codigo de moneda del precio',
    NU_MOQ_CANTIDAD          NUMBER(18,3)       COMMENT 'Cantidad minima de pedido en valor numerico',
    TX_MOQ_UNIDAD            VARCHAR(16777216)  COMMENT 'Unidad de medida de la cantidad minima de pedido',
    TX_CAS                   VARCHAR(16777216)  COMMENT 'Numero CAS del compuesto quimico (cas_no)',
    TX_FORMULA               VARCHAR(16777216)  COMMENT 'Formula quimica del compuesto',
    TX_EINECS                VARCHAR(16777216)  COMMENT 'Numero EINECS del compuesto (registro europeo de sustancias quimicas)',
    TX_GRADO                 VARCHAR(16777216)  COMMENT 'Grado de calidad del compuesto (e.g. "Superior Grade")',
    TX_APARIENCIA            VARCHAR(16777216)  COMMENT 'Apariencia fisica del compuesto (e.g. "Solid")',
    ID_PROVEEDOR             VARCHAR(16777216)  COMMENT 'Identificador unico del proveedor en made-in-china.com',
    NM_PROVEEDOR_RAW         VARCHAR(16777216)  COMMENT 'Nombre del proveedor tal como aparece en la fuente (supplier_name_raw)',
    URL_IMAGEN               VARCHAR(16777216)  COMMENT 'URL de la imagen principal del producto',
    TX_SITIO                 VARCHAR(50)        DEFAULT 'made-in-china'  COMMENT 'Identificador del sitio fuente del scraper',
    DS_FLAGS                 VARIANT            COMMENT 'Flags internos del scraper (array)',
    DT_SCRAPING              DATE               COMMENT 'Fecha en que se realizo el scraping del producto',
    FT_FUENTE                VARCHAR(200)       DEFAULT 'made_in_china'       COMMENT 'Identificador del scraper que origino la fila',
    CREATED_AT  TIMESTAMP_NTZ(9) DEFAULT CURRENT_TIMESTAMP() COMMENT 'Fecha y hora de creacion del registro',
    UPDATED_AT  TIMESTAMP_NTZ(9) DEFAULT CURRENT_TIMESTAMP() COMMENT 'Fecha y hora de ultima actualizacion del registro',
    CREATED_USR VARCHAR(100)     DEFAULT CURRENT_USER()      COMMENT 'Usuario que creo el registro',
    UPDATED_USR VARCHAR(100)     DEFAULT CURRENT_USER()      COMMENT 'Usuario que realizo la ultima actualizacion del registro'
)
COMMENT = 'Historico de productos de proveedores quimicos scrapeados de made-in-china.com. Fuente: scraper made_in_china (BrightData). Granularidad: 1 fila = 1 producto de proveedor chino. Tabla append-only (cada carga inserta, no sobreescribe).'""",
    ),
    (
        "SRC_COSMETICDESIGN_ART_HIST",
        """CREATE OR REPLACE TABLE PRD_STG.GNM.SRC_COSMETICDESIGN_ART_HIST (
    TX_TITULO                VARCHAR(16777216)  COMMENT 'Titulo del articulo tal como aparece en la publicacion (article_title)',
    URL_ARTICULO             VARCHAR(16777216)  COMMENT 'URL canonica del articulo en cosmeticdesign.com (article_url)',
    DT_PUBLICACION           TIMESTAMP_NTZ      COMMENT 'Fecha y hora de publicacion del articulo en UTC, formato ISO-8601 (publication_date)',
    TX_RESUMEN               VARCHAR(16777216)  COMMENT 'Resumen o bajada del articulo (article_summary)',
    TX_CONTENIDO             VARCHAR(16777216)  COMMENT 'Contenido completo del articulo; vacio si el articulo esta bloqueado por paywall (article_content)',
    FL_PAYWALL               BOOLEAN            COMMENT 'Indica si el articulo requiere suscripcion de pago para acceder al contenido completo (paywalled)',
    URL_IMAGEN               VARCHAR(16777216)  COMMENT 'URL de la imagen principal (lead) del articulo (lead_image_url)',
    TX_PIE_IMAGEN            VARCHAR(16777216)  COMMENT 'Pie de foto o leyenda de la imagen principal (image_caption)',
    DS_TEMAS                 VARIANT            COMMENT 'Temas y etiquetas editoriales del articulo como array de strings (related_topics)',
    FT_FUENTE                VARCHAR(200)       DEFAULT 'cosmetics_design'    COMMENT 'Identificador del scraper que origino la fila',
    CREATED_AT  TIMESTAMP_NTZ(9) DEFAULT CURRENT_TIMESTAMP() COMMENT 'Fecha y hora de creacion del registro',
    UPDATED_AT  TIMESTAMP_NTZ(9) DEFAULT CURRENT_TIMESTAMP() COMMENT 'Fecha y hora de ultima actualizacion del registro',
    CREATED_USR VARCHAR(100)     DEFAULT CURRENT_USER()      COMMENT 'Usuario que creo el registro',
    UPDATED_USR VARCHAR(100)     DEFAULT CURRENT_USER()      COMMENT 'Usuario que realizo la ultima actualizacion del registro'
)
COMMENT = 'Historico de articulos de beauty & wellness scrapeados de cosmeticdesign.com (nutraingredients.com). Fuente: scraper cosmetics_design (BrightData). Granularidad: 1 fila = 1 articulo de la revista. Aprox. 40% de filas tendran TX_CONTENIDO vacio por paywall. Tabla append-only (cada carga inserta, no sobreescribe).'""",
    ),
    (
        "SRC_COSME_RANKING_HIST",
        """CREATE OR REPLACE TABLE PRD_STG.GNM.SRC_COSME_RANKING_HIST (
    NU_RANK                  NUMBER(3,0)        COMMENT 'Posicion del producto en el ranking de la categoria scrapeada',
    TX_RANK_CAMBIO           VARCHAR(16777216)  COMMENT 'Variacion de posicion respecto al periodo anterior: "hot", "up", "down", "new", "same" (rank_change)',
    ID_PRODUCTO              VARCHAR(16777216)  COMMENT 'Identificador unico del producto en cosme.net',
    NM_PRODUCTO              VARCHAR(16777216)  COMMENT 'Nombre del producto en ingles o romanizado',
    NM_PRODUCTO_JP           VARCHAR(16777216)  COMMENT 'Nombre original del producto en japones (product_name_jp)',
    URL_PRODUCTO             VARCHAR(16777216)  COMMENT 'URL del producto en cosme.net (cosme.net/products/{id}/)',
    URL_IMG_PRINCIPAL        VARCHAR(16777216)  COMMENT 'URL del thumbnail del producto en el listing del ranking (product_img)',
    ID_MARCA                 VARCHAR(16777216)  COMMENT 'Identificador unico de la marca en cosme.net',
    NM_MARCA                 VARCHAR(16777216)  COMMENT 'Nombre de la marca en ingles o romanizado',
    NM_MARCA_JP              VARCHAR(16777216)  COMMENT 'Nombre de la marca en japones (brand_name_jp)',
    URL_MARCA                VARCHAR(16777216)  COMMENT 'URL del perfil de la marca en cosme.net',
    NM_FABRICANTE            VARCHAR(16777216)  COMMENT 'Nombre del fabricante del producto (メーカー)',
    URL_FABRICANTE           VARCHAR(16777216)  COMMENT 'URL del perfil del fabricante en cosme.net (manufacturer_url)',
    NM_CATEGORIA             VARCHAR(16777216)  COMMENT 'Nombre de la categoria del ranking scrapeada en Stage 1',
    URL_CATEGORIA            VARCHAR(16777216)  COMMENT 'URL de la pagina de la categoria en cosme.net',
    TX_CATEGORIA_FULL        VARCHAR(16777216)  COMMENT 'Jerarquia completa de la categoria en texto (e.g. "A > B > C") (category_full)',
    DS_CATEGORIA_PATH        VARIANT            COMMENT 'Jerarquia de categorias como array de objetos [{name, url}] (category_path)',
    TX_PRECIO_RAW            VARCHAR(16777216)  COMMENT 'Texto completo del precio incluyendo volumen y precio (price_text)',
    NU_PRECIO_YEN            NUMBER(18,4)       COMMENT 'Precio numerico extraido del texto, expresado en yenes japoneses',
    TX_TALLA                 VARCHAR(16777216)  COMMENT 'Volumen o tamano del producto (e.g. "30mL") (size)',
    FL_PRECIO_ABIERTO        BOOLEAN            COMMENT 'Indica si el precio es abierto (el fabricante no fija precio de venta) (is_open_price)',
    FL_INCLUYE_IVA           BOOLEAN            COMMENT 'Indica si el precio mostrado incluye impuesto (tax_included)',
    NU_RATING                NUMBER(5,2)        COMMENT 'Calificacion promedio del producto en Stage 1 del scraper (escala 0.0 a 7.0)',
    NU_RATING_DETAIL         NUMBER(5,2)        COMMENT 'Calificacion promedio detallada del producto obtenida en Stage 2 (p.average)',
    NU_PUNTOS                NUMBER(5,2)        COMMENT 'Puntaje del producto en el ranking de cosme.net (p.point, e.g. 59.1)',
    NU_RANK_CATEGORIA        NUMBER(5,0)        COMMENT 'Posicion del producto dentro de su propia categoria (cat_rank)',
    NM_CATEGORIA_RANK        VARCHAR(16777216)  COMMENT 'Nombre de la categoria en la que el producto tiene posicion de ranking (cat_rank_name)',
    DS_RANKING_EN            VARIANT            COMMENT 'Lista de rankings en los que aparece el producto como array de strings (ranking_in)',
    NU_RESENAS               NUMBER(12,0)       COMMENT 'Cantidad de resenas de usuarias para el producto (review_count)',
    NU_FOTOS                 NUMBER(12,0)       COMMENT 'Cantidad de fotos de usuarias asociadas al producto (photo_count)',
    NU_QA                    NUMBER(12,0)       COMMENT 'Cantidad de preguntas y respuestas de la comunidad (qa_count)',
    NU_LIKES                 NUMBER(12,0)       COMMENT 'Cantidad de likes del producto en la comunidad',
    NU_HAVES                 NUMBER(12,0)       COMMENT 'Cantidad de usuarias que marcaron el producto como que lo tienen (haves)',
    TX_FECHA_LANZAMIENTO     VARCHAR(16777216)  COMMENT 'Fecha de lanzamiento en texto japones tal como aparece en la pagina (release_date)',
    FL_BEST_COSME            BOOLEAN            COMMENT 'Indica si el producto tiene el badge de Best Cosme (is_best_cosme)',
    FL_NUEVO                 BOOLEAN            COMMENT 'Indica si el producto tiene el badge de nuevo lanzamiento (is_new)',
    TX_DESCRIPCION           VARCHAR(16777216)  COMMENT 'Descripcion del producto obtenida en Stage 2 (商品説明)',
    TX_MODO_USO              VARCHAR(16777216)  COMMENT 'Instrucciones de uso del producto (使い方) (how_to_use)',
    TX_INGREDIENTES          VARCHAR(16777216)  COMMENT 'Lista completa de ingredientes del producto (全成分) (ingredients)',
    TX_CLASIFICACION         VARCHAR(16777216)  COMMENT 'Clasificacion regulatoria del producto (e.g. "医薬部外品") (classification)',
    TX_JAN_CODE              VARCHAR(16777216)  COMMENT 'Codigo JAN (codigo de barras japones) del producto (jan_code)',
    URL_OFICIAL              VARCHAR(16777216)  COMMENT 'URL del sitio oficial del producto o fabricante (公式サイト) (official_url)',
    DS_IMAGENES              VARIANT            COMMENT 'Array con todas las URLs de imagenes del producto (all_images)',
    URL_TIENDA               VARCHAR(16777216)  COMMENT 'URL de redireccion a tienda de compra en cosme.com (shop_url)',
    DS_TIENDAS               VARIANT            COMMENT 'Lista de nombres de tiendas fisicas donde se vende el producto como array (stores)',
    DS_PRODUCTOS_RELACIONADOS VARIANT           COMMENT 'Productos relacionados sugeridos por cosme.net como array de objetos [{name, url}] (related_products)',
    DT_PERIODO_INICIO        DATE               COMMENT 'Fecha de inicio del periodo de agregacion del ranking (period_start)',
    DT_PERIODO_FIN           DATE               COMMENT 'Fecha de fin del periodo de agregacion del ranking (period_end)',
    NU_TOTAL_RANKING         NUMBER(6,0)        COMMENT 'Cantidad total de productos en el ranking en el momento del scraping (total_products)',
    DT_SCRAPING              TIMESTAMP_NTZ      COMMENT 'Fecha y hora en que se realizo el scraping, formato ISO 8601 (scraped_at)',
    TX_SOURCE                VARCHAR(100)       COMMENT 'Identificador de la fuente dentro del sitio (e.g. "cosme.net/ranking/products") (source)',
    TX_PAIS                  VARCHAR(10)        COMMENT 'Codigo de pais ISO-2 del sitio scrapeado (e.g. "JP") (country)',
    TX_RANKING_POR           VARCHAR(20)        COMMENT 'Criterio de agrupacion del ranking (e.g. "product") (ranking_by)',
    FT_FUENTE                VARCHAR(200)       DEFAULT 'cosme_ranking_products'   COMMENT 'Identificador del scraper que origino la fila',
    CREATED_AT  TIMESTAMP_NTZ(9) DEFAULT CURRENT_TIMESTAMP() COMMENT 'Fecha y hora de creacion del registro',
    UPDATED_AT  TIMESTAMP_NTZ(9) DEFAULT CURRENT_TIMESTAMP() COMMENT 'Fecha y hora de ultima actualizacion del registro',
    CREATED_USR VARCHAR(100)     DEFAULT CURRENT_USER()      COMMENT 'Usuario que creo el registro',
    UPDATED_USR VARCHAR(100)     DEFAULT CURRENT_USER()      COMMENT 'Usuario que realizo la ultima actualizacion del registro'
)
COMMENT = 'Historico del ranking semanal de productos scrapeado de cosme.net. Fuente: scraper cosme_ranking_products (BrightData). Granularidad: 1 fila = 1 producto en el ranking semanal; incluye detalle de Stage 2 (descripcion, ingredientes, imagenes). El periodo cubierto se identifica por DT_PERIODO_INICIO + DT_PERIODO_FIN. Tabla append-only (cada carga inserta, no sobreescribe).'""",
    ),
]


def main() -> None:
    load_dotenv(ENV_PATH)

    conn = snowflake.connector.connect(
        user=os.getenv("SNOWFLAKE_USER"),
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
        role=os.getenv("SNOWFLAKE_ROLE"),
    )

    sep = "=" * 64
    print(sep)
    print("DDL EXECUTION — PRD_STG.GNM (5 tablas SRC_*)")
    print(f"Usuario  : {os.getenv('SNOWFLAKE_USER')}")
    print(f"Rol      : {os.getenv('SNOWFLAKE_ROLE')}")
    print(f"Warehouse: {os.getenv('SNOWFLAKE_WAREHOUSE')}")
    print(sep)

    results: list[tuple[str, str, str]] = []

    try:
        cur = conn.cursor()
        cur.execute("USE DATABASE PRD_STG")
        cur.execute("USE SCHEMA GNM")

        for table_name, sql in STATEMENTS:
            t0 = time.time()
            try:
                cur.execute(sql)
                elapsed = time.time() - t0
                results.append((table_name, "OK", f"{elapsed:.1f}s"))
                print(f"[OK]  CREATE  PRD_STG.GNM.{table_name}  ({elapsed:.1f}s)")
            except snowflake.connector.errors.ProgrammingError as exc:
                elapsed = time.time() - t0
                err = str(exc)
                results.append((table_name, "ERR", err))
                print(f"[ERR] CREATE  PRD_STG.GNM.{table_name}")
                print(f"      ERROR SNOWFLAKE: {err}")
                print("      Deteniendo por fallo de permisos.")
                break

    finally:
        conn.close()

    print(sep)
    ok = sum(1 for _, s, _ in results if s == "OK")
    err = sum(1 for _, s, _ in results if s == "ERR")
    print(f"Resumen: {ok} OK, {err} ERR")
    print(sep)


if __name__ == "__main__":
    main()
