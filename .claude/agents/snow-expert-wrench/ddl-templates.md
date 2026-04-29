# DDL Templates — GLI Snowflake

Todos los templates siguen GLI v1.1.0: MAYÚSCULAS, COMMENT obligatorio en cada columna y tabla.

---

## Tabla LND (Landing Layer)

```sql
CREATE OR REPLACE TABLE DEV_LND.VENTAS.VTA_PEDIDO_FLE (
    -- Columnas fuente (VARCHAR para todo en LND — sin transformaciones)
    ID_PEDIDO       VARCHAR(16777216)   COMMENT 'Identificador único del pedido — valor raw de la fuente',
    COD_CLIENTE     VARCHAR(16777216)   COMMENT 'Código del cliente — valor raw de la fuente',
    FECHA_PEDIDO    VARCHAR(16777216)   COMMENT 'Fecha del pedido en formato original de la fuente',
    MONTO_TOTAL     VARCHAR(16777216)   COMMENT 'Monto total del pedido — valor raw sin tipado',
    -- Columna incremental (CDC via Delta Sharing o Databricks)
    _CHANGE_TYPE    VARCHAR(30)         COMMENT 'CDF: insert | update_postimage | delete. NULL en carga FULL.',
    -- Metadata ETL
    ETL_LOAD_TS     TIMESTAMP_NTZ   DEFAULT CURRENT_TIMESTAMP()  COMMENT 'Timestamp de carga ETL',
    ETL_SOURCE_FILE VARCHAR(500)                                  COMMENT 'Ruta o nombre del archivo fuente',
    ETL_BATCH_ID    VARCHAR(100)                                  COMMENT 'Identificador del batch de carga'
)
COMMENT = 'Landing table VTA_PEDIDO desde archivos FLE. Raw data, sin transformaciones.';
```

---

## Tabla STG (Staging Layer)

```sql
CREATE OR REPLACE TABLE DEV_STG.VENTAS.VTA_PEDIDO (
    -- Surrogate key
    PEDIDO_SK       NUMBER AUTOINCREMENT PRIMARY KEY           COMMENT 'Llave surrogada autoincremental',
    -- Business key
    ID_PEDIDO       VARCHAR(50)     NOT NULL                   COMMENT 'Identificador único del pedido (llave de negocio)',
    -- Columnas de negocio (tipadas)
    COD_CLIENTE     VARCHAR(50)                                COMMENT 'Código del cliente',
    FECHA_PEDIDO    DATE                                       COMMENT 'Fecha de emisión del pedido',
    MONTO_TOTAL     NUMBER(18,4)                               COMMENT 'Monto total del pedido en moneda local',
    -- Auditoría estándar
    CREATED_AT      TIMESTAMP_NTZ   DEFAULT CURRENT_TIMESTAMP()  COMMENT 'Fecha y hora de creación del registro',
    CREATED_USR     VARCHAR(100)                                 COMMENT 'Usuario que creó el registro',
    UPDATED_AT      TIMESTAMP_NTZ                                COMMENT 'Fecha y hora de última modificación',
    UPDATED_USR     VARCHAR(100)                                 COMMENT 'Usuario que modificó el registro',
    -- Metadata ETL
    ETL_LOAD_TS     TIMESTAMP_NTZ   DEFAULT CURRENT_TIMESTAMP()  COMMENT 'Timestamp de carga ETL',
    ETL_UPDATE_TS   TIMESTAMP_NTZ                                COMMENT 'Timestamp de última actualización ETL',
    ETL_SOURCE      VARCHAR(200)                                 COMMENT 'Sistema o archivo fuente',
    IS_ACTIVE       BOOLEAN         DEFAULT TRUE                 COMMENT 'Flag de borrado lógico (FALSE = eliminado)',
    UNIQUE (ID_PEDIDO)
)
CLUSTER BY (FECHA_PEDIDO)
COMMENT = 'Staging VTA_PEDIDO. Limpio y tipado desde LND.';
```

---

## Tabla CNS (Consumo / Agregado)

