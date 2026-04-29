-- =============================================================================
-- DDL: Cambios aprobados en DEV_STG.GNM_MEX — 2026-04-29
-- Ejecutar con rol DEVELOPER_ROLE (RGONZALEZA lo tiene asignado)
-- =============================================================================
-- Auditoria previa (estado actual verificado 2026-04-29):
--   SRC_ALIBABA_PROV_HIST       15 cols  — legacy: DS_INPUT, DT_CARGA, ID_JOB  — audit GLI: faltan
--   SRC_INDIAMART_PROV_HIST     31 cols  — legacy: DS_INPUT, DT_CARGA, ID_JOB  — audit GLI: faltan
--   SRC_MADEINCHINA_PROV_HIST   29 cols  — legacy: DS_INPUT, DT_CARGA, ID_JOB  — audit GLI: faltan
--   SRC_OLIVEYOUNG_RANK_HIST    14 cols  — legacy: DS_INPUT, DT_CARGA, ID_JOB  — audit GLI: faltan
--   SRC_COSMETICDESIGN_ART_HIST 13 cols  — legacy: DS_INPUT, DT_CARGA, ID_JOB  — audit GLI: faltan
--   SRC_COSME_RANKING_HIST      35 cols  — legacy: DS_INPUT, ID_JOB  — audit GLI: ya existen
--   SRC_COSME_AWARD_HIST        existe pero no tiene DDL canonical — DROP
-- =============================================================================

USE ROLE DEVELOPER_ROLE;
USE DATABASE DEV_STG;
USE SCHEMA GNM_MEX;


-- ---------------------------------------------------------------------------
-- 1. DROP TABLE — tabla sin DDL canonical
-- ---------------------------------------------------------------------------

DROP TABLE IF EXISTS DEV_STG.GNM_MEX.SRC_COSME_AWARD_HIST;


-- ---------------------------------------------------------------------------
-- 2. DROP columnas legacy
--    Snowflake no soporta DROP COLUMN IF EXISTS — las 3 existen confirmado
-- ---------------------------------------------------------------------------

-- SRC_ALIBABA_PROV_HIST
ALTER TABLE DEV_STG.GNM_MEX.SRC_ALIBABA_PROV_HIST DROP COLUMN DS_INPUT;
ALTER TABLE DEV_STG.GNM_MEX.SRC_ALIBABA_PROV_HIST DROP COLUMN DT_CARGA;
ALTER TABLE DEV_STG.GNM_MEX.SRC_ALIBABA_PROV_HIST DROP COLUMN ID_JOB;

-- SRC_INDIAMART_PROV_HIST
ALTER TABLE DEV_STG.GNM_MEX.SRC_INDIAMART_PROV_HIST DROP COLUMN DS_INPUT;
ALTER TABLE DEV_STG.GNM_MEX.SRC_INDIAMART_PROV_HIST DROP COLUMN DT_CARGA;
ALTER TABLE DEV_STG.GNM_MEX.SRC_INDIAMART_PROV_HIST DROP COLUMN ID_JOB;

-- SRC_MADEINCHINA_PROV_HIST
ALTER TABLE DEV_STG.GNM_MEX.SRC_MADEINCHINA_PROV_HIST DROP COLUMN DS_INPUT;
ALTER TABLE DEV_STG.GNM_MEX.SRC_MADEINCHINA_PROV_HIST DROP COLUMN DT_CARGA;
ALTER TABLE DEV_STG.GNM_MEX.SRC_MADEINCHINA_PROV_HIST DROP COLUMN ID_JOB;

-- SRC_OLIVEYOUNG_RANK_HIST
ALTER TABLE DEV_STG.GNM_MEX.SRC_OLIVEYOUNG_RANK_HIST DROP COLUMN DS_INPUT;
ALTER TABLE DEV_STG.GNM_MEX.SRC_OLIVEYOUNG_RANK_HIST DROP COLUMN DT_CARGA;
ALTER TABLE DEV_STG.GNM_MEX.SRC_OLIVEYOUNG_RANK_HIST DROP COLUMN ID_JOB;

