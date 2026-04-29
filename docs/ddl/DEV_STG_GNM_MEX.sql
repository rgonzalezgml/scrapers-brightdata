-- =============================================================================
-- Schema:  DEV_STG.GNM_MEX
-- Norma:   GLI Nomenclatura v1.1.0 (MAYUSCULAS, sin acentos, prefijos de dominio)
-- Fuente:  scrapers BrightData → middlewares Python → agentes GeommaAI
-- Prefijo: MKT  (inteligencia de mercado / I+D / precios de proveedores)
-- Sufijo:  _HIST (tabla histórica; cada carga inserta, no sobreescribe)
--
-- Columnas de auditoría comunes a todas las tablas:
--   DT_CARGA   TIMESTAMP_NTZ  — momento de la carga al DWH
--   FT_FUENTE  VARCHAR(200)   — identificador del scraper que originó la fila
--   ID_JOB     VARCHAR(100)   — job / run_id del pipeline ETL
--
-- Convenciones de tipo:
--   VARIANT  → arrays JSON o objetos anidados  (Snowflake semi-structured)
--   TEXT     → VARCHAR sin límite fijo (Snowflake lo trata igual)
--   FLOAT    → precio o rating numérico de punto flotante
--   NUMBER   → entero o decimal sin punto flotante
--   BOOLEAN  → flag scraper (verified, out_of_stock, etc.)
--   DATE     → fecha sin hora (scraped_date, launch_date)
-- =============================================================================


-- ---------------------------------------------------------------------------
-- 1. MKT_ALIBABA_PROV_HIST
--    Fuente: scrapers/alibaba  (alibaba.com, búsqueda de químicos industriales)
--    Granularidad: 1 fila = 1 producto listado en alibaba
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS DEV_STG.GNM_MEX.SRC_ALIBABA_PROV_HIST (
    -- identificación
    URL_PRODUCTO             TEXT,
    NM_PRODUCTO              TEXT,          -- cleaned_product_name

    -- proveedor
    NM_PROVEEDOR             TEXT,

    -- precio
    TX_PRECIO_RAW            TEXT,          -- precio tal como aparece en la página
    NU_PRECIO_MIN_USD        FLOAT,         -- precio mínimo en USD (float plano)
    NU_PRECIO_MAX_USD        FLOAT,
    TX_UNIDAD_PRECIO         TEXT,          -- price_unit (e.g. "per kilogram")

    -- producto
    TX_MOQ                   TEXT,          -- minimum_order_quantity (texto libre)
    TX_CAS                   TEXT,          -- número CAS del compuesto
    TX_PUREZA                TEXT,          -- purity (e.g. "40%")

    -- metadatos de la petición
    NU_STATUS_CODE           NUMBER(5,0),
    DS_INPUT                 VARIANT,       -- seed JSON enviado al scraper

    -- auditoría
    DT_CARGA                 TIMESTAMP_NTZ  DEFAULT CURRENT_TIMESTAMP,
    FT_FUENTE                VARCHAR(200)   DEFAULT 'alibaba',
    ID_JOB                   VARCHAR(100)
);


-- ---------------------------------------------------------------------------
-- 2. MKT_INDIAMART_PROV_HIST
--    Fuente: scrapers/indiamart  (indiamart.com, directorios de proveedores)
--    Granularidad: 1 fila = 1 producto / proveedor listado
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS DEV_STG.GNM_MEX.SRC_INDIAMART_PROV_HIST (
    -- identificación
    ID_PRODUCTO              TEXT,
    URL_PRODUCTO             TEXT,
    NM_PRODUCTO_ORIGINAL     TEXT,
    NM_PRODUCTO_CLEAN        TEXT,
    TX_DESCRIPCION           TEXT,
    TX_TIPO                  TEXT,          -- type (e.g. "other")

    -- categoría
    TX_CATEGORIA_MIC         TEXT,          -- category_mic (hoja de MIC)
    DS_CATEGORIA_PATH        VARIANT,       -- array de strings con la jerarquía

    -- precio  (objeto {value, currency, symbol} en raw)
    DS_PRECIO_MIN_USD        VARIANT,
    DS_PRECIO_MAX_USD        VARIANT,
    TX_PRECIO_RAW            TEXT,
    TX_PRECIO_VALOR_RAW      TEXT,          -- price_value_raw
    TX_UNIDAD_PRECIO         TEXT,
    TX_MONEDA                TEXT,          -- price_currency (código INR / USD…)
    TX_DISPONIBILIDAD        TEXT,          -- availability

    -- proveedor
    ID_PROVEEDOR             TEXT,
    NM_PROVEEDOR             TEXT,
    URL_PROVEEDOR            TEXT,
    TX_CIUDAD_PROVEEDOR      TEXT,
    TX_PAIS_PROVEEDOR        TEXT,          -- ISO-2 (IN, CN…)
    FL_VERIFICADO            BOOLEAN,
    FL_TRUSTSEAL             BOOLEAN,
    NU_ANIO_MIEMBRO          NUMBER(4,0),   -- member_since_year

    -- imagen
    URL_IMAGEN               TEXT,

    -- metadatos del scraper
    TX_SITIO                 VARCHAR(50)    DEFAULT 'indiamart',
    DS_FLAGS                 VARIANT,       -- scraper_flags (array)
    DT_SCRAPING              DATE,
    DS_INPUT                 VARIANT,

    -- auditoría
    DT_CARGA                 TIMESTAMP_NTZ  DEFAULT CURRENT_TIMESTAMP,
    FT_FUENTE                VARCHAR(200)   DEFAULT 'indiamart',
    ID_JOB                   VARCHAR(100)
);


