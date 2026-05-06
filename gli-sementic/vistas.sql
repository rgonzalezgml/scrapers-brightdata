-- =============================================================================
-- Vistas capa semántica — PRD_CNS_SHD.DATA_GNM
-- Fuente: scrapers BrightData → PRD_STG.GNM → vistas normalizadas
-- Convenciones: UPPER() en texto, URLs sin modificar, CREATED_AT::DATE → FECHA_CONSULTA
-- GRANTs: CORTEX_ANALYST_ROLE + ANALYST_MX_ROLE en cada vista
-- =============================================================================


-- ---------------------------------------------------------------------------
-- 1. VW_OLIVEYOUNG_RANK_HIST  [YA EXISTE — creada por Ángel 2026-04-29]
-- ---------------------------------------------------------------------------
create or replace view PRD_CNS_SHD.DATA_GNM.VW_OLIVEYOUNG_RANK_HIST(
    RANKING             COMMENT 'Posicion del producto en el ranking best-seller de Olive Young (1-100)',
    ID_PRODUCTO         COMMENT 'SKU del producto en Olive Young (prdtNo)',
    MARCA               COMMENT 'Nombre de la marca del producto',
    NOMBRE_PRODUCTO     COMMENT 'Nombre del producto en ingles',
    NOMBRE_PRODUCTO_KR  COMMENT 'Nombre del producto en coreano',
    PRECIO_ORIGINAL     COMMENT 'Precio original con simbolo de moneda, sin descuento (ej. US$27.00)',
    PRECIO_OFERTA       COMMENT 'Precio de oferta o con descuento con simbolo de moneda',
    RATING              COMMENT 'Calificacion promedio del producto (escala de la plataforma)',
    FLAG_SIN_STOCK      COMMENT 'Indica si el producto esta agotado',
    URL_IMAGEN          COMMENT 'URL de la imagen principal del producto',
    FUENTE              COMMENT 'Identificador del scraper que origino la fila (olive_young)',
    FECHA_CONSULTA      COMMENT 'Fecha en que se realizo la extraccion del dato'
) COMMENT='Vista del ranking best-seller de Olive Young Global. Top 100 productos por fecha de consulta. Fuente: PRD_STG.GNM.SRC_OLIVEYOUNG_RANK_HIST'
as
SELECT
    NU_RANK                             AS RANKING,
    UPPER(ID_PRODUCTO)                  AS ID_PRODUCTO,
    UPPER(NM_MARCA)                     AS MARCA,
    UPPER(NM_PRODUCTO)                  AS NOMBRE_PRODUCTO,
    NM_PRODUCTO_KR                      AS NOMBRE_PRODUCTO_KR,
    TX_PRECIO_ORIGINAL                  AS PRECIO_ORIGINAL,
    TX_PRECIO_OFERTA                    AS PRECIO_OFERTA,
    NU_RATING                           AS RATING,
    FL_SIN_STOCK                        AS FLAG_SIN_STOCK,
    URL_IMAGEN,
    FT_FUENTE                           AS FUENTE,
    CREATED_AT::DATE                    AS FECHA_CONSULTA
FROM PRD_STG.GNM.SRC_OLIVEYOUNG_RANK_HIST;

GRANT SELECT ON PRD_CNS_SHD.DATA_GNM.VW_OLIVEYOUNG_RANK_HIST TO ROLE CORTEX_ANALYST_ROLE;
GRANT SELECT ON PRD_CNS_SHD.DATA_GNM.VW_OLIVEYOUNG_RANK_HIST TO ROLE ANALYST_MX_ROLE;



