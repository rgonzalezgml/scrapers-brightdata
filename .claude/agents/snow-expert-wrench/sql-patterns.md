# SQL Patterns — Snowflake GLI

---

## Micro-Partition Pruning (crítico para performance)

```sql
-- BIEN: operar directamente sobre la columna — activa pruning
WHERE FECHA_VENTA >= DATEADD('day', -30, CURRENT_DATE)
WHERE FECHA_VENTA BETWEEN '2025-01-01' AND '2025-03-31'
WHERE STATUS = 'CERRADO'

-- MAL: función sobre columna bloquea pruning completamente
WHERE YEAR(FECHA_VENTA) = 2025             -- BAD
WHERE TO_DATE(FECHA_VENTA) >= '2025-01-01' -- BAD
WHERE UPPER(STATUS) = 'CERRADO'            -- BAD
```

---

## QUALIFY para deduplicación (más eficiente que subquery)

```sql
-- BIEN
SELECT *
FROM DEV_LND.VENTAS.VTA_SELLOUT_FLE
QUALIFY ROW_NUMBER() OVER (PARTITION BY ID_REGISTRO ORDER BY ETL_LOAD_TS DESC) = 1;

-- MAL: subquery más lenta
SELECT * FROM (
    SELECT *, ROW_NUMBER() OVER (...) AS rn FROM DEV_LND.VENTAS.VTA_SELLOUT_FLE
) WHERE rn = 1;
```

---

## JOINs optimizados

```sql
-- Filtrar antes del JOIN usando CTEs
WITH VENTAS_RECIENTES AS (
    SELECT PEDIDO_ID, COD_CLIENTE, MTO_TOTAL
    FROM DEV_STG.VENTAS.VTA_PEDIDO
    WHERE FECHA_PEDIDO >= DATEADD('day', -30, CURRENT_DATE)
)
SELECT v.PEDIDO_ID, c.NOM_CLIENTE, v.MTO_TOTAL
FROM VENTAS_RECIENTES v
JOIN DEV_STG.VENTAS.CTE_CLIENTE c ON v.COD_CLIENTE = c.COD_CLIENTE;

-- La tabla grande va a la IZQUIERDA (Snowflake construye hash table del lado derecho)
FROM TABLA_GRANDE_FACTS f
JOIN TABLA_PEQUENA_DIM d ON f.DIM_ID = d.DIM_ID;
```

---

## Clustering Keys

```sql
-- Para tablas grandes filtradas frecuentemente por fecha/status
ALTER TABLE DEV_STG.VENTAS.VTA_PEDIDO CLUSTER BY (FECHA_PEDIDO, STATUS);

-- Verificar profundidad de clustering
SELECT SYSTEM$CLUSTERING_INFORMATION('DEV_STG.VENTAS.VTA_PEDIDO', '(FECHA_PEDIDO, STATUS)');
-- depth_histogram concentrado en 1-4 = buen clustering
```

**Cuándo NO usar clustering:**
- Tablas < 1M filas
- Tablas con alta tasa de UPDATE (costo de re-clustering)
- Tablas que nunca se filtran por las columnas candidatas

---

## Result Cache

Snowflake cachea resultados 24h. **Misma query + mismos datos = costo cero.**

```sql
-- Esta query cachea:
SELECT COUNT(*) FROM DEV_STG.VENTAS.VTA_PEDIDO WHERE FECHA_PEDIDO = CURRENT_DATE - 1;

-- Esta query NUNCA cachea (CURRENT_TIMESTAMP cambia):
SELECT COUNT(*) FROM DEV_STG.VENTAS.VTA_PEDIDO WHERE ETL_LOAD_TS > CURRENT_TIMESTAMP() - INTERVAL '1 hour';
```

---

## Profiling — Queries costosas

```sql
SELECT
    QUERY_ID,
    QUERY_TEXT,
    TOTAL_ELAPSED_TIME / 1000   AS SECONDS,
    BYTES_SCANNED / 1e9         AS GB_SCANNED,
    PARTITIONS_SCANNED,
    PARTITIONS_TOTAL,
    ROUND(PARTITIONS_SCANNED / NULLIF(PARTITIONS_TOTAL,0) * 100, 1) AS PCT_SCANNED
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE EXECUTION_STATUS = 'SUCCESS'
  AND START_TIME >= DATEADD('day', -7, CURRENT_TIMESTAMP())
ORDER BY TOTAL_ELAPSED_TIME DESC
LIMIT 20;
```

---

## Spillage (warehouse demasiado pequeño)

```sql
SELECT WAREHOUSE_NAME,
       AVG(BYTES_SPILLED_TO_LOCAL_STORAGE)  AS AVG_LOCAL_SPILL,
       AVG(BYTES_SPILLED_TO_REMOTE_STORAGE) AS AVG_REMOTE_SPILL
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE WAREHOUSE_NAME = 'WH_ETL'
  AND START_TIME >= DATEADD('day', -7, CURRENT_TIMESTAMP())
GROUP BY 1;
-- Si remote spillage > 0 regularmente → escalar warehouse
```

---

## Data Lineage

```sql
SELECT *
FROM SNOWFLAKE.ACCOUNT_USAGE.OBJECT_DEPENDENCIES
WHERE REFERENCED_OBJECT_NAME = 'VTA_SELLOUT'
ORDER BY REFERENCING_OBJECT_NAME;
```

---

## Errores Comunes

| Error | Solución |
|-------|---------|
| `WHERE YEAR(col) = 2025` | `WHERE col BETWEEN '2025-01-01' AND '2025-12-31'` |
| `LIKE '%keyword%'` en tablas grandes | Full-text search o columna materializada |
| Nombres DB/schema hardcodeados en SPs | Variables de sesión o parámetros |
| `INSERT INTO ... SELECT` para upserts | Usar `MERGE` |
| Conversiones de tipo implícitas en JOIN | `CAST` explícito o tipos coincidentes |
| Sin manejo de errores en SPs | Siempre `EXCEPTION WHEN OTHER THEN` |
| `SELECT *` en SPs de producción | Lista explícita de columnas |
| Credenciales hardcodeadas en DDL | Usar `SECRET` de Snowflake |
| Warehouse siempre activo | `AUTO_SUSPEND = 60` en todos los warehouses |
| Campo sin `COMMENT` | Todo campo debe tener `COMMENT` con definición semántica |
| `Cannot overload PROCEDURE` | Agregar `DROP PROCEDURE IF EXISTS ...(tipos_anteriores)` antes del CREATE |
| `DEFAULT` en parámetros LANGUAGE SQL | No soportado — usar `COALESCE(P_PARAM, 'default')` en el body |
| `IF condition THEN` sin paréntesis | LANGUAGE SQL requiere `IF (condition) THEN` |