-- ---------------------------------------------------------------------------
-- 3. MKT_MADEINCHINA_PROV_HIST
--    Fuente: scrapers/made_in_china  (made-in-china.com, catálogos de químicos)
--    Granularidad: 1 fila = 1 producto de proveedor chino
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS DEV_STG.GNM_MEX.SRC_MADEINCHINA_PROV_HIST (
    -- identificación
    ID_PRODUCTO              TEXT,          -- product_id
    TX_SKU                   TEXT,          -- sku (coincide con product_id en v8)
    URL_PRODUCTO             TEXT,
    NM_PRODUCTO_ORIGINAL     TEXT,
    NM_PRODUCTO_CLEAN        TEXT,
    TX_TIPO                  TEXT,          -- type (e.g. "chemical")

    -- categoría
    TX_CATEGORIA_MIC         TEXT,
    DS_CATEGORIA_PATH        VARIANT,       -- array jerarquía

    -- precio  (objeto {value, currency, symbol} en raw)
    DS_PRECIO_MIN_USD        VARIANT,
    DS_PRECIO_MAX_USD        VARIANT,
    TX_PRECIO_RAW            TEXT,
    TX_MONEDA                TEXT,

    -- MOQ
    NU_MOQ_CANTIDAD          NUMBER(18,3),
    TX_MOQ_UNIDAD            TEXT,

    -- especificaciones químicas
    TX_CAS                   TEXT,          -- cas_no
    TX_FORMULA               TEXT,
    TX_EINECS                TEXT,
    TX_GRADO                 TEXT,          -- grade (e.g. "Superior Grade")
    TX_APARIENCIA            TEXT,          -- appearance (e.g. "Solid")

    -- proveedor
    ID_PROVEEDOR             TEXT,
    NM_PROVEEDOR_RAW         TEXT,          -- supplier_name_raw

    -- imagen
    URL_IMAGEN               TEXT,

    -- metadatos del scraper
    TX_SITIO                 VARCHAR(50)    DEFAULT 'made-in-china',
    DS_FLAGS                 VARIANT,       -- scraper_flags
    DT_SCRAPING              DATE,
    DS_INPUT                 VARIANT,

    -- auditoría
    DT_CARGA                 TIMESTAMP_NTZ  DEFAULT CURRENT_TIMESTAMP,
    FT_FUENTE                VARCHAR(200)   DEFAULT 'made_in_china',
    ID_JOB                   VARCHAR(100)
);


