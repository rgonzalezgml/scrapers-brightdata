# Cost, Governance & Security — Snowflake GLI

---

## Warehouse Sizing

| Escenario | Tamaño |
|-----------|--------|
| Query exploratoria, < 500K filas | XS |
| ETL rutinario, < 5M filas | S |
| Reload diario completo, 5M–50M filas | M |
| Backfill histórico, > 50M filas | L |
| Analytics complejas con muchos JOINs | L o XL |

**Regla:** Empezar pequeño, verificar spillage, escalar si hay remote spill recurrente.

---

## Budgets (alertas por gasto)

```sql
CREATE BUDGET ETL_BUDGET
    CREDIT_QUOTA = 500
    NOTIFY_AT_PERCENTAGE = (75, 90, 100);
ALTER BUDGET ETL_BUDGET ADD WAREHOUSE WH_ETL;
```

---

## Resource Monitors (suspensión automática)

```sql
CREATE OR REPLACE RESOURCE MONITOR MON_MENSUAL
    CREDIT_QUOTA = 1000
    FREQUENCY = MONTHLY
    START_TIMESTAMP = IMMEDIATELY
    TRIGGERS
        ON 75 PERCENT DO NOTIFY
        ON 90 PERCENT DO NOTIFY
        ON 100 PERCENT DO SUSPEND;
ALTER WAREHOUSE WH_ETL SET RESOURCE_MONITOR = MON_MENSUAL;
```

---

## Query Cost Attribution

```sql
SELECT USER_NAME, WAREHOUSE_NAME,
       SUM(CREDITS_USED_CLOUD_SERVICES) AS CLOUD_CREDITS
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE START_TIME >= DATEADD('month', -1, CURRENT_TIMESTAMP)
GROUP BY ALL
ORDER BY CLOUD_CREDITS DESC;
```

---

## Masking Policies (PII)

```sql
CREATE OR REPLACE MASKING POLICY DEV_CNS_MX.GNM_CF.MSK_EMAIL
AS (VAL STRING) RETURNS STRING ->
    CASE
        WHEN CURRENT_ROLE() IN ('ROLE_PRD_CNS_READ_PII') THEN VAL
        ELSE REGEXP_REPLACE(VAL, '(.+)@(.+)', '***@***')
    END;

ALTER TABLE DEV_STG.VENTAS.CTE_CLIENTE
    MODIFY COLUMN EMAIL SET MASKING POLICY DEV_CNS_MX.GNM_CF.MSK_EMAIL;
```

---

## Network Rules y Secrets

```sql
-- Egress rule para API externa
CREATE OR REPLACE NETWORK RULE DEV_LND._SRV_MEX.WMT_NETWORK_RULE
    TYPE = HOST_PORT  MODE = EGRESS
    VALUE_LIST = ('developer.api.us.walmart.com');

-- Secret para credenciales (nunca hardcodear en DDL)
CREATE OR REPLACE SECRET DEV_LND._SRV_MEX.API_SECRET
    TYPE = GENERIC_STRING
    SECRET_STRING = '{"clientId": "REEMPLAZAR", "clientSecret": "REEMPLAZAR"}';
GRANT READ ON SECRET DEV_LND._SRV_MEX.API_SECRET TO ROLE ROLE_ETL;
```

---

## Roles GLI

Nomenclatura: `ROLE_{ENV}_{CAPA}_{TIPO}`

```sql
-- Roles de servicio (ETL/SPs)
-- ROLE_PRD_LND_SERVICE   -- SPs y ETL sobre LND en producción
-- ROLE_PRD_STG_SERVICE   -- SPs y ETL sobre STG
-- ROLE_PRD_CNS_READ      -- Lectura de datos de consumo
-- ROLE_DEV_ALL_ADMIN     -- Admin de DEV para el equipo

-- Ejemplo: crear y asignar permisos mínimos
CREATE ROLE IF NOT EXISTS ROLE_PRD_CNS_READ;
GRANT USAGE ON DATABASE PRD_CNS_MX TO ROLE ROLE_PRD_CNS_READ;
GRANT USAGE ON ALL SCHEMAS IN DATABASE PRD_CNS_MX TO ROLE ROLE_PRD_CNS_READ;
GRANT SELECT ON ALL TABLES IN DATABASE PRD_CNS_MX TO ROLE ROLE_PRD_CNS_READ;
GRANT SELECT ON FUTURE TABLES IN DATABASE PRD_CNS_MX TO ROLE ROLE_PRD_CNS_READ;
```

**IMPORTANTE:** wrench/Claude NUNCA crea ni modifica roles, usuarios ni resource monitors sin aprobación DBA.

---

## Snowflake CLI (snow)

```bash
snow snowpark deploy --prune         # Desplegar objetos Snowpark
snow streamlit deploy --prune        # Desplegar Streamlit app
snow sql -q "CALL DEV_STG.VENTAS.SP_LOAD_VTA_SELLOUT('AIRFLOW_WMS', 'FULL')"
snow sql -f ddl/deploy_all.sql --connection PRD
snow notebook deploy mi_notebook.ipynb
```