-- ---------------------------------------------------------------------------
-- 2. VW_ALIBABA_PROV_HIST
--    Fuente: PRD_STG.GNM.SRC_ALIBABA_PROV_HIST
--    Precios B2B de quimicos industriales y empaque en Alibaba
-- ---------------------------------------------------------------------------
create or replace view PRD_CNS_SHD.DATA_GNM.VW_ALIBABA_PROV_HIST(
    URL_PRODUCTO        COMMENT 'URL del producto en alibaba.com',
    NOMBRE_PRODUCTO     COMMENT 'Nombre del producto normalizado por el scraper',
    PROVEEDOR           COMMENT 'Nombre del proveedor tal como aparece en el listing',
    PRECIO_RAW          COMMENT 'Precio tal como aparece en la pagina, sin procesar',
    PRECIO_MIN_USD      COMMENT 'Precio minimo convertido a dolares USD',
    PRECIO_MAX_USD      COMMENT 'Precio maximo convertido a dolares USD',
    UNIDAD_PRECIO       COMMENT 'Unidad de medida del precio (ej. per kilogram)',
    MOQ                 COMMENT 'Cantidad minima de pedido en texto libre',
    CAS                 COMMENT 'Numero CAS del compuesto quimico',
    PUREZA              COMMENT 'Pureza del compuesto (ej. 40%)',
    FUENTE              COMMENT 'Identificador del scraper que origino la fila (alibaba)',
    FECHA_CONSULTA      COMMENT 'Fecha en que se realizo la extraccion del dato'
) COMMENT='Vista de precios B2B de quimicos industriales y empaque scrapeados de alibaba.com. Fuente: PRD_STG.GNM.SRC_ALIBABA_PROV_HIST'
as
SELECT
    URL_PRODUCTO,
    UPPER(NM_PRODUCTO)                  AS NOMBRE_PRODUCTO,
    UPPER(NM_PROVEEDOR)                 AS PROVEEDOR,
    TX_PRECIO_RAW                       AS PRECIO_RAW,
    NU_PRECIO_MIN_USD                   AS PRECIO_MIN_USD,
    NU_PRECIO_MAX_USD                   AS PRECIO_MAX_USD,
    UPPER(TX_UNIDAD_PRECIO)             AS UNIDAD_PRECIO,
    UPPER(TX_MOQ)                       AS MOQ,
    UPPER(TX_CAS)                       AS CAS,
    UPPER(TX_PUREZA)                    AS PUREZA,
    FT_FUENTE                           AS FUENTE,
    CREATED_AT::DATE                    AS FECHA_CONSULTA
FROM PRD_STG.GNM.SRC_ALIBABA_PROV_HIST;

GRANT SELECT ON PRD_CNS_SHD.DATA_GNM.VW_ALIBABA_PROV_HIST TO ROLE CORTEX_ANALYST_ROLE;
GRANT SELECT ON PRD_CNS_SHD.DATA_GNM.VW_ALIBABA_PROV_HIST TO ROLE ANALYST_MX_ROLE;


-- ---------------------------------------------------------------------------
-- 3. VW_INDIAMART_PROV_HIST
--    Fuente: PRD_STG.GNM.SRC_INDIAMART_PROV_HIST
--    Proveedores y precios de quimicos industriales en IndiaMart
-- ---------------------------------------------------------------------------
create or replace view PRD_CNS_SHD.DATA_GNM.VW_INDIAMART_PROV_HIST(
    ID_PRODUCTO         COMMENT 'Identificador unico del producto en indiamart.com',
    URL_PRODUCTO        COMMENT 'URL del producto en indiamart.com',
    NOMBRE_PRODUCTO     COMMENT 'Nombre del producto normalizado por el scraper',
    NOMBRE_PRODUCTO_RAW COMMENT 'Nombre del producto tal como aparece en la fuente, sin normalizar',
    DESCRIPCION         COMMENT 'Descripcion del producto en texto libre',
    TIPO                COMMENT 'Tipo de producto',
    CATEGORIA           COMMENT 'Categoria del producto segun catalogo interno',
    PRECIO_RAW          COMMENT 'Precio tal como aparece en la pagina, sin procesar',
    PRECIO_VALOR_RAW    COMMENT 'Valor numerico del precio en texto',
    PRECIO_MIN_USD      COMMENT 'Objeto JSON con precio minimo en USD',
    PRECIO_MAX_USD      COMMENT 'Objeto JSON con precio maximo en USD',
    UNIDAD_PRECIO       COMMENT 'Unidad de medida del precio',
    MONEDA              COMMENT 'Codigo de moneda del precio (ej. INR, USD)',
    DISPONIBILIDAD      COMMENT 'Disponibilidad del producto',
    ID_PROVEEDOR        COMMENT 'Identificador unico del proveedor en indiamart.com',
    PROVEEDOR           COMMENT 'Nombre del proveedor',
    URL_PROVEEDOR       COMMENT 'URL del perfil del proveedor en indiamart.com',
    CIUDAD_PROVEEDOR    COMMENT 'Ciudad donde se ubica el proveedor',
    PAIS_PROVEEDOR      COMMENT 'Pais del proveedor en codigo ISO-2',
    FLAG_VERIFICADO     COMMENT 'Indica si el proveedor fue verificado por IndiaMART',
    FLAG_TRUSTSEAL      COMMENT 'Indica si el proveedor tiene sello de confianza TrustSeal',
    ANIOS_MIEMBRO       COMMENT 'Anios que el proveedor lleva como miembro de IndiaMART',
    URL_IMAGEN          COMMENT 'URL de la imagen principal del producto',
    FECHA_SCRAPING      COMMENT 'Fecha en que se realizo el scraping del producto',
    FUENTE              COMMENT 'Identificador del scraper que origino la fila (indiamart)',
    FECHA_CONSULTA      COMMENT 'Fecha en que se realizo la extraccion del dato'
) COMMENT='Vista de proveedores y precios de quimicos industriales scrapeados de indiamart.com. Fuente: PRD_STG.GNM.SRC_INDIAMART_PROV_HIST'
as
SELECT
    UPPER(ID_PRODUCTO)                  AS ID_PRODUCTO,
    URL_PRODUCTO,
    UPPER(NM_PRODUCTO_CLEAN)            AS NOMBRE_PRODUCTO,
    UPPER(NM_PRODUCTO_ORIGINAL)         AS NOMBRE_PRODUCTO_RAW,
    UPPER(TX_DESCRIPCION)               AS DESCRIPCION,
    UPPER(TX_TIPO)                      AS TIPO,
    UPPER(TX_CATEGORIA_MIC)             AS CATEGORIA,
    TX_PRECIO_RAW                       AS PRECIO_RAW,
    TX_PRECIO_VALOR_RAW                 AS PRECIO_VALOR_RAW,
    DS_PRECIO_MIN_USD                   AS PRECIO_MIN_USD,
    DS_PRECIO_MAX_USD                   AS PRECIO_MAX_USD,
    UPPER(TX_UNIDAD_PRECIO)             AS UNIDAD_PRECIO,
    UPPER(TX_MONEDA)                    AS MONEDA,
    UPPER(TX_DISPONIBILIDAD)            AS DISPONIBILIDAD,
    UPPER(ID_PROVEEDOR)                 AS ID_PROVEEDOR,
    UPPER(NM_PROVEEDOR)                 AS PROVEEDOR,
    URL_PROVEEDOR,
    UPPER(TX_CIUDAD_PROVEEDOR)          AS CIUDAD_PROVEEDOR,
    UPPER(TX_PAIS_PROVEEDOR)            AS PAIS_PROVEEDOR,
    FL_VERIFICADO                       AS FLAG_VERIFICADO,
    FL_TRUSTSEAL                        AS FLAG_TRUSTSEAL,
    NU_ANIO_MIEMBRO                     AS ANIOS_MIEMBRO,
    URL_IMAGEN,
    DT_SCRAPING                         AS FECHA_SCRAPING,
    FT_FUENTE                           AS FUENTE,
    CREATED_AT::DATE                    AS FECHA_CONSULTA