-- ---------------------------------------------------------------------------
-- 4. MKT_OLIVEYOUNG_RANK_HIST
--    Fuente: scrapers/olive_young  (global.oliveyoung.com, best-seller ranking)
--    Granularidad: 1 fila = 1 producto en el ranking de best-sellers
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS DEV_STG.GNM_MEX.SRC_OLIVEYOUNG_RANK_HIST (
    -- ranking
    NU_RANK                  NUMBER(5,0),
    ID_PRODUCTO              TEXT,          -- prdtNo (SKU de OliveYoung)

    -- producto
    NM_MARCA                 TEXT,          -- brand
    NM_PRODUCTO              TEXT,          -- name (EN)
    NM_PRODUCTO_KR           TEXT,          -- name_kr (KR)

    -- precio (texto con símbolo de moneda, e.g. "US$27.00")
    TX_PRECIO_ORIGINAL       TEXT,
    TX_PRECIO_OFERTA         TEXT,

    -- métricas
    NU_RATING                FLOAT,
    FL_SIN_STOCK             BOOLEAN,       -- out_of_stock

    -- imagen
    URL_IMAGEN               TEXT,

    -- metadatos del scraper
    DS_INPUT                 VARIANT,       -- seed enviado (url + region)

    -- auditoría
    DT_CARGA                 TIMESTAMP_NTZ  DEFAULT CURRENT_TIMESTAMP,
    FT_FUENTE                VARCHAR(200)   DEFAULT 'olive_young',
    ID_JOB                   VARCHAR(100)
);


-- ---------------------------------------------------------------------------
-- 5. MKT_COSMETICDESIGN_ART_HIST
--    Fuente: scrapers/cosmetics-design  (nutraingredients.com, artículos de
--            beauty & wellness — I+D de tendencias e ingredientes activos)
--    Granularidad: 1 fila = 1 artículo de la revista
--    Nota: ~40% de artículos tienen paywalled=true (contenido completo bloqueado);
--          article_content llegará vacío en esos casos.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS DEV_STG.GNM_MEX.SRC_COSMETICDESIGN_ART_HIST (
    -- artículo
    TX_TITULO                TEXT,          -- article_title
    URL_ARTICULO             TEXT,          -- article_url
    DT_PUBLICACION           TIMESTAMP_NTZ, -- publication_date (ISO-8601 → UTC)
    TX_RESUMEN               TEXT,          -- article_summary
    TX_CONTENIDO             TEXT,          -- article_content (vacío si paywalled)
    FL_PAYWALL               BOOLEAN,       -- paywalled

    -- multimedia
    URL_IMAGEN               TEXT,          -- lead_image_url
    TX_PIE_IMAGEN            TEXT,          -- image_caption

    -- taxonomía editorial (array de strings, e.g. ["Beauty & wellness", "Botanicals"])
    DS_TEMAS                 VARIANT,       -- related_topics

    -- metadatos del scraper
    DS_INPUT                 VARIANT,       -- seed enviado (url de la sección)

    -- auditoría
    DT_CARGA                 TIMESTAMP_NTZ  DEFAULT CURRENT_TIMESTAMP,
    FT_FUENTE                VARCHAR(200)   DEFAULT 'cosmetics_design',
    ID_JOB                   VARCHAR(100)
);


