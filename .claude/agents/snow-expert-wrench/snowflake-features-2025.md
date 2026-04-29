# Snowflake Features 2025
# Fuente: Snowflake Release Notes + Docs oficiales

---

## 1. CORTEX AI — IA nativa en SQL

### Funciones AI (GA Nov 2025)
Modelos disponibles: Claude (Anthropic), Mistral, Meta Llama, Google, Snowflake Arctic.

```sql
-- Clasificación de texto
SELECT AI_CLASSIFY(DES_COMENTARIO, ['POSITIVO','NEGATIVO','NEUTRO']) AS SENTIMIENTO
FROM DEV_STG.VENTAS.VTA_FEEDBACK;

-- Completado LLM
SELECT AI_COMPLETE('snowflake-arctic', 'Resume: ' || DES_COMENTARIO) AS RESUMEN
FROM DEV_STG.VENTAS.VTA_FEEDBACK;

-- Embeddings para búsqueda semántica
SELECT AI_EMBED('snowflake-arctic-embed-m', DES_PRODUCTO) AS VECTOR_EMBEDDING
FROM DEV_STG.PROD.PROD_CATALOGO;

-- Sentimiento clásico (-1 a 1)
SELECT SNOWFLAKE.CORTEX.SENTIMENT(DES_COMENTARIO) AS SCORE
FROM DEV_STG.VENTAS.VTA_FEEDBACK;

-- Traducción
SELECT SNOWFLAKE.CORTEX.TRANSLATE(DES_PRODUCTO, 'es', 'en') AS DES_EN
FROM DEV_STG.PROD.PROD_CATALOGO;
```

### Cortex Analyst — NL2SQL
```sql
CREATE OR REPLACE SEMANTIC VIEW DEV_CNS_MX.VENTAS.SV_PEDIDOS
  TABLES (
    DEV_STG.VENTAS.VTA_PEDIDO AS PEDIDO,
    DEV_STG.VENTAS.VTA_PEDIDO_DETALLE AS DETALLE
  )
  RELATIONSHIPS (DETALLE.ID_PEDIDO_FK = PEDIDO.PEDIDO_ID)
  METRICS (
    METRIC TOTAL_VENTAS AS SUM(DETALLE.MONTO_TOTAL_VENTA),
    METRIC CNT_PEDIDOS   AS COUNT(DISTINCT PEDIDO.PEDIDO_ID)
  );
```

### Cortex Search — Búsqueda semántica
```sql
CREATE OR REPLACE CORTEX SEARCH SERVICE DEV_CNS_MX.VENTAS.CS_FEEDBACK
    ON DES_COMENTARIO
    WAREHOUSE = WH_ETL
    TARGET_LAG = '1 hour'
    AS SELECT PEDIDO_ID, DES_COMENTARIO FROM DEV_STG.VENTAS.VTA_FEEDBACK;
```

### AI en Dynamic Tables (GA Sep 2025)
```sql
CREATE OR REPLACE DYNAMIC TABLE DEV_CNS_MX.VENTAS.VTA_FEEDBACK_CLASIFICADO
    TARGET_LAG = '1 hour'  WAREHOUSE = WH_ETL
AS
SELECT PEDIDO_ID, DES_COMENTARIO,
    AI_CLASSIFY(DES_COMENTARIO, ['POSITIVO','NEGATIVO','NEUTRO']) AS SENTIMIENTO
FROM DEV_STG.VENTAS.VTA_FEEDBACK;
```

---

## 2. DYNAMIC TABLES

| Criterio | Dynamic Tables | Stored Procedures |
|----------|---------------|-------------------|
| Lógica simple (SELECT/JOIN/AGG) | Preferido | Posible |
| Lógica compleja (loops, validaciones) | No soportado | Preferido |
| Refresh automático declarativo | Si | No (requiere Task) |
| AI Functions (Sep 2025) | Si | Si |

```sql
CREATE OR REPLACE DYNAMIC TABLE DEV_CNS_MX.VENTAS.VTA_PEDIDO_RESUMEN
    TARGET_LAG = '1 hour'  WAREHOUSE = WH_ETL
AS
SELECT DATE_TRUNC('day', FECHA_PEDIDO) AS DIA, COD_PAIS,
       COUNT(*) AS CNT_PEDIDOS, SUM(MTO_TOTAL) AS MTO_TOTAL
FROM DEV_STG.VENTAS.VTA_PEDIDO
GROUP BY ALL;
```