FROM PRD_STG.GNM.SRC_INDIAMART_PROV_HIST;

GRANT SELECT ON PRD_CNS_SHD.DATA_GNM.VW_INDIAMART_PROV_HIST TO ROLE CORTEX_ANALYST_ROLE;
GRANT SELECT ON PRD_CNS_SHD.DATA_GNM.VW_INDIAMART_PROV_HIST TO ROLE ANALYST_MX_ROLE;


-- ---------------------------------------------------------------------------
-- 4. VW_MADEINCHINA_PROV_HIST
--    Fuente: PRD_STG.GNM.SRC_MADEINCHINA_PROV_HIST
--    Proveedores y precios de quimicos industriales en Made-in-China
-- ---------------------------------------------------------------------------
create or replace view PRD_CNS_SHD.DATA_GNM.VW_MADEINCHINA_PROV_HIST(
    ID_PRODUCTO         COMMENT 'Identificador unico del producto en made-in-china.com',
    SKU                 COMMENT 'SKU del producto',
    URL_PRODUCTO        COMMENT 'URL del producto en made-in-china.com',
    NOMBRE_PRODUCTO     COMMENT 'Nombre del producto normalizado por el scraper',
    NOMBRE_PRODUCTO_RAW COMMENT 'Nombre del producto tal como aparece en la fuente, sin normalizar',
    TIPO                COMMENT 'Tipo de producto (chemical / packaging)',
    CATEGORIA           COMMENT 'Categoria del producto segun catalogo interno',
    PRECIO_RAW          COMMENT 'Precio tal como aparece en la pagina, sin procesar',
    PRECIO_MIN_USD      COMMENT 'Objeto JSON con precio minimo en USD',
    PRECIO_MAX_USD      COMMENT 'Objeto JSON con precio maximo en USD',
    MONEDA              COMMENT 'Codigo de moneda del precio',
    MOQ_CANTIDAD        COMMENT 'Cantidad minima de pedido en valor numerico',
    MOQ_UNIDAD          COMMENT 'Unidad de medida de la cantidad minima de pedido',
    CAS                 COMMENT 'Numero CAS del compuesto quimico',
    FORMULA             COMMENT 'Formula quimica del compuesto',
    EINECS              COMMENT 'Numero EINECS del compuesto',
    GRADO               COMMENT 'Grado de calidad del compuesto (ej. Superior Grade)',
    APARIENCIA          COMMENT 'Apariencia fisica del compuesto (ej. Solid)',
    ID_PROVEEDOR        COMMENT 'Identificador unico del proveedor en made-in-china.com',
    PROVEEDOR           COMMENT 'Nombre del proveedor tal como aparece en la fuente',
    URL_IMAGEN          COMMENT 'URL de la imagen principal del producto',
    FECHA_SCRAPING      COMMENT 'Fecha en que se realizo el scraping del producto',
    FUENTE              COMMENT 'Identificador del scraper que origino la fila (made_in_china)',
    FECHA_CONSULTA      COMMENT 'Fecha en que se realizo la extraccion del dato'
) COMMENT='Vista de proveedores y precios de quimicos industriales scrapeados de made-in-china.com. Fuente: PRD_STG.GNM.SRC_MADEINCHINA_PROV_HIST'
as
SELECT
    UPPER(ID_PRODUCTO)                  AS ID_PRODUCTO,
    UPPER(TX_SKU)                       AS SKU,
    URL_PRODUCTO,
    UPPER(NM_PRODUCTO_CLEAN)            AS NOMBRE_PRODUCTO,
    UPPER(NM_PRODUCTO_ORIGINAL)         AS NOMBRE_PRODUCTO_RAW,
    UPPER(TX_TIPO)                      AS TIPO,
    UPPER(TX_CATEGORIA_MIC)             AS CATEGORIA,
    TX_PRECIO_RAW                       AS PRECIO_RAW,
    DS_PRECIO_MIN_USD                   AS PRECIO_MIN_USD,
    DS_PRECIO_MAX_USD                   AS PRECIO_MAX_USD,
    UPPER(TX_MONEDA)                    AS MONEDA,
    NU_MOQ_CANTIDAD                     AS MOQ_CANTIDAD,
    UPPER(TX_MOQ_UNIDAD)                AS MOQ_UNIDAD,
    UPPER(TX_CAS)                       AS CAS,
    UPPER(TX_FORMULA)                   AS FORMULA,
    UPPER(TX_EINECS)                    AS EINECS,
    UPPER(TX_GRADO)                     AS GRADO,
    UPPER(TX_APARIENCIA)                AS APARIENCIA,
    UPPER(ID_PROVEEDOR)                 AS ID_PROVEEDOR,
    UPPER(NM_PROVEEDOR_RAW)             AS PROVEEDOR,
    URL_IMAGEN,
    DT_SCRAPING                         AS FECHA_SCRAPING,
    FT_FUENTE                           AS FUENTE,
    CREATED_AT::DATE                    AS FECHA_CONSULTA
