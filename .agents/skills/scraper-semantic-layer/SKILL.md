---
name: scraper-semantic-layer
description: >
  Etapa de creación de la capa semántica de un scraper en PRD_CNS_SHD.DATA_GNM.
  Usar cuando se pide "crea la vista semántica de X", "crea el YAML de X",
  "agrega X a Cortex Analyst", o cuando un scraper tiene tabla en PRD_STG.GNM
  y todavía no tiene vista ni modelo YAML en gli-sementic/.
  Produce: (1) bloque SQL en vistas.sql con CREATE VIEW + GRANTs, y
  (2) archivo semantic_<name>.yaml en gli-sementic/.
---

# SKILL: scraper-semantic-layer

Etapa de exposición semántica de scrapers BrightData para Cortex Analyst de Genomma Lab.
Cada scraper con tabla en `PRD_STG.GNM` debe tener una vista normalizada en
`PRD_CNS_SHD.DATA_GNM` y un modelo YAML para Cortex Analyst.

Archivos de referencia en `/workspace/gli-sementic/`:
- `SKILL (2) 1.md` — skill GLI interna (convenciones de DTs y vistas de negocio)
- `semantic_cosme_ranking 1.yaml` — ejemplo YAML de referencia
- `vistas.sql` — archivo acumulativo con todas las vistas del proyecto

---

## 1. Cuándo se activa

- Usuario pide "crea la vista/YAML del scraper X".
- Se agrega un scraper nuevo a PRD_STG.GNM y falta su exposición semántica.
- Se modifica el DDL de una tabla fuente y hay que actualizar la vista.
- Se detecta que un YAML referencia columnas crudas (GLI nomenclatura) en lugar de los alias de la vista.

---

## 2. Producto

### 2a. Bloque en `gli-sementic/vistas.sql`

```sql
-- ---------------------------------------------------------------------------
-- N. VW_<NOMBRE>
--    Fuente: PRD_STG.GNM.SRC_<NOMBRE>
--    <Una línea describiendo qué contiene>
-- ---------------------------------------------------------------------------
create or replace view PRD_CNS_SHD.DATA_GNM.VW_<NOMBRE>(
    <COLUMNA_1>  COMMENT '<descripción canónica>',
    ...
    FECHA_CONSULTA  COMMENT 'Fecha en que se realizo la extraccion del dato'
) COMMENT='<Descripción completa de la vista. Fuente: PRD_STG.GNM.SRC_<NOMBRE>>'
as
SELECT
    <mapeo de columnas>
FROM PRD_STG.GNM.SRC_<NOMBRE>;

GRANT SELECT ON PRD_CNS_SHD.DATA_GNM.VW_<NOMBRE> TO ROLE CORTEX_ANALYST_ROLE;
GRANT SELECT ON PRD_CNS_SHD.DATA_GNM.VW_<NOMBRE> TO ROLE ANALYST_MX_ROLE;
```

### 2b. Archivo `gli-sementic/semantic_<nombre>.yaml`

```yaml
name: <Nombre legible del modelo>
description: >
  Descripción del modelo semántico. Incluir IMPORTANTE sobre filtrar
  por fecha máxima si aplica.

tables:
  - name: VW_<NOMBRE>
    description: >
      Descripción de la vista. Granularidad, rango de fechas, conteo de ítems.
    base_table:
      database: PRD_CNS_SHD
      schema: DATA_GNM
      table: VW_<NOMBRE>

    filters:
      - name: ULTIMO_<ENTIDAD>
        synonyms: [...]
        description: >
          Filtro que selecciona solo la fecha de consulta más reciente.
          Aplicar SIEMPRE salvo que el usuario pida histórico.
        expr: FECHA_CONSULTA = (SELECT MAX(FECHA_CONSULTA) FROM PRD_CNS_SHD.DATA_GNM.VW_<NOMBRE>)

    dimensions:
      - name: <COLUMNA>
        synonyms: [<sinónimo_es>, <sinónimo_en>, ...]
        description: <Descripción breve>
        expr: <COLUMNA>
        data_type: VARCHAR | NUMBER | BOOLEAN | DATE | TIMESTAMP_NTZ | FLOAT

    time_dimensions:
      - name: FECHA_CONSULTA
        synonyms: [fecha, fecha extraccion, fecha scraping, dia, date]
        description: Fecha en que se realizo la extraccion del dato
        expr: FECHA_CONSULTA
        data_type: DATE

    measures:
      - name: <METRICA>
        synonyms: [...]
        description: <Descripción>
        expr: <expr o columna>
        data_type: NUMBER | FLOAT | VARCHAR
        default_aggregation: avg | sum | count_distinct | count | min | max
```

---

## 3. Convenciones de vistas SQL

### Transformaciones de columnas

| Tipo de columna | Transformación |
|----------------|---------------|
| Texto (nombres, marcas, descripciones) | `UPPER(columna) AS alias` |
| URLs | Sin `UPPER()` — dejar intactas |
| Precios en texto (TX_PRECIO_*) | Sin `UPPER()` — preservar símbolo de moneda |
| Fechas tipo timestamp | `CREATED_AT::DATE AS FECHA_CONSULTA` |
| Fechas ya tipadas DATE | Alias directo sin cast |
| Booleanos (FL_*) | Alias directo, renombrar a `FLAG_*` |
| Numéricos (NU_*) | Alias directo |
| JSON/Arrays (DS_*) | Alias directo |

### Mapeo de nomenclatura GLI → alias de vista