-- ---------------------------------------------------------------------------
-- 6. MKT_COSME_RANKING_HIST
--    Fuente: scrapers/cosme-ranking-products  (cosme.net, ranking semanal)
--    Granularidad: 1 fila = 1 producto en el ranking semanal
--    Periodo: DT_PERIODO_INICIO + DT_PERIODO_FIN (集計期間 visible en la página)
--    Detalle: incluye Stage 2 (descripción, ingredientes, imágenes del producto)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS DEV_STG.GNM_MEX.SRC_COSME_RANKING_HIST (
    -- ranking
    NU_RANK                  NUMBER(3,0),
    TX_RANK_CAMBIO           TEXT,          -- rank_change: "hot", "up", "down", "new", "same"

    -- producto
    ID_PRODUCTO              TEXT,
    NM_PRODUCTO              TEXT,
    NM_PRODUCTO_JP           TEXT,          -- product_name_jp (nombre original japonés)
    URL_PRODUCTO             TEXT,          -- product_url (cosme.net/products/{id}/)
    URL_IMG_PRINCIPAL        TEXT,          -- product_img (thumbnail del listing)

    -- marca
    ID_MARCA                 TEXT,
    NM_MARCA                 TEXT,
    NM_MARCA_JP              TEXT,          -- brand_name_jp
    URL_MARCA                TEXT,
    NM_FABRICANTE            TEXT,          -- manufacturer (メーカー)
    URL_FABRICANTE           TEXT,          -- manufacturer_url

    -- categoría
    NM_CATEGORIA             TEXT,          -- category (Stage 1, categoría del ranking)
    URL_CATEGORIA            TEXT,
    TX_CATEGORIA_FULL        TEXT,          -- category_full (jerarquía completa: "A > B > C")
    DS_CATEGORIA_PATH        VARIANT,       -- category_path (array [{name, url}])

    -- precio
    TX_PRECIO_RAW            TEXT,          -- price_text (texto completo: volumen + precio)
    NU_PRECIO_YEN            FLOAT,         -- precio numérico extraído
    TX_TALLA                 TEXT,          -- size (volumen/tamaño, ej. "30mL")
    FL_PRECIO_ABIERTO        BOOLEAN,       -- is_open_price
    FL_INCLUYE_IVA           BOOLEAN,       -- tax_included

    -- métricas de ranking y valoración
    NU_RATING                FLOAT,         -- rating (Stage 1, 0.0–7.0)
    NU_RATING_DETAIL         FLOAT,         -- rating_detail (Stage 2, p.average)
    NU_PUNTOS                FLOAT,         -- points (p.point, ej. 59.1)
    NU_RANK_CATEGORIA        NUMBER(5,0),   -- cat_rank (posición en su categoría)
    NM_CATEGORIA_RANK        TEXT,          -- cat_rank_name (nombre de la categoría rankeada)
    DS_RANKING_EN            VARIANT,       -- ranking_in (array de strings: "美容液ランキング 1位", …)

    -- métricas de comunidad
    NU_RESENAS               NUMBER(12,0),  -- review_count
    NU_FOTOS                 NUMBER(12,0),  -- photo_count (fotos de usuarias)
    NU_QA                    NUMBER(12,0),  -- qa_count (preguntas y respuestas)
    NU_LIKES                 NUMBER(12,0),  -- likes
    NU_HAVES                 NUMBER(12,0),  -- haves (usuarias que "tienen" el producto)

    -- lanzamiento
    TX_FECHA_LANZAMIENTO     TEXT,          -- release_date (texto japonés: 発売日：YYYY/M/D)

    -- flags del producto
    FL_BEST_COSME            BOOLEAN,       -- is_best_cosme (badge bestcosme)
    FL_NUEVO                 BOOLEAN,       -- is_new (badge nuevo)

    -- detalle del producto (Stage 2 — cosme.net/products/{id}/)
    TX_DESCRIPCION           TEXT,          -- description (商品説明)
    TX_MODO_USO              TEXT,          -- how_to_use (使い方)
    TX_INGREDIENTES          TEXT,          -- ingredients (全成分)
    TX_CLASIFICACION         TEXT,          -- classification (分類, ej. 医薬部外品)
    TX_JAN_CODE              TEXT,          -- jan_code
    URL_OFICIAL              TEXT,          -- official_url (公式サイト)
    DS_IMAGENES              VARIANT,       -- all_images (array de URLs)
    URL_TIENDA               TEXT,          -- shop_url (cosme.com redirect)
    DS_TIENDAS               VARIANT,       -- stores (array de nombres de tiendas físicas)
    DS_PRODUCTOS_RELACIONADOS VARIANT,      -- related_products (array [{name, url}])

    -- periodo del ranking (集計期間)
    DT_PERIODO_INICIO        DATE,          -- period_start
    DT_PERIODO_FIN           DATE,          -- period_end

    -- totales
    NU_TOTAL_RANKING         NUMBER(6,0),   -- total_products en el ranking

    -- metadatos del scraper
    DT_SCRAPING              TIMESTAMP_NTZ, -- scraped_at (ISO 8601)
    TX_SOURCE                VARCHAR(100),  -- source (ej. 'cosme.net/ranking/products')
    TX_PAIS                  VARCHAR(10),   -- country (ISO-2, ej. 'JP')
    TX_RANKING_POR           VARCHAR(20),   -- ranking_by (ej. 'product')
    DS_INPUT                 VARIANT,       -- inputs del job (page, max_pages, url)

    -- auditoría
    DT_CARGA                 TIMESTAMP_NTZ  DEFAULT CURRENT_TIMESTAMP,
    FT_FUENTE                VARCHAR(200)   DEFAULT 'cosme_ranking_products',
    ID_JOB                   VARCHAR(100)
);


-- =============================================================================
-- Permisos externos — STREAMLIT_DEVELOPER
-- Ejecutar con un rol que tenga MANAGE GRANTS sobre DEV_STG.GNM_MEX
-- =============================================================================

GRANT SELECT ON TABLE DEV_STG.GNM_MEX.SRC_COSMETICDESIGN_ART_HIST TO ROLE STREAMLIT_DEVELOPER;
GRANT SELECT ON TABLE DEV_STG.GNM_MEX.SRC_COSME_RANKING_HIST TO ROLE STREAMLIT_DEVELOPER;