FROM PRD_STG.GNM.SRC_MADEINCHINA_PROV_HIST;

GRANT SELECT ON PRD_CNS_SHD.DATA_GNM.VW_MADEINCHINA_PROV_HIST TO ROLE CORTEX_ANALYST_ROLE;
GRANT SELECT ON PRD_CNS_SHD.DATA_GNM.VW_MADEINCHINA_PROV_HIST TO ROLE ANALYST_MX_ROLE;


-- ---------------------------------------------------------------------------
-- 5. VW_OLIVEYOUNG_NEWARRIVALS
--    Fuente: PRD_STG.GNM.SRC_OLIVEYOUNG_NEWARRIVALS
--    Nuevos lanzamientos de Olive Young Global (Stage 2 enriquecido)
-- ---------------------------------------------------------------------------
create or replace view PRD_CNS_SHD.DATA_GNM.VW_OLIVEYOUNG_NEWARRIVALS(
    ID_PRODUCTO         COMMENT 'Identificador unico del producto en Olive Young Global (prdt_no)',
    URL_PRODUCTO        COMMENT 'URL del detalle del producto en Olive Young',
    NOMBRE_PRODUCTO     COMMENT 'Nombre del producto en ingles',
    NOMBRE_PRODUCTO_KR  COMMENT 'Nombre del producto en coreano',
    URL_IMAGEN          COMMENT 'URL de la imagen principal del producto',
    ID_MARCA            COMMENT 'Identificador unico de la marca en Olive Young',
    MARCA               COMMENT 'Nombre de la marca en ingles',
    URL_MARCA           COMMENT 'URL del perfil de la marca en Olive Young',
    URL_IMAGEN_MARCA    COMMENT 'URL de la imagen o logo de la marca',
    PRECIO_VENTA        COMMENT 'Precio de venta en USD',
    PRECIO_NORMAL       COMMENT 'Precio normal sin descuento en USD',
    DESCUENTO           COMMENT 'Porcentaje de descuento aplicado',
    CATEGORIA           COMMENT 'Categoria hoja del producto',
    RATING              COMMENT 'Calificacion promedio del producto',
    RESENAS             COMMENT 'Cantidad de resenas del producto',
    DESCRIPCION         COMMENT 'Descripcion editorial del producto (why we love it)',
    MODO_USO            COMMENT 'Instrucciones de uso del producto',
    FLAG_NUEVO          COMMENT 'Badge New en Olive Young',
    FLAG_BEST           COMMENT 'Badge Best en Olive Young',
    FLAG_REGALO         COMMENT 'Incluye regalo con compra',
    CORNER              COMMENT 'Nombre del corner o coleccion editorial donde aparece el producto',
    FECHA_SCRAPING      COMMENT 'Fecha del scraping YYYY-MM-DD',
    FUENTE              COMMENT 'Identificador del scraper (olive_young_new_arrivals)',
    FECHA_CONSULTA      COMMENT 'Fecha en que se realizo la extraccion del dato'
) COMMENT='Vista de nuevos lanzamientos de Olive Young Global con detalle enriquecido (Stage 2). Fuente: PRD_STG.GNM.SRC_OLIVEYOUNG_NEWARRIVALS'
as
SELECT
    UPPER(TX_PRDT_NO)                   AS ID_PRODUCTO,
    URL_PRODUCTO,
    UPPER(NM_PRODUCTO_EN)               AS NOMBRE_PRODUCTO,
    NM_PRODUCTO_KR                      AS NOMBRE_PRODUCTO_KR,
    URL_IMAGEN,
    UPPER(TX_BRAND_NO)                  AS ID_MARCA,
    UPPER(NM_MARCA_EN)                  AS MARCA,
    URL_MARCA,
    URL_IMAGEN_MARCA,
    TX_PRECIO_VENTA                     AS PRECIO_VENTA,
    TX_PRECIO_NORMAL                    AS PRECIO_NORMAL,
    TX_DESCUENTO                        AS DESCUENTO,
    UPPER(NM_CATEGORIA)                 AS CATEGORIA,
    NU_RATING                           AS RATING,
    NU_RESENAS                          AS RESENAS,
    UPPER(TX_DESCRIPCION)               AS DESCRIPCION,
    UPPER(TX_MODO_USO)                  AS MODO_USO,
    FL_NEW                              AS FLAG_NUEVO,
    FL_BEST                             AS FLAG_BEST,
    FL_REGALO                           AS FLAG_REGALO,
    UPPER(NM_CORNER)                    AS CORNER,
    DT_SCRAPING                         AS FECHA_SCRAPING,
    FT_FUENTE                           AS FUENTE,
    CREATED_AT::DATE                    AS FECHA_CONSULTA
