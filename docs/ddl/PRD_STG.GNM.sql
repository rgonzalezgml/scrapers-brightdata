-- =============================================================================
-- Schema:  PRD_STG.GNM
-- Norma:   GLI Nomenclatura v1.1.0 (MAYUSCULAS, sin acentos, prefijos de dominio)
-- Fuente:  scrapers BrightData → middlewares Python → agentes GeommaAI
-- Prefijo: MKT  (inteligencia de mercado / I+D / precios de proveedores)
-- Sufijo:  _HIST (tabla histórica; cada carga inserta, no sobreescribe)
--
-- Columnas de auditoría comunes a todas las tablas:
--   CREATED_AT TIMESTAMP_NTZ(9) DEFAULT CURRENT_TIMESTAMP() — momento de la carga al DWH (reemplaza DT_CARGA)
--   FT_FUENTE  VARCHAR(200)   — identificador del scraper que originó la fila
--   ID_JOB     VARCHAR(100)   — job / run_id del pipeline ETL
--
-- Convenciones de tipo:
--   VARIANT          → arrays JSON o objetos anidados  (Snowflake semi-structured)
--   VARCHAR(16777216) → texto sin límite fijo (máx Snowflake)
--   NUMBER(18,4)     → precio o monto monetario
--   NUMBER(5,2)      → rating o porcentaje con decimales
--   NUMBER            → entero o decimal sin punto flotante
--   BOOLEAN          → flag scraper (verified, out_of_stock, etc.)
--   DATE             → fecha sin hora (scraped_date, launch_date)
-- =============================================================================


-- ---------------------------------------------------------------------------
-- 1. SRC_ALIBABA_PROV_HIST
--    Fuente: scrapers/alibaba  (alibaba.com, búsqueda de químicos industriales)
--    Granularidad: 1 fila = 1 producto listado en alibaba
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE PRD_STG.GNM.SRC_ALIBABA_PROV_HIST (
    -- identificación
    URL_PRODUCTO             VARCHAR(16777216)  COMMENT 'URL del producto en alibaba.com',
    NM_PRODUCTO              VARCHAR(16777216)  COMMENT 'Nombre del producto normalizado (cleaned_product_name)',

    -- proveedor
    NM_PROVEEDOR             VARCHAR(16777216)  COMMENT 'Nombre del proveedor tal como aparece en el listing',

    -- precio
    TX_PRECIO_RAW            VARCHAR(16777216)  COMMENT 'Precio tal como aparece en la pagina, sin procesar',
    NU_PRECIO_MIN_USD        NUMBER(18,4)       COMMENT 'Precio minimo en dolares USD (extremo inferior del rango)',
    NU_PRECIO_MAX_USD        NUMBER(18,4)       COMMENT 'Precio maximo en dolares USD (extremo superior del rango)',
    TX_UNIDAD_PRECIO         VARCHAR(16777216)  COMMENT 'Unidad de medida del precio (e.g. "per kilogram")',

    -- producto
    TX_MOQ                   VARCHAR(16777216)  COMMENT 'Cantidad minima de pedido en texto libre (minimum_order_quantity)',
    TX_CAS                   VARCHAR(16777216)  COMMENT 'Numero CAS del compuesto quimico',
    TX_PUREZA                VARCHAR(16777216)  COMMENT 'Pureza del compuesto (e.g. "40%")',

    -- metadatos de la petición
    NU_STATUS_CODE           NUMBER(5,0)        COMMENT 'Codigo HTTP de respuesta del scraper',
    -- DS_INPUT                 VARIANT            COMMENT 'Seed JSON enviado al scraper (parametros de entrada del job)',

    -- auditoría ETL
    -- DT_CARGA  TIMESTAMP_NTZ  DEFAULT CURRENT_TIMESTAMP()  -- renombrado a CREATED_AT (auditoría GLI)
    FT_FUENTE                VARCHAR(200)       DEFAULT 'alibaba'             COMMENT 'Identificador del scraper que origino la fila',
    -- ID_JOB                   VARCHAR(100)       COMMENT 'Job ID / run_id del pipeline ETL que genero la fila',

    -- auditoría GLI
    CREATED_AT  TIMESTAMP_NTZ(9) DEFAULT CURRENT_TIMESTAMP() COMMENT 'Fecha y hora de creacion del registro',
    UPDATED_AT  TIMESTAMP_NTZ(9) DEFAULT CURRENT_TIMESTAMP() COMMENT 'Fecha y hora de ultima actualizacion del registro',
    CREATED_USR VARCHAR(100)     DEFAULT CURRENT_USER()      COMMENT 'Usuario que creo el registro',
    UPDATED_USR VARCHAR(100)     DEFAULT CURRENT_USER()      COMMENT 'Usuario que realizo la ultima actualizacion del registro'
)
COMMENT = 'Historico de productos de proveedores quimicos scrapeados de alibaba.com. Fuente: scraper alibaba (BrightData). Granularidad: 1 fila = 1 producto listado. Tabla append-only (cada carga inserta, no sobreescribe).';