| Prefijo GLI | Significado | Alias en vista |
|------------|-------------|----------------|
| `NM_` | Nombre | `NOMBRE_*` o nombre semántico |
| `TX_` | Texto libre | `*_RAW`, `DESCRIPCION`, `PRECIO_*`, etc. |
| `NU_` | Numérico | Nombre semántico sin prefijo |
| `FL_` | Flag booleano | `FLAG_*` |
| `FT_FUENTE` | Fuente del scraper | `FUENTE` |
| `DS_` | Descriptor/JSON | Alias descriptivo |
| `DT_` | Fecha | Nombre semántico |
| `ID_` | Identificador | Mantener `ID_*` |
| `URL_` | URL | Mantener `URL_*` |

### Columna FECHA_CONSULTA

**Siempre** la última columna de la vista. Derivada de:
- `CREATED_AT::DATE AS FECHA_CONSULTA` — cuando la fuente tiene CREATED_AT TIMESTAMP
- `DT_SCRAPING AS FECHA_CONSULTA` — si aplica como fecha canónica de extracción

### COMMENT en columnas

**Obligatorio** en cada columna de la vista. Formato: frase descriptiva en español, sin punto final, en minúsculas excepto nombres propios.

```sql
COLUMNA  COMMENT 'descripcion de la columna sin punto final'
```

### COMMENT en vista

**Obligatorio** en el `CREATE OR REPLACE VIEW`. Incluir:
- Qué contiene la vista
- Granularidad
- Fuente: `PRD_STG.GNM.SRC_<NOMBRE>`

### GRANTs obligatorios

Siempre después del `;` del CREATE VIEW:

```sql
GRANT SELECT ON PRD_CNS_SHD.DATA_GNM.VW_<NOMBRE> TO ROLE CORTEX_ANALYST_ROLE;
GRANT SELECT ON PRD_CNS_SHD.DATA_GNM.VW_<NOMBRE> TO ROLE ANALYST_MX_ROLE;
```

---

## 4. Convenciones del YAML semántico

### Filtro por defecto ULTIMO_*

**Obligatorio** en toda vista con granularidad `producto x fecha_consulta`. Nombre: `ULTIMO_RANKING`, `ULTIMO_PRECIO`, `ULTIMO_LANZAMIENTO`, etc. según el contexto del scraper.

El `expr` del filtro siempre usa subquery `SELECT MAX(FECHA_CONSULTA)` sobre la misma vista:

```yaml
expr: FECHA_CONSULTA = (SELECT MAX(FECHA_CONSULTA) FROM PRD_CNS_SHD.DATA_GNM.VW_<NOMBRE>)
```

### Synonyms

- Mínimo 3 sinónimos por campo
- Mezcla español + inglés
- Incluir variantes coloquiales o de negocio (ej. "posicion", "lugar", "rank")
- Usar listas YAML `[...]` o bloque con `-`

### Medidas mínimas recomendadas

| Medida | expr | aggregation |
|--------|------|-------------|
| `TOTAL_PRODUCTOS` | `ID_PRODUCTO` o campo PK | `count_distinct` |
| `TOTAL_MARCAS` | `MARCA` | `count_distinct` |
| `TOTAL_PROVEEDORES` | `PROVEEDOR` o `ID_PROVEEDOR` | `count_distinct` |
| `RATING` (si aplica) | `RATING` | `avg` |
| `RANKING` (si aplica) | `RANKING` | `avg` |

### Campos booleanos

Van como `dimensions`, no como `measures`. `data_type: BOOLEAN`.
Agregar filtros opcionales si tienen uso frecuente (ej. `SOLO_VERIFICADOS`, `SOLO_BADGE_NEW`).

### Campos JSON/Array

Van como `dimensions` con `data_type: VARCHAR`. No agregar como measures.

### URLs

Van como `dimensions` con `data_type: VARCHAR`. No agregar como measures.

---

## 5. Proceso paso a paso

1. **Leer el DDL** de la tabla fuente en `docs/ddl/PRD_STG.GNM.sql` para conocer las columnas reales.
2. **Leer un YAML de referencia** (`gli-sementic/semantic_cosme_ranking 1.yaml`) para calibrar el formato.
3. **Construir la vista SQL**: aplicar transformaciones, COMMENTs, GRANTs.
4. **Agregar el bloque a `vistas.sql`**: siempre al final del bloque de vistas nuevas, antes de los comentarios de vistas existentes.
5. **Construir el YAML semántico**: `name`, `description`, `tables` con `base_table → PRD_CNS_SHD.DATA_GNM`, filtro `ULTIMO_*`, dimensions, time_dimensions, measures.
6. **Guardar el YAML** en `gli-sementic/semantic_<nombre>.yaml`.
7. **Verificar**: que todos los `expr:` en el YAML correspondan a alias de la vista (no a columnas crudas de la tabla fuente).

---

## 6. Checklist antes de reportar completado

- [ ] Vista SQL creada con `UPPER()` en texto, URLs sin modificar
- [ ] Cada columna tiene `COMMENT`
- [ ] Vista tiene `COMMENT` general
- [ ] `CREATED_AT::DATE AS FECHA_CONSULTA` al final de la vista
- [ ] GRANTs a `CORTEX_ANALYST_ROLE` y `ANALYST_MX_ROLE`
- [ ] YAML tiene `base_table` apuntando a `PRD_CNS_SHD.DATA_GNM`
- [ ] YAML tiene filtro `ULTIMO_*` con subquery `MAX(FECHA_CONSULTA)`
- [ ] YAML tiene `FECHA_CONSULTA` en `time_dimensions`
- [ ] Todos los `expr:` del YAML usan alias de la vista, no columnas crudas
- [ ] Cada campo tiene mínimo 3 synonyms (mezcla ES + EN)
- [ ] Medidas mínimas presentes (`TOTAL_PRODUCTOS` + al menos una métrica del dominio)