---

## 3. SERVERLESS TASKS + DAG

```sql
-- Task serverless — billing por segundo real (sin mínimo de 60 seg)
CREATE OR REPLACE TASK GNM_CF.TSK_LOAD_VTA_DIARIO
    SCHEDULE = 'USING CRON 0 6 * * * America/Mexico_City'
    USER_TASK_MANAGED_INITIAL_WAREHOUSE_SIZE = 'SMALL'
AS CALL DEV_STG.VENTAS.SP_LOAD_VTA_SELLOUT('INCREMENTAL');

-- DAG encadenado LND → STG → CNS
CREATE OR REPLACE TASK GNM_CF.TSK_LOAD_STG
    AFTER GNM_CF.TSK_LOAD_LND
    USER_TASK_MANAGED_INITIAL_WAREHOUSE_SIZE = 'SMALL'
AS CALL DEV_STG.VENTAS.SP_PROCESS_VENTAS('FULL');

-- Activar DAG desde la raíz hacia las hojas
ALTER TASK GNM_CF.TSK_LOAD_CNS RESUME;
ALTER TASK GNM_CF.TSK_LOAD_STG RESUME;
ALTER TASK GNM_CF.TSK_LOAD_LND RESUME;

-- Task condicional — solo cuando hay datos nuevos en el stream
CREATE OR REPLACE TASK DEV_STG.GNM_CF.TSK_PROCESS_PEDIDOS
    WAREHOUSE = WH_ETL
    WHEN SYSTEM$STREAM_HAS_DATA('DEV_LND.VENTAS.STR_VTA_PEDIDO')
    SCHEDULE = '1 MINUTE'
AS
MERGE INTO DEV_STG.VENTAS.VTA_PEDIDO tgt
USING (SELECT * FROM DEV_LND.VENTAS.STR_VTA_PEDIDO WHERE METADATA$ACTION = 'INSERT') src
    ON tgt.PEDIDO_ID = src.PEDIDO_ID
WHEN NOT MATCHED THEN INSERT VALUES (src.PEDIDO_ID, src.STATUS, src.FECHA_PEDIDO, CURRENT_TIMESTAMP());
```

---

## 4. STREAMS (CDC)

```sql
CREATE OR REPLACE STREAM GNM_CF.STR_LND_PEDIDO ON TABLE DEV_LND.VENTAS.VTA_PEDIDO_FLE;
-- Consumir solo inserts
SELECT * FROM GNM_CF.STR_LND_PEDIDO WHERE METADATA$ACTION = 'INSERT';
```

---

## 5. ICEBERG TABLES

```sql
-- Tabla Iceberg gestionada por Snowflake
CREATE OR REPLACE ICEBERG TABLE DEV_LND.LOG.LOG_EVENTO_FLE (
    EVENTO_ID        VARCHAR(50)         COMMENT 'Identificador único del evento',
    TIMESTAMP_EVENTO TIMESTAMP_NTZ       COMMENT 'Timestamp del evento en la fuente (UTC)',
    PAYLOAD          VARIANT             COMMENT 'Payload completo del evento en formato JSON',
    ETL_LOAD_TS      TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP() COMMENT 'Timestamp de carga ETL'
)
    CATALOG        = 'SNOWFLAKE'
    EXTERNAL_VOLUME = 'S3_LANDING_VOL'
    BASE_LOCATION  = 'log/evento/';
```

---

## 6. TIME TRAVEL

```sql
-- Consultar estado hace 1 hora
SELECT * FROM DEV_STG.VENTAS.VTA_PEDIDO AT (OFFSET => -3600);
-- Restaurar registros eliminados accidentalmente
INSERT INTO DEV_STG.VENTAS.VTA_PEDIDO
SELECT * FROM DEV_STG.VENTAS.VTA_PEDIDO BEFORE (STATEMENT => '<query_id>');
```

---

## 7. NUEVAS FUNCIONES SQL 2024-2025