-- ---------------------------------------------------------------------------
-- 2. SRC_INDIAMART_PROV_HIST
--    Fuente: scrapers/indiamart  (indiamart.com, directorios de proveedores)
--    Granularidad: 1 fila = 1 producto / proveedor listado
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE PRD_STG.GNM.SRC_INDIAMART_PROV_HIST (
    -- identificación
    ID_PRODUCTO              VARCHAR(16777216)  COMMENT 'Identificador unico del producto en indiamart.com',
    URL_PRODUCTO             VARCHAR(16777216)  COMMENT 'URL del producto en indiamart.com',
    NM_PRODUCTO_ORIGINAL     VARCHAR(16777216)  COMMENT 'Nombre del producto tal como aparece en la fuente, sin normalizar',
    NM_PRODUCTO_CLEAN        VARCHAR(16777216)  COMMENT 'Nombre del producto normalizado por el scraper',
    TX_DESCRIPCION           VARCHAR(16777216)  COMMENT 'Descripcion del producto en texto libre',
    TX_TIPO                  VARCHAR(16777216)  COMMENT 'Tipo de producto (e.g. "other")',

    -- categoría
    TX_CATEGORIA_MIC         VARCHAR(16777216)  COMMENT 'Categoria del producto segun la hoja MIC del catalogo interno',
    DS_CATEGORIA_PATH        VARIANT            COMMENT 'Jerarquia de categorias como array de strings',

    -- precio  (objeto {value, currency, symbol} en raw)
    DS_PRECIO_MIN_USD        VARIANT            COMMENT 'Objeto JSON con precio minimo: {value, currency, symbol}',
    DS_PRECIO_MAX_USD        VARIANT            COMMENT 'Objeto JSON con precio maximo: {value, currency, symbol}',
    TX_PRECIO_RAW            VARCHAR(16777216)  COMMENT 'Precio tal como aparece en la pagina, sin procesar',
    TX_PRECIO_VALOR_RAW      VARCHAR(16777216)  COMMENT 'Valor numerico del precio en texto (price_value_raw)',
    TX_UNIDAD_PRECIO         VARCHAR(16777216)  COMMENT 'Unidad de medida del precio',
    TX_MONEDA                VARCHAR(16777216)  COMMENT 'Codigo de moneda del precio (e.g. "INR", "USD")',
    TX_DISPONIBILIDAD        VARCHAR(16777216)  COMMENT 'Disponibilidad del producto (availability)',

    -- proveedor
    ID_PROVEEDOR             VARCHAR(16777216)  COMMENT 'Identificador unico del proveedor en indiamart.com',
    NM_PROVEEDOR             VARCHAR(16777216)  COMMENT 'Nombre del proveedor',
    URL_PROVEEDOR            VARCHAR(16777216)  COMMENT 'URL del perfil del proveedor en indiamart.com',
    TX_CIUDAD_PROVEEDOR      VARCHAR(16777216)  COMMENT 'Ciudad donde se ubica el proveedor',
    TX_PAIS_PROVEEDOR        VARCHAR(16777216)  COMMENT 'Pais del proveedor en codigo ISO-2 (e.g. "IN", "CN")',
    FL_VERIFICADO            BOOLEAN            COMMENT 'Indica si el proveedor fue verificado por indiamart',
    FL_TRUSTSEAL             BOOLEAN            COMMENT 'Indica si el proveedor tiene sello de confianza TrustSeal',
    NU_ANIO_MIEMBRO          NUMBER(4,0)        COMMENT 'Anio desde el que el proveedor es miembro de indiamart (member_since_year)',

    -- imagen
    URL_IMAGEN               VARCHAR(16777216)  COMMENT 'URL de la imagen principal del producto',

    -- metadatos del scraper
    TX_SITIO                 VARCHAR(50)        DEFAULT 'indiamart'  COMMENT 'Identificador del sitio fuente del scraper',
    DS_FLAGS                 VARIANT            COMMENT 'Flags internos del scraper (array)',
    DT_SCRAPING              DATE               COMMENT 'Fecha en que se realizo el scraping del producto',
    -- DS_INPUT                 VARIANT            COMMENT 'Seed JSON enviado al scraper (parametros de entrada del job)',

    -- auditoría ETL
    -- DT_CARGA  TIMESTAMP_NTZ  DEFAULT CURRENT_TIMESTAMP()  -- renombrado a CREATED_AT (auditoría GLI)
    FT_FUENTE                VARCHAR(200)       DEFAULT 'indiamart'           COMMENT 'Identificador del scraper que origino la fila',
    -- ID_JOB                   VARCHAR(100)       COMMENT 'Job ID / run_id del pipeline ETL que genero la fila',

    -- auditoría GLI
    CREATED_AT  TIMESTAMP_NTZ(9) DEFAULT CURRENT_TIMESTAMP() COMMENT 'Fecha y hora de creacion del registro',
    UPDATED_AT  TIMESTAMP_NTZ(9) DEFAULT CURRENT_TIMESTAMP() COMMENT 'Fecha y hora de ultima actualizacion del registro',
    CREATED_USR VARCHAR(100)     DEFAULT CURRENT_USER()      COMMENT 'Usuario que creo el registro',
    UPDATED_USR VARCHAR(100)     DEFAULT CURRENT_USER()      COMMENT 'Usuario que realizo la ultima actualizacion del registro'
)
COMMENT = 'Historico de productos y proveedores scrapeados de indiamart.com. Fuente: scraper indiamart (BrightData). Granularidad: 1 fila = 1 producto/proveedor listado. Tabla append-only (cada carga inserta, no sobreescribe).';