-- SRC_COSMETICDESIGN_ART_HIST
ALTER TABLE DEV_STG.GNM_MEX.SRC_COSMETICDESIGN_ART_HIST DROP COLUMN DS_INPUT;
ALTER TABLE DEV_STG.GNM_MEX.SRC_COSMETICDESIGN_ART_HIST DROP COLUMN DT_CARGA;
ALTER TABLE DEV_STG.GNM_MEX.SRC_COSMETICDESIGN_ART_HIST DROP COLUMN ID_JOB;

-- SRC_COSME_RANKING_HIST (DT_CARGA ya no existe — solo DS_INPUT e ID_JOB)
ALTER TABLE DEV_STG.GNM_MEX.SRC_COSME_RANKING_HIST DROP COLUMN DS_INPUT;
ALTER TABLE DEV_STG.GNM_MEX.SRC_COSME_RANKING_HIST DROP COLUMN ID_JOB;


-- ---------------------------------------------------------------------------
-- 3. ADD columnas de auditoria GLI en 5 tablas
--    (SRC_COSME_RANKING_HIST ya las tiene — omitida)
-- ---------------------------------------------------------------------------

ALTER TABLE DEV_STG.GNM_MEX.SRC_ALIBABA_PROV_HIST
    ADD COLUMN CREATED_AT  TIMESTAMP_NTZ(9) DEFAULT CURRENT_TIMESTAMP() COMMENT 'Fecha y hora de creacion del registro',
    ADD COLUMN UPDATED_AT  TIMESTAMP_NTZ(9) DEFAULT CURRENT_TIMESTAMP() COMMENT 'Fecha y hora de ultima actualizacion del registro',
    ADD COLUMN CREATED_USR VARCHAR(100)     DEFAULT CURRENT_USER()      COMMENT 'Usuario que creo el registro',
    ADD COLUMN UPDATED_USR VARCHAR(100)     DEFAULT CURRENT_USER()      COMMENT 'Usuario que realizo la ultima actualizacion del registro';

ALTER TABLE DEV_STG.GNM_MEX.SRC_INDIAMART_PROV_HIST
    ADD COLUMN CREATED_AT  TIMESTAMP_NTZ(9) DEFAULT CURRENT_TIMESTAMP() COMMENT 'Fecha y hora de creacion del registro',
    ADD COLUMN UPDATED_AT  TIMESTAMP_NTZ(9) DEFAULT CURRENT_TIMESTAMP() COMMENT 'Fecha y hora de ultima actualizacion del registro',
    ADD COLUMN CREATED_USR VARCHAR(100)     DEFAULT CURRENT_USER()      COMMENT 'Usuario que creo el registro',
    ADD COLUMN UPDATED_USR VARCHAR(100)     DEFAULT CURRENT_USER()      COMMENT 'Usuario que realizo la ultima actualizacion del registro';

ALTER TABLE DEV_STG.GNM_MEX.SRC_MADEINCHINA_PROV_HIST
    ADD COLUMN CREATED_AT  TIMESTAMP_NTZ(9) DEFAULT CURRENT_TIMESTAMP() COMMENT 'Fecha y hora de creacion del registro',
    ADD COLUMN UPDATED_AT  TIMESTAMP_NTZ(9) DEFAULT CURRENT_TIMESTAMP() COMMENT 'Fecha y hora de ultima actualizacion del registro',
    ADD COLUMN CREATED_USR VARCHAR(100)     DEFAULT CURRENT_USER()      COMMENT 'Usuario que creo el registro',
    ADD COLUMN UPDATED_USR VARCHAR(100)     DEFAULT CURRENT_USER()      COMMENT 'Usuario que realizo la ultima actualizacion del registro';