FROM PRD_STG.GNM.SRC_OLIVEYOUNG_NEWARRIVALS;

GRANT SELECT ON PRD_CNS_SHD.DATA_GNM.VW_OLIVEYOUNG_NEWARRIVALS TO ROLE CORTEX_ANALYST_ROLE;
GRANT SELECT ON PRD_CNS_SHD.DATA_GNM.VW_OLIVEYOUNG_NEWARRIVALS TO ROLE ANALYST_MX_ROLE;


-- ---------------------------------------------------------------------------
-- 6. VW_COSME_RANKING_NEWARRIVALS
--    Fuente: PRD_STG.GNM.SRC_COSME_RANKING_NEWARRIVALS
--    Calendario de nuevos lanzamientos de @cosme (Stage 3 enriquecido)
-- ---------------------------------------------------------------------------
create or replace view PRD_CNS_SHD.DATA_GNM.VW_COSME_RANKING_NEWARRIVALS(
    ID_PRODUCTO             COMMENT 'Identificador unico del producto en @cosme',
    NOMBRE_PRODUCTO         COMMENT 'Nombre del producto',
    URL_PRODUCTO            COMMENT 'URL del producto en @cosme',
    MARCA                   COMMENT 'Nombre de la marca',
    URL_MARCA               COMMENT 'URL del perfil de la marca en @cosme',
    DT_LANZAMIENTO          COMMENT 'Fecha oficial de lanzamiento del producto (YYYY-MM-DD)',
    URL_TIENDA              COMMENT 'URL de compra en @cosme',
    DESCRIPCION             COMMENT 'Descripcion del producto en japones',
    MODO_USO                COMMENT 'Instrucciones de uso del producto',
    FABRICANTE              COMMENT 'Nombre del fabricante del producto',
    URL_FABRICANTE          COMMENT 'URL del perfil del fabricante en @cosme',
    CATEGORIA_FULL          COMMENT 'Jerarquia completa de la categoria en texto (A > B > C)',
    RATING                  COMMENT 'Calificacion promedio del producto en @cosme',
    PUNTOS                  COMMENT 'Puntaje del producto en @cosme',
    RESENAS                 COMMENT 'Cantidad de resenas de usuarias',
    FOTOS                   COMMENT 'Cantidad de fotos de usuarias',
    QA                      COMMENT 'Cantidad de preguntas y respuestas',
    LIKES                   COMMENT 'Cantidad de likes en la comunidad',
    HAVES                   COMMENT 'Cantidad de usuarias que tienen el producto',
    FECHA_SCRAPING          COMMENT 'Fecha y hora del scraping ISO 8601',
    FUENTE                  COMMENT 'Identificador del scraper (cosme-new-arrivals)',
    FECHA_CONSULTA          COMMENT 'Fecha en que se realizo la extraccion del dato'
) COMMENT='Vista del calendario de nuevos lanzamientos de @cosme con detalle enriquecido (Stage 3). Fuente: PRD_STG.GNM.SRC_COSME_RANKING_NEWARRIVALS'
as
SELECT
    UPPER(ID_PRODUCTO)                  AS ID_PRODUCTO,
    UPPER(NM_PRODUCTO)                  AS NOMBRE_PRODUCTO,
    URL_PRODUCTO,
    UPPER(NM_MARCA)                     AS MARCA,
    URL_MARCA,
    DT_LANZAMIENTO,
    URL_TIENDA,
    UPPER(TX_DESCRIPCION)               AS DESCRIPCION,
    UPPER(TX_MODO_USO)                  AS MODO_USO,
    UPPER(NM_FABRICANTE)                AS FABRICANTE,
    URL_FABRICANTE,
    UPPER(TX_CATEGORIA_FULL)            AS CATEGORIA_FULL,
    NU_RATING                           AS RATING,
    NU_PUNTOS                           AS PUNTOS,
    NU_RESENAS                          AS RESENAS,
    NU_FOTOS                            AS FOTOS,
    NU_QA                               AS QA,
    NU_LIKES                            AS LIKES,
    NU_HAVES                            AS HAVES,
    DT_SCRAPING                         AS FECHA_SCRAPING,
    FT_FUENTE                           AS FUENTE,
    CREATED_AT::DATE                    AS FECHA_CONSULTA