-- ---------------------------------------------------------------------------
-- 3. SRC_MADEINCHINA_PROV_HIST
--    Fuente: scrapers/made_in_china  (made-in-china.com, catálogos de químicos)
--    Granularidad: 1 fila = 1 producto de proveedor chino
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE PRD_STG.GNM.SRC_MADEINCHINA_PROV_HIST (
    -- identificación
    ID_PRODUCTO              VARCHAR(16777216)  COMMENT 'Identificador unico del producto en made-in-china.com (product_id)',
    TX_SKU                   VARCHAR(16777216)  COMMENT 'SKU del producto; coincide con product_id en la version v8 del scraper',
    URL_PRODUCTO             VARCHAR(16777216)  COMMENT 'URL del producto en made-in-china.com',
    NM_PRODUCTO_ORIGINAL     VARCHAR(16777216)  COMMENT 'Nombre del producto tal como aparece en la fuente, sin normalizar',
    NM_PRODUCTO_CLEAN        VARCHAR(16777216)  COMMENT 'Nombre del producto normalizado por el scraper',
    TX_TIPO                  VARCHAR(16777216)  COMMENT 'Tipo de producto (e.g. "chemical")',

    -- categoría
    TX_CATEGORIA_MIC         VARCHAR(16777216)  COMMENT 'Categoria del producto segun la hoja MIC del catalogo interno',
    DS_CATEGORIA_PATH        VARIANT            COMMENT 'Jerarquia de categorias como array de strings',

    -- precio  (objeto {value, currency, symbol} en raw)
    DS_PRECIO_MIN_USD        VARIANT            COMMENT 'Objeto JSON con precio minimo: {value, currency, symbol}',
    DS_PRECIO_MAX_USD        VARIANT            COMMENT 'Objeto JSON con precio maximo: {value, currency, symbol}',
    TX_PRECIO_RAW            VARCHAR(16777216)  COMMENT 'Precio tal como aparece en la pagina, sin procesar',
    TX_MONEDA                VARCHAR(16777216)  COMMENT 'Codigo de moneda del precio',

    -- MOQ
    NU_MOQ_CANTIDAD          NUMBER(18,3)       COMMENT 'Cantidad minima de pedido en valor numerico',
    TX_MOQ_UNIDAD            VARCHAR(16777216)  COMMENT 'Unidad de medida de la cantidad minima de pedido',

    -- especificaciones químicas
    TX_CAS                   VARCHAR(16777216)  COMMENT 'Numero CAS del compuesto quimico (cas_no)',
    TX_FORMULA               VARCHAR(16777216)  COMMENT 'Formula quimica del compuesto',
    TX_EINECS                VARCHAR(16777216)  COMMENT 'Numero EINECS del compuesto (registro europeo de sustancias quimicas)',
    TX_GRADO                 VARCHAR(16777216)  COMMENT 'Grado de calidad del compuesto (e.g. "Superior Grade")',
    TX_APARIENCIA            VARCHAR(16777216)  COMMENT 'Apariencia fisica del compuesto (e.g. "Solid")',

    -- proveedor
    ID_PROVEEDOR             VARCHAR(16777216)  COMMENT 'Identificador unico del proveedor en made-in-china.com',
    NM_PROVEEDOR_RAW         VARCHAR(16777216)  COMMENT 'Nombre del proveedor tal como aparece en la fuente (supplier_name_raw)',

    -- imagen
    URL_IMAGEN               VARCHAR(16777216)  COMMENT 'URL de la imagen principal del producto',

    -- metadatos del scraper
    TX_SITIO                 VARCHAR(50)        DEFAULT 'made-in-china'  COMMENT 'Identificador del sitio fuente del scraper',
    DS_FLAGS                 VARIANT            COMMENT 'Flags internos del scraper (array)',
    DT_SCRAPING              DATE               COMMENT 'Fecha en que se realizo el scraping del producto',
    -- DS_INPUT                 VARIANT            COMMENT 'Seed JSON enviado al scraper (parametros de entrada del job)',

    -- auditoría ETL
    -- DT_CARGA  TIMESTAMP_NTZ  DEFAULT CURRENT_TIMESTAMP()  -- renombrado a CREATED_AT (auditoría GLI)
    FT_FUENTE                VARCHAR(200)       DEFAULT 'made_in_china'       COMMENT 'Identificador del scraper que origino la fila',
    -- ID_JOB                   VARCHAR(100)       COMMENT 'Job ID / run_id del pipeline ETL que genero la fila',

    -- auditoría GLI
    CREATED_AT  TIMESTAMP_NTZ(9) DEFAULT CURRENT_TIMESTAMP() COMMENT 'Fecha y hora de creacion del registro',
    UPDATED_AT  TIMESTAMP_NTZ(9) DEFAULT CURRENT_TIMESTAMP() COMMENT 'Fecha y hora de ultima actualizacion del registro',
    CREATED_USR VARCHAR(100)     DEFAULT CURRENT_USER()      COMMENT 'Usuario que creo el registro',
    UPDATED_USR VARCHAR(100)     DEFAULT CURRENT_USER()      COMMENT 'Usuario que realizo la ultima actualizacion del registro'
)
COMMENT = 'Historico de productos de proveedores quimicos scrapeados de made-in-china.com. Fuente: scraper made_in_china (BrightData). Granularidad: 1 fila = 1 producto de proveedor chino. Tabla append-only (cada carga inserta, no sobreescribe).';


