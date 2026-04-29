---
name: snowflake-json-load
description: >
  Carga de emergencia: inserta un JSON (array de objetos) directamente en
  cualquier tabla Snowflake. Auto-detecta el mapping campo→columna comparando
  contra el schema real (DESCRIBE TABLE). Soporta VARIANT, DATE y TIMESTAMP_NTZ
  sin configuración manual. Usar cuando el middleware falla y hay que cargar
  resultados manualmente.
---

# Skill: snowflake-json-load

Carga de emergencia JSON → Snowflake sin configuración manual.

Conecta, describe la tabla destino, auto-mapea los campos del JSON contra las
columnas reales, convierte tipos (VARIANT, DATE, TIMESTAMP_NTZ, BOOLEAN) y
usa `write_pandas` para insertar en un solo chunk.

---

## Estructura

```
snowflake-json-load/
├── SKILL.md
└── scripts/
    └── load.py
```

---

## Prerequisitos

```bash
pip install "snowflake-connector-python[pandas]" python-dotenv pandas \
    --break-system-packages
```

---

## Uso

### Carga rápida (auto-detect)

```bash
python .agents/skills/snowflake-json-load/scripts/load.py \
  --file bd_scrapers/cosme-ranking-products/results/j_xxx.json \
  --table DEV_STG.GNM_MEX.SRC_COSME_RANKING_HIST \
  --job-id j_xxx
```

### Con mapping explícito

Crea un `mapping.json` con `{"campo_json": "COLUMNA_SNOWFLAKE"}`:

```bash
python .agents/skills/snowflake-json-load/scripts/load.py \
  --file results.json \
  --table DEV_STG.GNM_MEX.MI_TABLA \
  --map mapping.json \
  --job-id j_xxx
```

### Dry-run (ver plan sin insertar)

```bash
python .agents/skills/snowflake-json-load/scripts/load.py \
  --file results.json \
  --table DEV_STG.GNM_MEX.MI_TABLA \
  --dry-run
```

### Overwrite (truncar antes de insertar)

```bash
python .agents/skills/snowflake-json-load/scripts/load.py \
  --file results.json \
  --table DEV_STG.GNM_MEX.MI_TABLA \
  --overwrite
```

---

## Parámetros

| Parámetro     | Default          | Descripción |
|---------------|------------------|-------------|
| `--file`      | (requerido)      | Ruta al JSON (array de objetos) |
| `--table`     | (requerido)      | Tabla destino: `DB.SCHEMA.TABLE` o solo `TABLE` (usa vars del .env) |
| `--map`       | —                | JSON con mapping explícito `{"json_key": "COLUMN_NAME"}` |
| `--job-id`    | —                | Valor para `ID_JOB` (si la columna existe en la tabla) |
| `--role`      | `DEVELOPER_ROLE` | Rol de Snowflake |
| `--env`       | `.env`           | Ruta al `.env` con credenciales |
| `--dry-run`   | false            | Muestra el plan sin insertar |
| `--overwrite` | false            | Trunca la tabla antes de insertar |

---

## Auto-detección de mapping

El script compara cada clave del JSON contra las columnas de la tabla con tres
estrategias (en orden):

1. **Exacto** (case-insensitive): `rank` → `RANK`
2. **Upper + guión→underscore**: `rank_change` → `RANK_CHANGE`
3. **Normalizado** (solo alfanumérico): `product-id` → `PRODUCTID` → `PRODUCTID`

Los campos sin match se reportan como aviso y se ignoran.

## Conversión de tipos

| Tipo Snowflake  | Tratamiento |
|-----------------|-------------|
| `VARIANT`       | dict/list se serializan a JSON string |
| `DATE`          | Intenta `YYYY/M/D`, `YYYY-MM-DD`, `DD/MM/YYYY`, `MM/DD/YYYY` |
| `TIMESTAMP_NTZ` | ISO 8601 con sufijo `Z` o `+HH:MM` |
| `BOOLEAN`       | `true/false/1/0/yes/sí` |

---

## Variables de entorno requeridas (`.env`)

```
SNOWFLAKE_USER=
SNOWFLAKE_PASSWORD=
SNOWFLAKE_ACCOUNT=
SNOWFLAKE_WAREHOUSE=
SNOWFLAKE_DATABASE=   # opcional si --table es DB.SCHEMA.TABLE
SNOWFLAKE_SCHEMA=     # opcional si --table es DB.SCHEMA.TABLE
```