```sql
CREATE OR REPLACE TABLE DEV_CNS_MX.VENTAS.VTA_PEDIDO_AGG (
    -- Grano
    FECHA_DIA       DATE            NOT NULL    COMMENT 'Fecha del día (grano de la agregación)',
    COD_PAIS        VARCHAR(10)     NOT NULL    COMMENT 'Código de país ISO (MX, BR, CO, etc.)',
    DES_BU          VARCHAR(100)    NOT NULL    COMMENT 'Nombre de la unidad de negocio',
    -- Métricas
    CNT_PEDIDOS     NUMBER(12,0)    DEFAULT 0   COMMENT 'Cantidad de pedidos en el día',
    MTO_TOTAL_MXN   NUMBER(18,4)    DEFAULT 0   COMMENT 'Monto total de pedidos en pesos mexicanos',
    -- Auditoría
    ETL_LOAD_TS     TIMESTAMP_NTZ   DEFAULT CURRENT_TIMESTAMP()  COMMENT 'Timestamp de carga ETL',
    PRIMARY KEY (FECHA_DIA, COD_PAIS, DES_BU)
)
COMMENT = 'Consumo agregado VTA_PEDIDO por día/país/BU. Fuente para BI.';
```

---

## Tabla de Auditoría ETL

```sql
CREATE OR REPLACE TABLE DEV_STG.GNM_CF.ETL_AUDIT_LOG (
    LOG_ID          NUMBER AUTOINCREMENT PRIMARY KEY           COMMENT 'Identificador único del registro de auditoría',
    ENTITY_NAME     VARCHAR(100)    NOT NULL                   COMMENT 'Nombre de la entidad o tabla procesada',
    LAYER           VARCHAR(10)     NOT NULL                   COMMENT 'Capa procesada: LND, STG o CNS',
    MODE            VARCHAR(20)     NOT NULL                   COMMENT 'Modo de carga: FULL o INCREMENTAL',
    STATUS          VARCHAR(20)     NOT NULL                   COMMENT 'Estado de ejecución: OK, ERROR o RUNNING',
    ROWS_PROCESSED  NUMBER          DEFAULT 0                  COMMENT 'Número de filas procesadas',
    START_TS        TIMESTAMP_NTZ   DEFAULT CURRENT_TIMESTAMP() COMMENT 'Timestamp de inicio',
    END_TS          TIMESTAMP_NTZ                              COMMENT 'Timestamp de fin',
    DURATION_SECS   NUMBER                                     COMMENT 'Duración total en segundos',
    ERROR_MESSAGE   VARCHAR(5000)                              COMMENT 'Mensaje de error en caso de fallo',
    ENVIRONMENT     VARCHAR(10)     NOT NULL                   COMMENT 'Ambiente de ejecución: DEV o PRD'
)
COMMENT = 'Tabla de auditoría ETL. Registra todas las ejecuciones de SPs y pipelines.';
```

---

## Vista CNS

```sql
CREATE OR REPLACE VIEW DEV_CNS_MX.VENTAS.VW_VTA_PEDIDO AS
SELECT
    PEDIDO_SK,
    ID_PEDIDO,
    COD_CLIENTE,
    FECHA_PEDIDO,
    MONTO_TOTAL,
    ETL_LOAD_TS
FROM DEV_STG.VENTAS.VTA_PEDIDO
WHERE IS_ACTIVE = TRUE
COMMENT = 'Vista pública VTA_PEDIDO. Solo registros activos. Fuente para BI.';
```

---

## Template: Stored Procedure LND → STG (LANGUAGE SQL)