-- -- ---------------------------------------------------------------------------
-- -- 4. SRC_OLIVEYOUNG_RANK_HIST
-- --    Fuente: scrapers/olive_young  (global.oliveyoung.com, best-seller ranking)
-- --    Granularidad: 1 fila = 1 producto en el ranking de best-sellers
-- -- ---------------------------------------------------------------------------
-- CREATE OR REPLACE TABLE PRD_STG.GNM.SRC_OLIVEYOUNG_RANK_HIST (
--     -- ranking
--     NU_RANK                  NUMBER(5,0)        COMMENT 'Posicion del producto en el ranking de best-sellers de OliveYoung',
--     ID_PRODUCTO              VARCHAR(16777216)  COMMENT 'SKU del producto en OliveYoung (prdtNo)',

--     -- producto
--     NM_MARCA                 VARCHAR(16777216)  COMMENT 'Nombre de la marca del producto (brand)',
--     NM_PRODUCTO              VARCHAR(16777216)  COMMENT 'Nombre del producto en ingles (name)',
--     NM_PRODUCTO_KR           VARCHAR(16777216)  COMMENT 'Nombre del producto en coreano (name_kr)',

--     -- precio (texto con símbolo de moneda, e.g. "US$27.00")
--     TX_PRECIO_ORIGINAL       VARCHAR(16777216)  COMMENT 'Precio original del producto con simbolo de moneda, sin descuento',
--     TX_PRECIO_OFERTA         VARCHAR(16777216)  COMMENT 'Precio de oferta o con descuento del producto con simbolo de moneda',

--     -- métricas
--     NU_RATING                NUMBER(5,2)        COMMENT 'Calificacion promedio del producto (escala de la plataforma)',
--     FL_SIN_STOCK             BOOLEAN            COMMENT 'Indica si el producto esta agotado (out_of_stock)',

--     -- imagen
--     URL_IMAGEN               VARCHAR(16777216)  COMMENT 'URL de la imagen principal del producto',

--     -- metadatos del scraper
--     -- DS_INPUT                 VARIANT            COMMENT 'Seed JSON enviado al scraper (url de la pagina + region)',

--     -- auditoría ETL
--     -- DT_CARGA  TIMESTAMP_NTZ  DEFAULT CURRENT_TIMESTAMP()  -- renombrado a CREATED_AT (auditoría GLI)
--     FT_FUENTE                VARCHAR(200)       DEFAULT 'olive_young'         COMMENT 'Identificador del scraper que origino la fila',
--     -- ID_JOB                   VARCHAR(100)       COMMENT 'Job ID / run_id del pipeline ETL que genero la fila',

--     -- auditoría GLI
--     CREATED_AT  TIMESTAMP_NTZ(9) DEFAULT CURRENT_TIMESTAMP() COMMENT 'Fecha y hora de creacion del registro',
--     UPDATED_AT  TIMESTAMP_NTZ(9) DEFAULT CURRENT_TIMESTAMP() COMMENT 'Fecha y hora de ultima actualizacion del registro',
--     CREATED_USR VARCHAR(100)     DEFAULT CURRENT_USER()      COMMENT 'Usuario que creo el registro',
--     UPDATED_USR VARCHAR(100)     DEFAULT CURRENT_USER()      COMMENT 'Usuario que realizo la ultima actualizacion del registro'
-- )
-- COMMENT = 'Historico del ranking de best-sellers scrapeado de global.oliveyoung.com. Fuente: scraper olive_young (BrightData). Granularidad: 1 fila = 1 producto en el ranking de best-sellers. Tabla append-only (cada carga inserta, no sobreescribe).';