ALTER TABLE DEV_STG.GNM_MEX.SRC_OLIVEYOUNG_RANK_HIST
    ADD COLUMN CREATED_AT  TIMESTAMP_NTZ(9) DEFAULT CURRENT_TIMESTAMP() COMMENT 'Fecha y hora de creacion del registro',
    ADD COLUMN UPDATED_AT  TIMESTAMP_NTZ(9) DEFAULT CURRENT_TIMESTAMP() COMMENT 'Fecha y hora de ultima actualizacion del registro',
    ADD COLUMN CREATED_USR VARCHAR(100)     DEFAULT CURRENT_USER()      COMMENT 'Usuario que creo el registro',
    ADD COLUMN UPDATED_USR VARCHAR(100)     DEFAULT CURRENT_USER()      COMMENT 'Usuario que realizo la ultima actualizacion del registro';

ALTER TABLE DEV_STG.GNM_MEX.SRC_COSMETICDESIGN_ART_HIST
    ADD COLUMN CREATED_AT  TIMESTAMP_NTZ(9) DEFAULT CURRENT_TIMESTAMP() COMMENT 'Fecha y hora de creacion del registro',
    ADD COLUMN UPDATED_AT  TIMESTAMP_NTZ(9) DEFAULT CURRENT_TIMESTAMP() COMMENT 'Fecha y hora de ultima actualizacion del registro',
    ADD COLUMN CREATED_USR VARCHAR(100)     DEFAULT CURRENT_USER()      COMMENT 'Usuario que creo el registro',
    ADD COLUMN UPDATED_USR VARCHAR(100)     DEFAULT CURRENT_USER()      COMMENT 'Usuario que realizo la ultima actualizacion del registro';


-- ---------------------------------------------------------------------------
-- 4. ADD 25 columnas faltantes en SRC_COSME_RANKING_HIST
--    (FL_PRECIO_ABIERTO, FL_INCLUYE_IVA, DS_IMAGENES ya existen — omitidas)
-- ---------------------------------------------------------------------------