FROM PRD_STG.GNM.SRC_COSME_RANKING_NEWARRIVALS;

GRANT SELECT ON PRD_CNS_SHD.DATA_GNM.VW_COSME_RANKING_NEWARRIVALS TO ROLE CORTEX_ANALYST_ROLE;
GRANT SELECT ON PRD_CNS_SHD.DATA_GNM.VW_COSME_RANKING_NEWARRIVALS TO ROLE ANALYST_MX_ROLE;


-- ---------------------------------------------------------------------------
-- ---------------------------------------------------------------------------
-- 7. VW_COSME_RANKING_HIST  [YA EXISTE — creada por Ángel 2026-04-29]
-- ---------------------------------------------------------------------------
-- Creator Angel
-- PRD_CNS_SHD.DATA_GNM.VW_COSME_RANKING_HIST source

create or replace view PRD_CNS_SHD.DATA_GNM.VW_COSME_RANKING_HIST(
	RANKING COMMENT 'Posicion en el ranking semanal de @cosme (1-100)',
	RANK_CAMBIO COMMENT 'Indicador de movimiento en el ranking (UP, DOWN, HOT, NEW, STAY)',
	ID_PRODUCTO COMMENT 'Identificador unico del producto en @cosme',
	NOMBRE_PRODUCTO COMMENT 'Nombre del producto en japones',
	URL_IMG_PRINCIPAL COMMENT 'URL de la imagen principal del producto',
	MARCA COMMENT 'Nombre de la marca en japones',
	URL_MARCA COMMENT 'URL del perfil de la marca en @cosme',
	NOMBRE_CATEGORIA COMMENT 'Nombre de la categoria del producto en japones',
	URL_CATEGORIA COMMENT 'URL de la categoria en @cosme',
	PRECIO_YEN COMMENT 'Precio numerico del producto en yenes japoneses',
	TALLA COMMENT 'Tamano o presentacion del producto (ej. ml, g)',
	FLAG_PRECIO_ABIERTO COMMENT 'Indicador de precio abierto (sin precio fijo de venta)',
	FLAG_INCLUYE_IVA COMMENT 'Indicador si el precio incluye impuesto al consumo (IVA japones)',
	RATING COMMENT 'Calificacion promedio del producto en @cosme (escala 0-7)',
	RESENIAS COMMENT 'Numero total de resenas del producto',
	FECHA_LANZAMIENTO COMMENT 'Fecha de lanzamiento del producto en texto',
	FLAG_BEST_COSME COMMENT 'Indicador de premio Best Cosme Award',
	ES_PRODUCTO_NUEVO COMMENT 'Indicador de producto nuevo en el ranking',
	DESCRIPCION COMMENT 'Descripcion del producto en japones',
	INGREDIENTES COMMENT 'Lista de ingredientes del producto',
	DS_IMAGENES COMMENT 'Array JSON con URLs de imagenes adicionales del producto',
	URL_TIENDA COMMENT 'URL de la pagina del producto en @cosme',
	DT_PERIODO_INICIO COMMENT 'Fecha de inicio del periodo semanal del ranking',
	DT_PERIODO_FIN COMMENT 'Fecha de fin del periodo semanal del ranking',
	FUENTE COMMENT 'Identificador de la fuente de datos (cosme_ranking_products)',
	FECHA_CONSULTA COMMENT 'Fecha en que se realizo la consulta/extraccion del dato'
) COMMENT='Vista de ranking semanal de productos de belleza @cosme (plataforma japonesa). Top 100 por periodo semanal con precios en yenes, ratings, categorias. Fuente: PRD_STG.GNM.SRC_COSME_RANKING_HIST'
 as