-- ---------------------------------------------------------------------------
-- 5. SRC_COSMETICDESIGN_ART_HIST
--    Fuente: scrapers/cosmetics-design  (nutraingredients.com, artículos de
--            beauty & wellness — I+D de tendencias e ingredientes activos)
--    Granularidad: 1 fila = 1 artículo de la revista
--    Nota: ~40% de artículos tienen paywalled=true (contenido completo bloqueado);
--          article_content llegará vacío en esos casos.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE PRD_STG.GNM.SRC_COSMETICDESIGN_ART_HIST (
    -- artículo
    TX_TITULO                VARCHAR(16777216)  COMMENT 'Titulo del articulo tal como aparece en la publicacion (article_title)',
    URL_ARTICULO             VARCHAR(16777216)  COMMENT 'URL canonica del articulo en cosmeticdesign.com (article_url)',
    DT_PUBLICACION           TIMESTAMP_NTZ      COMMENT 'Fecha y hora de publicacion del articulo en UTC, formato ISO-8601 (publication_date)',
    TX_RESUMEN               VARCHAR(16777216)  COMMENT 'Resumen o bajada del articulo (article_summary)',
    TX_CONTENIDO             VARCHAR(16777216)  COMMENT 'Contenido completo del articulo; vacio si el articulo esta bloqueado por paywall (article_content)',
    FL_PAYWALL               BOOLEAN            COMMENT 'Indica si el articulo requiere suscripcion de pago para acceder al contenido completo (paywalled)',

    -- multimedia
    URL_IMAGEN               VARCHAR(16777216)  COMMENT 'URL de la imagen principal (lead) del articulo (lead_image_url)',
    TX_PIE_IMAGEN            VARCHAR(16777216)  COMMENT 'Pie de foto o leyenda de la imagen principal (image_caption)',

    -- taxonomía editorial (array de strings, e.g. ["Beauty & wellness", "Botanicals"])
    DS_TEMAS                 VARIANT            COMMENT 'Temas y etiquetas editoriales del articulo como array de strings (related_topics)',

    -- metadatos del scraper
    -- DS_INPUT                 VARIANT            COMMENT 'Seed JSON enviado al scraper (url de la seccion scrapeada)',

    -- auditoría ETL
    -- DT_CARGA  TIMESTAMP_NTZ  DEFAULT CURRENT_TIMESTAMP()  -- renombrado a CREATED_AT (auditoría GLI)
    FT_FUENTE                VARCHAR(200)       DEFAULT 'cosmetics_design'    COMMENT 'Identificador del scraper que origino la fila',
    -- ID_JOB                   VARCHAR(100)       COMMENT 'Job ID / run_id del pipeline ETL que genero la fila',

    -- auditoría GLI
    CREATED_AT  TIMESTAMP_NTZ(9) DEFAULT CURRENT_TIMESTAMP() COMMENT 'Fecha y hora de creacion del registro',
    UPDATED_AT  TIMESTAMP_NTZ(9) DEFAULT CURRENT_TIMESTAMP() COMMENT 'Fecha y hora de ultima actualizacion del registro',
    CREATED_USR VARCHAR(100)     DEFAULT CURRENT_USER()      COMMENT 'Usuario que creo el registro',
    UPDATED_USR VARCHAR(100)     DEFAULT CURRENT_USER()      COMMENT 'Usuario que realizo la ultima actualizacion del registro'
)
COMMENT = 'Historico de articulos de beauty & wellness scrapeados de cosmeticdesign.com (nutraingredients.com). Fuente: scraper cosmetics_design (BrightData). Granularidad: 1 fila = 1 articulo de la revista. Aprox. 40% de filas tendran TX_CONTENIDO vacio por paywall. Tabla append-only (cada carga inserta, no sobreescribe).';


