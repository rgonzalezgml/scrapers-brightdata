---
name: gli-snowflake-connect
description: >
  Conecta a Snowflake GLI y verifica resultados de jobs/pruebas QA directamente
  en BD, sin depender del endpoint HTTP. Agnóstico al proyecto: configura las
  tablas objetivo via env vars. Incluye credenciales GLI preconfiguradas en
  reference/.env. Úsala para obtener evidencia canónica de resultados y
  actualizar test_cases.md.
---

# Skill: gli-snowflake-connect

Conexión directa a Snowflake GLI para verificación QA. La fuente de verdad es
siempre la base de datos, no lo que devuelve el endpoint HTTP.

Las tablas objetivo se configuran por env vars → la misma skill funciona para
cualquier módulo/proyecto que siga el patrón `HIST` + `RESULT_HIST`.

---

## Estructura

```
gli-snowflake-connect/
├── SKILL.md
├── reference/
│   └── .env          ← credenciales GLI + tablas objetivo (no commitear)
└── scripts/
    └── connector.py
```

---

## Configuración

### reference/.env

Todas las variables de conexión y las tablas objetivo viven aquí.
El script las carga automáticamente — no hace falta `server/.env` del proyecto.

| Variable | Descripción |
|----------|-------------|
| `SNOWFLAKE_USER` | Usuario GLI (ej: `RGONZALEZA`) |
| `SNOWFLAKE_PASSWORD` | Contraseña |
| `SNOWFLAKE_ACCOUNT` | Cuenta Snowflake (ej: `qob68501-genommalab`) |
| `SNOWFLAKE_WAREHOUSE` | Warehouse (ej: `GENOMMA`) |
| `SNOWFLAKE_DATABASE` | Base de datos (ej: `DEV_STG`) |
| `SNOWFLAKE_SCHEMA` | Schema (ej: `GNM_CT`) |
| `SNOWFLAKE_ROLE` | Rol (ej: `STREAMLIT_DEVELOPER`) |
| `SNOWFLAKE_HIST_TABLE` | Tabla de jobs/historia (fully-qualified) |
| `SNOWFLAKE_RESULT_TABLE` | Tabla de resultados por fila (fully-qualified) |

**Prerequisitos:**
```bash
pip install snowflake-connector-python python-dotenv --break-system-packages
```

---

## Uso del script

```bash
# Job más reciente del usuario en .env (env por defecto: reference/.env)
python .agents/skills/gli-snowflake-connect/scripts/connector.py

# Con ALTA_ID específico
python .agents/skills/gli-snowflake-connect/scripts/connector.py --job-id <UUID>

# Asociando a un caso de prueba (muestra evidencia y ofrece actualizar test_cases.md)
python .agents/skills/gli-snowflake-connect/scripts/connector.py --tc TC-ONB-026

# Combinado + ruta a test_cases.md explícita
python .agents/skills/gli-snowflake-connect/scripts/connector.py \
  --job-id <UUID> \
  --tc TC-ONB-008 \
  --test-cases docs/qa/onboarding/test_cases.md

# Con .env de otro proyecto
python .agents/skills/gli-snowflake-connect/scripts/connector.py \
  --env /ruta/otro-proyecto/server/.env \
  --tc TC-XXX-001
```

### Parámetros

| Parámetro | Default | Descripción |
|-----------|---------|-------------|
| `--job-id` | último job del usuario | UUID del job a inspeccionar |
| `--tc` | — | ID del caso de prueba (ej: `TC-ONB-026`) |
| `--test-cases` | — | Ruta a `test_cases.md`. Si se omite, no se ofrece actualizar. |
| `--env` | `reference/.env` (del skill) | Ruta al archivo `.env` |

---

## Tablas de referencia

### Tabla HIST — jobs

Columnas clave: `ALTA_ID` (PK), `STATUS` (`queued/running/finished/failed`),
`METRIC`, `SOURCE`, `CREATED_BY`, `RECEIVED`, `INSERTED`, `FAILED`,
`ERROR_MESSAGE`, `CREATED_AT`, `FINISHED_AT`.

### Tabla RESULT_HIST — resultados por fila

Columnas clave: `RESULT_ID` (PK), `ALTA_ID` (FK), `ROW_SEQ`, `STATUS`
(`INSERTED/FAILED/SKIPPED`), `ENTITY_ID`, `IDENTIFIER`, `CODE`, `MESSAGE`, `META`.

---

## Queries manuales de referencia

```sql
-- Job más reciente del usuario
SELECT ALTA_ID, STATUS, METRIC, SOURCE, RECEIVED, INSERTED, FAILED,
       ERROR_MESSAGE, CREATED_AT, FINISHED_AT
FROM {SNOWFLAKE_HIST_TABLE}
WHERE CREATED_BY = 'RGONZALEZA'
ORDER BY CREATED_AT DESC LIMIT 1;

-- Resultados fallidos de un job
SELECT ROW_SEQ, STATUS, CODE, MESSAGE, IDENTIFIER
FROM {SNOWFLAKE_RESULT_TABLE}
WHERE ALTA_ID = '<UUID>' AND STATUS = 'FAILED'
ORDER BY ROW_SEQ;

-- Jobs con mezcla INSERTED + FAILED (validar parciales)
SELECT ALTA_ID, STATUS, RECEIVED, INSERTED, FAILED, CREATED_AT
FROM {SNOWFLAKE_HIST_TABLE}
WHERE CREATED_BY = 'RGONZALEZA' AND INSERTED > 0 AND FAILED > 0
ORDER BY CREATED_AT DESC LIMIT 5;

-- Buscar por código de error
SELECT h.ALTA_ID, h.CREATED_AT, r.ROW_SEQ, r.CODE, r.MESSAGE
FROM {SNOWFLAKE_HIST_TABLE} h
JOIN {SNOWFLAKE_RESULT_TABLE} r ON r.ALTA_ID = h.ALTA_ID
WHERE h.CREATED_BY = 'RGONZALEZA'
  AND r.CODE = 'TIPO_PRESENTACION_VALUE_NOT_FOUND'
ORDER BY h.CREATED_AT DESC LIMIT 10;
```

---

## Cómo actualizar test_cases.md

Si `--tc` y `--test-cases` están presentes, el script ofrece actualizar la fila
automáticamente con evidencia extraída de BD.

| Columna | Qué escribir |
|---------|-------------|
| **Resultado real** | `BD (fecha): job finished, INSERTED=N, FAILED=N. Códigos: X. ALTA_ID: uuid.` |
| **Estado** | `APROBADO` si BD confirma el esperado. `FALLIDO` si difiere. |

**Reglas:**
1. Verificar el `ALTA_ID` en BD antes de marcar `APROBADO`. Nunca por lo que respondió el endpoint.
2. `STATUS=failed` en el job (error técnico) → caso `FALLIDO` aunque el endpoint devolviera 200.
3. `CODE` y `MESSAGE` de la tabla RESULT son la evidencia canónica para errores por fila.
4. Usar `Edit` del agente para editar solo la fila afectada. Nunca reescribir todo el archivo.