```sql
-- GROUP BY ALL
SELECT REGION, PRODUCTO, SUM(MTO_VENTA) FROM DEV_STG.VENTAS.VTA_PEDIDO GROUP BY ALL;

-- SELECT * EXCLUDE / RENAME
SELECT * EXCLUDE (COL_SENSIBLE, PASSWORD_HASH) FROM DEV_STG.VENTAS.CTE_CLIENTE;
SELECT * RENAME (NOMBRE_COMPLETO AS NOM_CLIENTE) FROM DEV_STG.VENTAS.CTE_CLIENTE;

-- MERGE con WHEN NOT MATCHED BY SOURCE — sync completo eliminando huérfanos
MERGE INTO DEV_STG.VENTAS.VTA_PEDIDO AS tgt
USING DEV_LND.VENTAS.VTA_PEDIDO_FLE AS src ON tgt.PEDIDO_ID = src.PEDIDO_ID
WHEN MATCHED THEN UPDATE SET tgt.STATUS = src.STATUS
WHEN NOT MATCHED BY TARGET THEN INSERT VALUES (src.PEDIDO_ID, src.STATUS, src.FECHA_PEDIDO)
WHEN NOT MATCHED BY SOURCE THEN DELETE;

-- ASOF JOIN — Time Series (precio vigente en cada transacción)
SELECT t.FECHA_TXN, t.MTO_VENTA, p.PRECIO_LISTA
FROM DEV_STG.VENTAS.VTA_TRANSACCION t
ASOF JOIN DEV_STG.PROD.PROD_PRECIO p
    MATCH_CONDITION (t.FECHA_TXN >= p.FECHA_VIGENCIA)
    ON t.PROD_COD = p.PROD_COD;

-- RESULT_SCAN — reusar resultado cacheado sin costo
SELECT COUNT(*) FROM DEV_CNS_MX.VENTAS.VW_VTA_PEDIDOS;
SELECT * FROM TABLE(RESULT_SCAN(LAST_QUERY_ID())) WHERE REGION = 'NORTE';
```

---

## 8. QUERY ACCELERATION SERVICE (QAS)

```sql
ALTER WAREHOUSE WH_ANALYTICS SET
    ENABLE_QUERY_ACCELERATION = TRUE
    QUERY_ACCELERATION_MAX_SCALE_FACTOR = 4;

-- Verificar uso de QAS
SELECT QUERY_ID, QUERY_TEXT, QUERY_ACCELERATION_BYTES_SCANNED
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE QUERY_ACCELERATION_BYTES_SCANNED > 0
ORDER BY QUERY_ACCELERATION_BYTES_SCANNED DESC LIMIT 10;
```

---

## 9. SNOWPARK PANDAS + ML

```python
import snowflake.snowpark.modin.pandas as spd

# Pandas en Snowflake sin extraer datos
df = spd.read_snowflake("DEV_STG.VENTAS.VTA_PEDIDO")
df["MTO_BRUTO"] = df["MTO_SUBTOTAL"] + df["MTO_IMPUESTO"]
df.to_snowflake("DEV_CNS_MX.VENTAS.VTA_PEDIDO_ENRIQUECIDO", if_exists="replace")

# Vectorized UDF
from snowflake.snowpark.functions import pandas_udf
from snowflake.snowpark.types import DoubleType

@pandas_udf(return_type=DoubleType(), input_types=[DoubleType(), DoubleType()])
def FN_CALCULATE_MARGEN(mto_venta, mto_costo):
    return (mto_venta - mto_costo) / mto_venta

session.udf.register(FN_CALCULATE_MARGEN, name="DEV_STG.VENTAS.FN_CALCULATE_MARGEN", replace=True)
```

---

## Resumen — Cuándo usar cada tecnología

| Necesidad | Tecnología |
|-----------|-----------|
| Clasificar/analizar texto en SQL | `AI_CLASSIFY`, `AI_COMPLETE`, `SNOWFLAKE.CORTEX.*` |
| Búsqueda semántica | Cortex Search |
| Preguntas en lenguaje natural sobre datos | Cortex Analyst + Semantic Views |
| CNS layer lógica simple | Dynamic Tables |
| CNS layer lógica compleja | Stored Procedures + Serverless Task |
| Sync completo eliminando huérfanos | `MERGE ... WHEN NOT MATCHED BY SOURCE THEN DELETE` |
| Datos open-format | Iceberg Tables |
| Time series joins | `ASOF JOIN` |
| Pandas en Snowflake sin extraer | Snowpark pandas (Modin) |
| Control de costos | Budgets + Resource Monitors + Serverless Tasks |