-- ---------------------------------------------------------------------------
-- 6. SRC_COSME_RANKING_HIST
--    Fuente: scrapers/cosme-ranking-products  (cosme.net, ranking semanal)
--    Granularidad: 1 fila = 1 producto en el ranking semanal
--    Periodo: DT_PERIODO_INICIO + DT_PERIODO_FIN (集計期間 visible en la página)
--    Detalle: incluye Stage 2 (descripción, ingredientes, imágenes del producto)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE PRD_STG.GNM.SRC_COSME_RANKING_HIST (
    -- ranking
    NU_RANK                  NUMBER(3,0)        COMMENT 'Posicion del producto en el ranking de la categoria scrapeada',
    TX_RANK_CAMBIO           VARCHAR(16777216)  COMMENT 'Variacion de posicion respecto al periodo anterior: "hot", "up", "down", "new", "same" (rank_change)',

    -- producto
    ID_PRODUCTO              VARCHAR(16777216)  COMMENT 'Identificador unico del producto en cosme.net',
    NM_PRODUCTO              VARCHAR(16777216)  COMMENT 'Nombre del producto en ingles o romanizado',
    NM_PRODUCTO_JP           VARCHAR(16777216)  COMMENT 'Nombre original del producto en japones (product_name_jp)',
    URL_PRODUCTO             VARCHAR(16777216)  COMMENT 'URL del producto en cosme.net (cosme.net/products/{id}/)',
    URL_IMG_PRINCIPAL        VARCHAR(16777216)  COMMENT 'URL del thumbnail del producto en el listing del ranking (product_img)',

    -- marca
    -- ID_MARCA                 VARCHAR(16777216)  COMMENT 'Identificador unico de la marca en cosme.net',
    NM_MARCA                 VARCHAR(16777216)  COMMENT 'Nombre de la marca en ingles o romanizado',
    NM_MARCA_JP              VARCHAR(16777216)  COMMENT 'Nombre de la marca en japones (brand_name_jp)',
    URL_MARCA                VARCHAR(16777216)  COMMENT 'URL del perfil de la marca en cosme.net',
    NM_FABRICANTE            VARCHAR(16777216)  COMMENT 'Nombre del fabricante del producto (メーカー)',
    URL_FABRICANTE           VARCHAR(16777216)  COMMENT 'URL del perfil del fabricante en cosme.net (manufacturer_url)',

    -- categoría
    NM_CATEGORIA             VARCHAR(16777216)  COMMENT 'Nombre de la categoria del ranking scrapeada en Stage 1',
    URL_CATEGORIA            VARCHAR(16777216)  COMMENT 'URL de la pagina de la categoria en cosme.net',
    TX_CATEGORIA_FULL        VARCHAR(16777216)  COMMENT 'Jerarquia completa de la categoria en texto (e.g. "A > B > C") (category_full)',
    DS_CATEGORIA_PATH        VARIANT            COMMENT 'Jerarquia de categorias como array de objetos [{name, url}] (category_path)',

    -- precio
    TX_PRECIO_RAW            VARCHAR(16777216)  COMMENT 'Texto completo del precio incluyendo volumen y precio (price_text)',
    NU_PRECIO_YEN            NUMBER(18,4)       COMMENT 'Precio numerico extraido del texto, expresado en yenes japoneses',
    TX_TALLA                 VARCHAR(16777216)  COMMENT 'Volumen o tamano del producto (e.g. "30mL") (size)',
    FL_PRECIO_ABIERTO        BOOLEAN            COMMENT 'Indica si el precio es abierto (el fabricante no fija precio de venta) (is_open_price)',
    FL_INCLUYE_IVA           BOOLEAN            COMMENT 'Indica si el precio mostrado incluye impuesto (tax_included)',

    -- métricas de ranking y valoración
    NU_RATING                NUMBER(5,2)        COMMENT 'Calificacion promedio del producto en Stage 1 del scraper (escala 0.0 a 7.0)',
    NU_RATING_DETAIL         NUMBER(5,2)        COMMENT 'Calificacion promedio detallada del producto obtenida en Stage 2 (p.average)',
    NU_PUNTOS                NUMBER(8,2)        COMMENT 'Puntaje del producto en el ranking de cosme.net (p.point, e.g. 1539.7)',
    NU_RANK_CATEGORIA        NUMBER(5,0)        COMMENT 'Posicion del producto dentro de su propia categoria (cat_rank)',
    NM_CATEGORIA_RANK        VARCHAR(16777216)  COMMENT 'Nombre de la categoria en la que el producto tiene posicion de ranking (cat_rank_name)',
    DS_RANKING_EN            VARIANT            COMMENT 'Lista de rankings en los que aparece el producto como array de strings (e.g. "美容液ランキング 1位") (ranking_in)',

    -- métricas de comunidad
    NU_RESENAS               NUMBER(12,0)       COMMENT 'Cantidad de resenas de usuarias para el producto (review_count)',
    NU_FOTOS                 NUMBER(12,0)       COMMENT 'Cantidad de fotos de usuarias asociadas al producto (photo_count)',
    NU_QA                    NUMBER(12,0)       COMMENT 'Cantidad de preguntas y respuestas de la comunidad (qa_count)',
    NU_LIKES                 NUMBER(12,0)       COMMENT 'Cantidad de likes del producto en la comunidad',
    NU_HAVES                 NUMBER(12,0)       COMMENT 'Cantidad de usuarias que marcaron el producto como que lo tienen (haves)',

    -- lanzamiento
    TX_FECHA_LANZAMIENTO     VARCHAR(16777216)  COMMENT 'Fecha de lanzamiento en texto japones tal como aparece en la pagina (発売日：YYYY/M/D) (release_date)',

    -- flags del producto
    FL_BEST_COSME            BOOLEAN            COMMENT 'Indica si el producto tiene el badge de Best Cosme (is_best_cosme)',
    FL_NUEVO                 BOOLEAN            COMMENT 'Indica si el producto tiene el badge de nuevo lanzamiento (is_new)',

    -- detalle del producto (Stage 2 — cosme.net/products/{id}/)
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

    -- periodo del ranking (集計期間)
    DT_PERIODO_INICIO        DATE               COMMENT 'Fecha de inicio del periodo de agregacion del ranking (period_start)',
    DT_PERIODO_FIN           DATE               COMMENT 'Fecha de fin del periodo de agregacion del ranking (period_end)',

    -- totales
    -- NU_TOTAL_RANKING         NUMBER(6,0)        COMMENT 'Cantidad total de productos en el ranking en el momento del scraping (total_products)',

    -- metadatos del scraper
    DT_SCRAPING              TIMESTAMP_NTZ      COMMENT 'Fecha y hora en que se realizo el scraping, formato ISO 8601 (scraped_at)',
    TX_SOURCE                VARCHAR(100)       COMMENT 'Identificador de la fuente dentro del sitio (e.g. "cosme.net/ranking/products") (source)',
    TX_PAIS                  VARCHAR(10)        COMMENT 'Codigo de pais ISO-2 del sitio scrapeado (e.g. "JP") (country)',
    TX_RANKING_POR           VARCHAR(20)        COMMENT 'Criterio de agrupacion del ranking (e.g. "product") (ranking_by)',
    -- DS_INPUT                 VARIANT            COMMENT 'Seed JSON enviado al scraper (page, max_pages, url del ranking)',

    -- auditoría ETL
    -- DT_CARGA  TIMESTAMP_NTZ  DEFAULT CURRENT_TIMESTAMP()  -- renombrado a CREATED_AT (auditoría GLI)
    FT_FUENTE                VARCHAR(200)       DEFAULT 'cosme_ranking_products'   COMMENT 'Identificador del scraper que origino la fila',
    -- ID_JOB                   VARCHAR(100)       COMMENT 'Job ID / run_id del pipeline ETL que genero la fila',

    -- auditoría GLI
    CREATED_AT  TIMESTAMP_NTZ(9) DEFAULT CURRENT_TIMESTAMP() COMMENT 'Fecha y hora de creacion del registro',
    UPDATED_AT  TIMESTAMP_NTZ(9) DEFAULT CURRENT_TIMESTAMP() COMMENT 'Fecha y hora de ultima actualizacion del registro',
    CREATED_USR VARCHAR(100)     DEFAULT CURRENT_USER()      COMMENT 'Usuario que creo el registro',
    UPDATED_USR VARCHAR(100)     DEFAULT CURRENT_USER()      COMMENT 'Usuario que realizo la ultima actualizacion del registro'
)
COMMENT = 'Historico del ranking semanal de productos scrapeado de cosme.net. Fuente: scraper cosme_ranking_products (BrightData). Granularidad: 1 fila = 1 producto en el ranking semanal; incluye detalle de Stage 2 (descripcion, ingredientes, imagenes). El periodo cubierto se identifica por DT_PERIODO_INICIO + DT_PERIODO_FIN. Tabla append-only (cada carga inserta, no sobreescribe).';