SELECT
    NU_RANK                             AS RANKING,
    UPPER(TX_RANK_CAMBIO)               AS RANK_CAMBIO,
    UPPER(ID_PRODUCTO)                  AS ID_PRODUCTO,
    UPPER(NM_PRODUCTO)                  AS NOMBRE_PRODUCTO,
    URL_IMG_PRINCIPAL,
    UPPER(NM_MARCA)                     AS MARCA,
    URL_MARCA,
    UPPER(NM_CATEGORIA)                 AS NOMBRE_CATEGORIA,
    URL_CATEGORIA,
    NU_PRECIO_YEN                       AS PRECIO_YEN,
    UPPER(TX_TALLA)                     AS TALLA,
    FL_PRECIO_ABIERTO                   AS FLAG_PRECIO_ABIERTO,
    FL_INCLUYE_IVA                      AS FLAG_INCLUYE_IVA,
    NU_RATING                           AS RATING,
    NU_RESENAS                          AS RESENIAS,
    UPPER(TX_FECHA_LANZAMIENTO)         AS FECHA_LANZAMIENTO,
    FL_BEST_COSME                       AS FLAG_BEST_COSME,
    FL_NUEVO                            AS ES_PRODUCTO_NUEVO,
    UPPER(TX_DESCRIPCION)               AS DESCRIPCION,
    UPPER(TX_INGREDIENTES)              AS INGREDIENTES,
    DS_IMAGENES,
    URL_TIENDA,
    DT_PERIODO_INICIO,
    DT_PERIODO_FIN,
    FT_FUENTE                           AS FUENTE,
    CREATED_AT::DATE                    AS FECHA_CONSULTA
FROM PRD_STG.GNM.SRC_COSME_RANKING_HIST;

-- ---------------------------------------------------------------------------
-- 8. VW_COSMETIC_DESIGN_ARTICULOS  [YA EXISTE — creada por Ángel 2026-04-29]
-- ---------------------------------------------------------------------------
-- Creator: Angel
-- PRD_CNS_SHD.DATA_GNM.VW_COSMETIC_DESIGN_ARTICULOS source

create or replace view PRD_CNS_SHD.DATA_GNM.VW_COSMETIC_DESIGN_ARTICULOS(
	TITULO COMMENT 'Titulo del articulo tal como aparece en la publicacion',
	URL_ARTICULO COMMENT 'URL canonica del articulo en cosmeticdesign.com',
	FECHA_PUBLICACION COMMENT 'Fecha de publicacion del articulo',
	RESUMEN COMMENT 'Resumen o bajada del articulo',
	CONTENIDO COMMENT 'Contenido completo del articulo (vacio si requiere suscripcion)',
	FLAG_PAYWALL COMMENT 'Indica si el articulo requiere suscripcion de pago para acceder al contenido completo',
	URL_IMAGEN COMMENT 'URL de la imagen principal del articulo',
	PIE_IMAGEN COMMENT 'Pie de foto o leyenda de la imagen principal',
	TEMAS COMMENT 'Temas y etiquetas editoriales del articulo como array JSON',
	FUENTE COMMENT 'Identificador de la fuente de datos (cosmetics_design)',
	FECHA_CONSULTA COMMENT 'Fecha en que se realizo la extraccion del articulo'
) COMMENT='Vista de articulos publicados en Cosmetic Design / NutraIngredients. Contiene noticias y analisis de la industria de belleza, cuidado personal y nutricion. Fuente: PRD_STG.GNM.SRC_COSMETICDESIGN_ART_HIST'
 as
SELECT
    UPPER(TX_TITULO)                    AS TITULO,
    URL_ARTICULO,
    DT_PUBLICACION::DATE                AS FECHA_PUBLICACION,
    UPPER(TX_RESUMEN)                   AS RESUMEN,
    UPPER(TX_CONTENIDO)                 AS CONTENIDO,
    FL_PAYWALL                          AS FLAG_PAYWALL,
    URL_IMAGEN,
    UPPER(TX_PIE_IMAGEN)                AS PIE_IMAGEN,
    DS_TEMAS                            AS TEMAS,
    UPPER(FT_FUENTE)                    AS FUENTE,
    CREATED_AT::DATE                    AS FECHA_CONSULTA
FROM PRD_STG.GNM.SRC_COSMETICDESIGN_ART_HIST;

-- =============================================================================
-- Permisos de lectura sobre cada vista (PRD_CNS_SHD.DATA_GNM)
-- Ejecutar con STREAMLIT_DEVELOPER (owner del schema DATA_GNM)
-- =============================================================================