ALTER TABLE DEV_STG.GNM_MEX.SRC_COSME_RANKING_HIST
    ADD COLUMN NM_PRODUCTO_JP           VARCHAR(16777216)  COMMENT 'Nombre original del producto en japones (product_name_jp)',
    ADD COLUMN URL_PRODUCTO             VARCHAR(16777216)  COMMENT 'URL del producto en cosme.net (cosme.net/products/{id}/)',
    ADD COLUMN NM_MARCA_JP              VARCHAR(16777216)  COMMENT 'Nombre de la marca en japones (brand_name_jp)',
    ADD COLUMN NM_FABRICANTE            VARCHAR(16777216)  COMMENT 'Nombre del fabricante del producto (メーカー)',
    ADD COLUMN URL_FABRICANTE           VARCHAR(16777216)  COMMENT 'URL del perfil del fabricante en cosme.net (manufacturer_url)',
    ADD COLUMN TX_CATEGORIA_FULL        VARCHAR(16777216)  COMMENT 'Jerarquia completa de la categoria en texto (e.g. A > B > C) (category_full)',
    ADD COLUMN DS_CATEGORIA_PATH        VARIANT            COMMENT 'Jerarquia de categorias como array de objetos [{name, url}] (category_path)',
    ADD COLUMN NU_RATING_DETAIL         NUMBER(5,2)        COMMENT 'Calificacion promedio detallada del producto obtenida en Stage 2 (p.average)',
    ADD COLUMN NU_PUNTOS                NUMBER(5,2)        COMMENT 'Puntaje del producto en el ranking de cosme.net (p.point, e.g. 59.1)',
    ADD COLUMN NU_RANK_CATEGORIA        NUMBER(5,0)        COMMENT 'Posicion del producto dentro de su propia categoria (cat_rank)',
    ADD COLUMN NM_CATEGORIA_RANK        VARCHAR(16777216)  COMMENT 'Nombre de la categoria en la que el producto tiene posicion de ranking (cat_rank_name)',
    ADD COLUMN DS_RANKING_EN            VARIANT            COMMENT 'Lista de rankings en los que aparece el producto como array de strings (ranking_in)',
    ADD COLUMN NU_FOTOS                 NUMBER(12,0)       COMMENT 'Cantidad de fotos de usuarias asociadas al producto (photo_count)',
    ADD COLUMN NU_QA                    NUMBER(12,0)       COMMENT 'Cantidad de preguntas y respuestas de la comunidad (qa_count)',
    ADD COLUMN NU_LIKES                 NUMBER(12,0)       COMMENT 'Cantidad de likes del producto en la comunidad',
    ADD COLUMN NU_HAVES                 NUMBER(12,0)       COMMENT 'Cantidad de usuarias que marcaron el producto como que lo tienen (haves)',
    ADD COLUMN TX_MODO_USO              VARCHAR(16777216)  COMMENT 'Instrucciones de uso del producto (使い方) (how_to_use)',
    ADD COLUMN TX_CLASIFICACION         VARCHAR(16777216)  COMMENT 'Clasificacion regulatoria del producto (e.g. Iyakubuhin) (classification)',
    ADD COLUMN TX_JAN_CODE              VARCHAR(16777216)  COMMENT 'Codigo JAN (codigo de barras japones) del producto (jan_code)',
    ADD COLUMN URL_OFICIAL              VARCHAR(16777216)  COMMENT 'URL del sitio oficial del producto o fabricante (oficial_url)',
    ADD COLUMN DS_TIENDAS               VARIANT            COMMENT 'Lista de nombres de tiendas fisicas donde se vende el producto como array (stores)',
    ADD COLUMN DS_PRODUCTOS_RELACIONADOS VARIANT           COMMENT 'Productos relacionados sugeridos por cosme.net como array de objetos [{name, url}] (related_products)',
    ADD COLUMN TX_SOURCE                VARCHAR(100)       COMMENT 'Identificador de la fuente dentro del sitio (e.g. cosme.net/ranking/products) (source)',
    ADD COLUMN TX_PAIS                  VARCHAR(10)        COMMENT 'Codigo de pais ISO-2 del sitio scrapeado (e.g. JP) (country)',
    ADD COLUMN TX_RANKING_POR           VARCHAR(20)        COMMENT 'Criterio de agrupacion del ranking (e.g. product) (ranking_by)';


-- ---------------------------------------------------------------------------
-- 5. DESCRIBE TABLE — validacion post-cambios
-- ---------------------------------------------------------------------------

DESCRIBE TABLE DEV_STG.GNM_MEX.SRC_ALIBABA_PROV_HIST;
DESCRIBE TABLE DEV_STG.GNM_MEX.SRC_INDIAMART_PROV_HIST;
DESCRIBE TABLE DEV_STG.GNM_MEX.SRC_MADEINCHINA_PROV_HIST;
DESCRIBE TABLE DEV_STG.GNM_MEX.SRC_OLIVEYOUNG_RANK_HIST;
DESCRIBE TABLE DEV_STG.GNM_MEX.SRC_COSMETICDESIGN_ART_HIST;
DESCRIBE TABLE DEV_STG.GNM_MEX.SRC_COSME_RANKING_HIST;

-- =============================================================================
-- Conteo esperado post-cambios:
--   SRC_ALIBABA_PROV_HIST        12 cols  (15 - 3 legacy + 4 audit)
--   SRC_INDIAMART_PROV_HIST      32 cols  (31 - 3 legacy + 4 audit)
--   SRC_MADEINCHINA_PROV_HIST    30 cols  (29 - 3 legacy + 4 audit)
--   SRC_OLIVEYOUNG_RANK_HIST     15 cols  (14 - 3 legacy + 4 audit)
--   SRC_COSMETICDESIGN_ART_HIST  14 cols  (13 - 3 legacy + 4 audit)
--   SRC_COSME_RANKING_HIST       58 cols  (35 - 2 legacy + 25 nuevas)
-- =============================================================================
