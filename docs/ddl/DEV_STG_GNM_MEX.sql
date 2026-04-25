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
-- 5. MKT_COSMEDESIGN_ART_HIST
--    Fuente: scrapers/cosmetics-design  (nutraingredients.com, artículos de
--            beauty & wellness — I+D de tendencias e ingredientes activos)
--    Granularidad: 1 fila = 1 artículo de la revista
--    Nota: ~40% de artículos tienen paywalled=true (contenido completo bloqueado);
--          article_content llegará vacío en esos casos.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS DEV_STG.GNM_MEX.SRC_COSMEDESIGN_ART_HIST (
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
-- 6. MKT_COSME_AWARD_HIST
--    Fuente: scrapers/cosme  (cosme.net, premios bestcosme anuales)
--    Granularidad: 1 fila = 1 producto ganador / nominado
--    Nota: el scraper emite 3 entity-types (product/ranking/brand);
--          esta tabla almacena sólo las filas entity="product".
--          Ver MKT_COSME_RANKING_HIST y MKT_COSME_BRAND_HIST si se requieren.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS DEV_STG.GNM_MEX.SRC_COSME_AWARD_HIST (
    -- identificación
    ID_PRODUCTO              TEXT,
    URL_PRODUCTO             TEXT,
    NM_PRODUCTO_RAW          TEXT,          -- product_name_raw (japonés)
    NM_PRODUCTO_CLEAN        TEXT,          -- normalizado post-mojibake

    -- marca / fabricante
    ID_MARCA                 TEXT,
    NM_MARCA                 TEXT,
    ID_FABRICANTE            TEXT,
    NM_FABRICANTE            TEXT,

    -- categorías
    ID_CATEGORIA_PRIMARIA    TEXT,
    DS_CATEGORIA_IDS         VARIANT,       -- array de IDs
    DS_CATEGORIA_NOMBRES     VARIANT,       -- array de strings
    DS_CATEGORIA_CADENAS     VARIANT,       -- array de arrays de objetos (breadcrumb)

    -- efectos / ingredientes
    DS_EFECTO_IDS            VARIANT,
    DS_EFECTO_NOMBRES        VARIANT,
    DS_INGREDIENTE_IDS       VARIANT,

    -- métricas de comunidad
    NU_RATING_AVG            FLOAT,
    NU_RESENAS               NUMBER(12,0),  -- review_count
    NU_RESENAS_FOTO          NUMBER(12,0),  -- review_count_photo

    -- lanzamiento
    TX_FECHA_LANZAMIENTO     TEXT,          -- launch_date (formato variable)
    NU_ANIO_LANZAMIENTO      NUMBER(4,0),

    -- rankings bestcosme embebidos en el producto
    DS_RANKINGS              VARIANT,       -- array de objetos {year, group, rank…}

    -- variaciones de producto
    DS_VARIACIONES           VARIANT,

    -- clasificación regulatoria
    TX_CLASE_REGULACION      TEXT,

    -- flags de calidad del scraper
    FL_OFICIAL               BOOLEAN,       -- is_official
    FL_MOJIBAKE              BOOLEAN,       -- has_mojibake (señal de encoding roto)
    TX_NOMBRE_FUENTE         TEXT,          -- _name_source (debug: de dónde viene el nombre)

    -- metadatos del scraper
    DT_SCRAPING              DATE,
    DS_INPUT                 VARIANT,

    -- auditoría
    DT_CARGA                 TIMESTAMP_NTZ  DEFAULT CURRENT_TIMESTAMP,
    FT_FUENTE                VARCHAR(200)   DEFAULT 'cosme',
    ID_JOB                   VARCHAR(100)
);