```sql
-- DROP del overload anterior si existe (evitar ambiguedad)
DROP PROCEDURE IF EXISTS DEV_STG.VENTAS.SP_LOAD_VTA_SELLOUT(VARCHAR);

CREATE OR REPLACE PROCEDURE DEV_STG.VENTAS.SP_LOAD_VTA_SELLOUT(
    P_USUARIO     VARCHAR,
    P_MODO_CARGA  VARCHAR   -- 'FULL' | 'INCREMENTAL'
)
RETURNS VARIANT
LANGUAGE SQL
EXECUTE AS CALLER
AS
$$
DECLARE
    v_ins   INTEGER DEFAULT 0;
    v_eli   INTEGER DEFAULT 0;
    v_start TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP();
    v_res   VARIANT;
BEGIN
    -- 1. Validar modo
    IF (COALESCE(P_MODO_CARGA, 'FULL') NOT IN ('FULL', 'INCREMENTAL')) THEN
        RETURN OBJECT_CONSTRUCT('status', 'ERROR', 'message', 'P_MODO_CARGA invalido: ' || P_MODO_CARGA);
    END IF;

    -- 2. Soft-delete: solo en FULL (INCREMENTAL lo maneja el DAG via _CHANGE_TYPE)
    IF (COALESCE(P_MODO_CARGA, 'FULL') = 'FULL') THEN
        EXECUTE IMMEDIATE '
            UPDATE DEV_STG.VENTAS.VTA_SELLOUT t
            SET t.IS_ACTIVE   = FALSE,
                t.UPDATED_AT  = CURRENT_TIMESTAMP(),
                t.UPDATED_USR = ''' || P_USUARIO || '''
            WHERE NOT EXISTS (
                SELECT 1 FROM DEV_LND.VENTAS.VTA_SELLOUT_FLE s
                WHERE s.ID_REGISTRO = t.ID_REGISTRO
            ) AND t.IS_ACTIVE = TRUE';
        v_eli := SQLROWCOUNT;
    END IF;

    -- 3. MERGE idempotente
    MERGE INTO DEV_STG.VENTAS.VTA_SELLOUT AS tgt
    USING (
        SELECT
            ID_REGISTRO,
            TRIM(COD_CLIENTE)                           AS COD_CLIENTE,
            TRY_TO_DATE(FECHA_VENTA, 'YYYY-MM-DD')      AS FECHA_VENTA,
            TRY_CAST(CANTIDAD_VENDIDA AS NUMBER(12,3))  AS CANTIDAD_VENDIDA,
            TRY_CAST(PRECIO_UNITARIO AS NUMBER(18,4))   AS PRECIO_UNITARIO
        FROM DEV_LND.VENTAS.VTA_SELLOUT_FLE
    ) AS src ON tgt.ID_REGISTRO = src.ID_REGISTRO
    WHEN MATCHED THEN UPDATE SET
        tgt.CANTIDAD_VENDIDA = src.CANTIDAD_VENDIDA,
        tgt.PRECIO_UNITARIO  = src.PRECIO_UNITARIO,
        tgt.UPDATED_AT       = CURRENT_TIMESTAMP(),
        tgt.UPDATED_USR      = P_USUARIO
    WHEN NOT MATCHED THEN INSERT (
        ID_REGISTRO, COD_CLIENTE, FECHA_VENTA, CANTIDAD_VENDIDA, PRECIO_UNITARIO,
        CREATED_AT, CREATED_USR, IS_ACTIVE
    ) VALUES (
        src.ID_REGISTRO, src.COD_CLIENTE, src.FECHA_VENTA, src.CANTIDAD_VENDIDA, src.PRECIO_UNITARIO,
        CURRENT_TIMESTAMP(), P_USUARIO, TRUE
    );
    v_ins := SQLROWCOUNT;

    v_res := OBJECT_CONSTRUCT(
        'status',     'OK',
        'modo_carga', P_MODO_CARGA,
        'insertados', v_ins,
        'eliminados', v_eli,
        'duracion',   DATEDIFF('second', v_start, CURRENT_TIMESTAMP())
    );
    RETURN v_res;

EXCEPTION
    WHEN OTHER THEN
        RETURN OBJECT_CONSTRUCT('status', 'ERROR', 'code', SQLCODE, 'message', SQLERRM);
END;
$$;
```

---

## Warehouse Sizing

```sql
-- ETL / batch loads
CREATE WAREHOUSE IF NOT EXISTS WH_ETL
    WAREHOUSE_SIZE = 'SMALL'
    AUTO_SUSPEND   = 60
    AUTO_RESUME    = TRUE
    COMMENT        = 'ETL pipeline warehouse';

-- Queries analíticas
CREATE WAREHOUSE IF NOT EXISTS WH_ANALYTICS
    WAREHOUSE_SIZE = 'X-SMALL'
    AUTO_SUSPEND   = 300
    AUTO_RESUME    = TRUE
    COMMENT        = 'Analytics and BI queries';
```