GRANT SELECT ON PRD_CNS_SHD.DATA_GNM.VW_OLIVEYOUNG_RANK_HIST TO ROLE CORTEX_ANALYST_ROLE;
GRANT SELECT ON PRD_CNS_SHD.DATA_GNM.VW_OLIVEYOUNG_RANK_HIST TO ROLE ANALYST_MX_ROLE;
GRANT SELECT ON PRD_CNS_SHD.DATA_GNM.VW_OLIVEYOUNG_RANK_HIST TO ROLE DEVELOPER_ROLE;

GRANT SELECT ON PRD_CNS_SHD.DATA_GNM.VW_ALIBABA_PROV_HIST TO ROLE CORTEX_ANALYST_ROLE;
GRANT SELECT ON PRD_CNS_SHD.DATA_GNM.VW_ALIBABA_PROV_HIST TO ROLE ANALYST_MX_ROLE;
GRANT SELECT ON PRD_CNS_SHD.DATA_GNM.VW_ALIBABA_PROV_HIST TO ROLE DEVELOPER_ROLE;

GRANT SELECT ON PRD_CNS_SHD.DATA_GNM.VW_INDIAMART_PROV_HIST TO ROLE CORTEX_ANALYST_ROLE;
GRANT SELECT ON PRD_CNS_SHD.DATA_GNM.VW_INDIAMART_PROV_HIST TO ROLE ANALYST_MX_ROLE;
GRANT SELECT ON PRD_CNS_SHD.DATA_GNM.VW_INDIAMART_PROV_HIST TO ROLE DEVELOPER_ROLE;

GRANT SELECT ON PRD_CNS_SHD.DATA_GNM.VW_MADEINCHINA_PROV_HIST TO ROLE CORTEX_ANALYST_ROLE;
GRANT SELECT ON PRD_CNS_SHD.DATA_GNM.VW_MADEINCHINA_PROV_HIST TO ROLE ANALYST_MX_ROLE;
GRANT SELECT ON PRD_CNS_SHD.DATA_GNM.VW_MADEINCHINA_PROV_HIST TO ROLE DEVELOPER_ROLE;

GRANT SELECT ON PRD_CNS_SHD.DATA_GNM.VW_OLIVEYOUNG_NEWARRIVALS TO ROLE CORTEX_ANALYST_ROLE;
GRANT SELECT ON PRD_CNS_SHD.DATA_GNM.VW_OLIVEYOUNG_NEWARRIVALS TO ROLE ANALYST_MX_ROLE;
GRANT SELECT ON PRD_CNS_SHD.DATA_GNM.VW_OLIVEYOUNG_NEWARRIVALS TO ROLE DEVELOPER_ROLE;

GRANT SELECT ON PRD_CNS_SHD.DATA_GNM.VW_COSME_RANKING_NEWARRIVALS TO ROLE CORTEX_ANALYST_ROLE;
GRANT SELECT ON PRD_CNS_SHD.DATA_GNM.VW_COSME_RANKING_NEWARRIVALS TO ROLE ANALYST_MX_ROLE;
GRANT SELECT ON PRD_CNS_SHD.DATA_GNM.VW_COSME_RANKING_NEWARRIVALS TO ROLE DEVELOPER_ROLE;

GRANT SELECT ON PRD_CNS_SHD.DATA_GNM.VW_COSME_RANKING_HIST TO ROLE CORTEX_ANALYST_ROLE;
GRANT SELECT ON PRD_CNS_SHD.DATA_GNM.VW_COSME_RANKING_HIST TO ROLE ANALYST_MX_ROLE;
GRANT SELECT ON PRD_CNS_SHD.DATA_GNM.VW_COSME_RANKING_HIST TO ROLE DEVELOPER_ROLE;

GRANT SELECT ON PRD_CNS_SHD.DATA_GNM.VW_COSMETIC_DESIGN_ARTICULOS TO ROLE CORTEX_ANALYST_ROLE;
GRANT SELECT ON PRD_CNS_SHD.DATA_GNM.VW_COSMETIC_DESIGN_ARTICULOS TO ROLE ANALYST_MX_ROLE;
GRANT SELECT ON PRD_CNS_SHD.DATA_GNM.VW_COSMETIC_DESIGN_ARTICULOS TO ROLE DEVELOPER_ROLE;

GRANT SELECT ON FUTURE VIEWS IN SCHEMA PRD_CNS_SHD.DATA_GNM TO ROLE CORTEX_ANALYST_ROLE;
GRANT SELECT ON FUTURE VIEWS IN SCHEMA PRD_CNS_SHD.DATA_GNM TO ROLE ANALYST_MX_ROLE;
GRANT SELECT ON FUTURE VIEWS IN SCHEMA PRD_CNS_SHD.DATA_GNM TO ROLE DEVELOPER_ROLE;