-- =============================================================================
-- Permisos externos — DEVELOPER_ROLE
-- Ejecutar con un rol que tenga MANAGE GRANTS sobre PRD_STG.GNM
-- =============================================================================

GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE ON TABLE PRD_STG.GNM.SRC_ALIBABA_PROV_HIST         TO ROLE DEVELOPER_ROLE;
GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE ON TABLE PRD_STG.GNM.SRC_INDIAMART_PROV_HIST       TO ROLE DEVELOPER_ROLE;
GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE ON TABLE PRD_STG.GNM.SRC_MADEINCHINA_PROV_HIST     TO ROLE DEVELOPER_ROLE;
GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE ON TABLE PRD_STG.GNM.SRC_OLIVEYOUNG_RANK_HIST      TO ROLE DEVELOPER_ROLE;
GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE ON TABLE PRD_STG.GNM.SRC_COSMETICDESIGN_ART_HIST   TO ROLE DEVELOPER_ROLE;
GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE ON TABLE PRD_STG.GNM.SRC_COSME_RANKING_HIST        TO ROLE DEVELOPER_ROLE;




  
--   ALTER TABLE PRD_STG.GNM.SRC_COSMETICDESIGN_ART_HIST
--   MODIFY COLUMN CREATED_AT SET DEFAULT CURRENT_TIMESTAMP();

-- ALTER TABLE PRD_STG.GNM.SRC_COSMETICDESIGN_ART_HIST
--   MODIFY COLUMN UPDATED_AT SET DEFAULT CURRENT_TIMESTAMP();

-- ALTER TABLE PRD_STG.GNM.SRC_COSMETICDESIGN_ART_HIST
--   MODIFY COLUMN CREATED_USR SET DEFAULT CURRENT_USER();

-- ALTER TABLE PRD_STG.GNM.SRC_COSMETICDESIGN_ART_HIST
--   MODIFY COLUMN UPDATED_USR SET DEFAULT CURRENT_USER();


-- -- Angel
-- create or replace TABLE PRD_STG.GNM.SRC_OLIVEYOUNG_RANK_HIST (
-- 	NU_RANK NUMBER(5,0) COMMENT 'Posicion en el ranking best-seller de Olive Young (1-100)',
-- 	ID_PRODUCTO VARCHAR(16777216) COMMENT 'Identificador unico del producto en Olive Young',
-- 	NM_MARCA VARCHAR(16777216) COMMENT 'Nombre de la marca del producto',
-- 	NM_PRODUCTO VARCHAR(16777216) COMMENT 'Nombre del producto en ingles',
-- 	NM_PRODUCTO_KR VARCHAR(16777216) COMMENT 'Nombre del producto en coreano',
-- 	TX_PRECIO_ORIGINAL VARCHAR(16777216) COMMENT 'Precio original del producto (texto con moneda, ej. US$30.00)',
-- 	TX_PRECIO_OFERTA VARCHAR(16777216) COMMENT 'Precio de oferta o con descuento (texto con moneda)',
-- 	NU_RATING FLOAT COMMENT 'Calificacion promedio del producto (escala 1-5)',
-- 	FL_SIN_STOCK BOOLEAN COMMENT 'Indicador de producto sin stock (true/false)',
-- 	URL_IMAGEN VARCHAR(16777216) COMMENT 'URL de la imagen del producto en CDN de Olive Young',
-- 	DS_INPUT VARIANT COMMENT 'Metadata del scraping en formato JSON (region, URL fuente)',
-- 	DT_CARGA TIMESTAMP_NTZ(9) DEFAULT CURRENT_TIMESTAMP() COMMENT 'Fecha y hora de extraccion/scraping del dato',
-- 	FT_FUENTE VARCHAR(200) DEFAULT 'olive_young' COMMENT 'Identificador de la fuente de datos (olive_young)',
-- 	ID_JOB VARCHAR(100) COMMENT 'Identificador del job de extraccion que genero el registro',
-- 	CREATED_AT TIMESTAMP_NTZ(9) DEFAULT CURRENT_TIMESTAMP() COMMENT 'Fecha y hora de creacion del registro',
-- 	UPDATED_AT TIMESTAMP_NTZ(9) DEFAULT CURRENT_TIMESTAMP() COMMENT 'Fecha y hora de ultima actualizacion del registro',
-- 	CREATED_USR VARCHAR(100) DEFAULT CURRENT_USER() COMMENT 'Usuario que creo el registro',
-- 	UPDATED_USR VARCHAR(100) DEFAULT CURRENT_USER() COMMENT 'Usuario que realizo la ultima actualizacion del registro'
-- )COMMENT='Historico de ranking de productos best-seller de Olive Young'; 



-- TRUNCATE PRD_STG.GNM.SRC_COSME_RANKING_HIST;