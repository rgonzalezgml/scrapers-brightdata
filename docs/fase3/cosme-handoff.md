# Handoff Fase 3 — cosme

> **Destino del trabajo**: `middlewares/cosme/` (este repo).
> **Consumidor**: repo de agentes. Importa este paquete como dependencia y encima coloca `ServiceRegistry`, persistencia (`scraper_runs` en PostgreSQL), cache TTL y declaración de tool al agente.
> **Agente responsable**: `middleware-python`.
>
> **[POST-FACTO 2026-04-23]** Este handoff es **ratificatorio**: el middleware ya
> fue implementado (commit previo, `middlewares/cosme/` con tests pasando), y
> este documento fija por escrito las decisiones que el agente tomó al cerrar
> la Etapa 3 del scraper. La estructura sigue el canónico
> [`cosmetics-design-handoff.md`](./cosmetics-design-handoff.md); cosme es un
> scraper de I+D hermano pero **multi-entidad**, así que las secciones §2, §4,
> §5 divergen del canónico por razones de shape, no de política.

---

## 0. Antes de arrancar (ratificación)

Al momento de abrir el handoff las respuestas ya estaban tomadas — quedan aquí
como confirmación de qué se asumió:

1. **Resource id de BrightData**. Dual-mode, con precedencia v3 > DCA
   (idéntica al canónico). Env vars:
   - `BRIGHTDATA_DATASET_ID_COSME` (formato `gd_...`) — modo v3.
   - `BRIGHTDATA_COLLECTOR_ID_COSME` (formato `c_.../j_...`) — modo DCA legacy.
   Si las dos están seteadas, v3 gana. Ninguna hardcodeada en `config.py` —
   todo vía env (`resolve_mode_and_id()`). El valor concreto lo poblamos al
   primer uso real.
2. **`middlewares/core/` ya existe** (legado de cosmetics-design). cosme **no**
   es POC; reusa `BaseScraperClient`, `Envelope`, `ScraperError` y
   `NORMALIZED_CODES` sin modificar el catálogo base.
3. **Env var `BRIGHTDATA_API_KEY`** — la misma en v3 y DCA.
4. **Nombre del paquete Python**: `middlewares/cosme/` (sin underscore — el
   nombre del scraper JS ya es Python-safe). El scraper JS sigue en
   `scrapers/cosme/` (hyphen no aplica acá).

### Preguntas que sí quedan abiertas al repo de agentes

- Cadencia esperada de corridas (cosme es catálogo cíclico anual, no feed diario
  — ver §8).
- Política de cache TTL sobre `inputs_hash` cuando el único input que cambia es
  `year`.
- ¿Cuenta el `mode: full-refresh` como señal para bypassear cache en el lado
  agents o es puro hint cosmético? Hoy el middleware lo forwarda en
  `envelope.inputs` sin interpretarlo.

---

## 1. Contexto del scraper

- **Nombre**: `cosme` (carpeta JS `scrapers/cosme/` / paquete Python
  `middlewares/cosme/` — ambos sin hyphen, a diferencia de cosmetics-design).
- **Categoría**: I+D (tendencias de belleza Japón, rankings de productos — NO
  precios).
- **Entidades (tres, multi-entidad)**: `product`, `ranking`, `brand`.
  Es la diferencia estructural más importante contra el canónico
  (cosmetics-design es mono-entidad = `article`).
- **Fuente**: `https://www.cosme.net/` (istyle Inc., residencial JP).
  Páginas autoritarias: `/products/{id}/`, `/bestcosme/archive/{year}/{grand|hall|rookie}/`,
  `/bestcosme/archive/{year}/category/{slug}/`, `/brands/{id}/?nt=1`.
- **Spec completo**: `docs/specs/scrapers/cosme.md` — §2 es el schema inmutable
  de `data[]`, §4-§5 entidades, §6-§7 reglas de parsing, §7 límites, §8 output,
  §10-§11 arquitectura Stage 1 browser + Stage 2 HTTP.
- **Implementación JS**: `scrapers/cosme/sc_browser/` + `sc_code/` (ver §8 —
  estado actual: Stage 2 **solo emite `product`**; ranking/brand están en el
  vendor pero no en las versiones `_vN` nuestras todavía).

---

## 2. Contrato público del paquete

### 2.1 `trigger(inputs) -> dict`

```python
async def trigger(inputs: CosmeInputs | dict | None = None) -> dict:
    """
    Returns: {"job_id": str, "eta_seconds": int}
    Raises nunca — errores van por shape {"status": "failed", "error": {...}}.
    """
```

### 2.2 `get_result(job_id) -> dict`

```python
async def get_result(job_id: str) -> dict:
    """
    Returns envelope con shape:
      {"status": "running",  "progress_pct": int}
      {"status": "done",     "data": <Envelope>}
      {"status": "failed",   "error": {"code": str, "message": str, "retriable": bool}}
    """
```

### 2.3 Inputs — `CosmeInputs` (pydantic v2, `extra="forbid"`)

```python
class CosmeInputs(BaseModel):
    year: int | None = None                    # 2000..2100 — award/ranking year
    max_products: int = 1000                   # 1..3000 — hard cap (spec §7)
    max_categories: int = 24                   # 1..30  — slugs a descubrir Stage 1
    category: str | None = None                # substring filter opcional
    include_rankings: bool = True              # drop ranking rows si False
    include_brands: bool = True                # drop brand rows si False
    mode: Literal["incremental", "full-refresh"] = "incremental"
```

Diferencias explícitas contra cosmetics-design:

- **No hay `window_days`**. cosme es catálogo cíclico anual (bestcosme archive
  `{year}/`), no feed temporal. `year` reemplaza a `window_days` con semántica
  totalmente distinta: "qué cosecha de awards crawlear", no "cuánto tiempo atrás".
- **No hay `region_filter`**. La fuente es JP-only.
- Sí hay `include_rankings` / `include_brands`: el consumidor puede pedir solo
  productos para reducir payload, sin que el scraper reconfigure.
- **`max_products` es post-download** (spec §7 lo aplica el middleware sobre
  rows `entity=product`). Ranking y brand son tablas de referencia pequeñas
  y **NO** se recortan.

### 2.4 Envelope normalizado (cuando `status == "done"`)

```python
{
  "source": "cosme",
  "scraped_at": "2026-04-23T15:30:00Z",
  "inputs": { ... echo de inputs efectivos ... },
  "data": [ { "entity": "product"|"ranking"|"brand", ... } ],
  "meta": {
    "rows": 123,
    "emitted": 120,
    "emitted_by_entity": {"product": 100, "ranking": 15, "brand": 5},
    "skipped_by_reason": { "unknown_entity": 1, "max_products_cap": 2, ... },
    "blocked": 4,
    "errors": 0,
    "started_at": "...",
    "ended_at": "..."
  }
}
```

**Lo que diverge del canónico**: `data[]` es **heterogéneo** — cada row lleva
un discriminador `entity` en `{"product", "ranking", "brand"}`. El
consumidor puede filtrar por clave `entity` sin reparsear. El shape de cada
entidad cumple el §2 del spec de cosme:

```json
{
  "product": ["product_id","url","name_raw","brand_id","category_ids",
              "effect_ids","ingredient_tag_ids","rating_avg","review_count",
              "launch_date","regulation_class","variants"],
  "ranking": ["source_type","year","group","category_slug","rank","product_id"],
  "brand":   ["brand_id","name","url","total_products","total_reviews"]
}
```

Estas claves son **inmutables**. Además el scraper emite los extras §4/§5
(`name_clean`, `category_chains`, `maker_id`, `scraper_flags`, etc.) que
pasan por `ConfigDict(extra="allow")` verbatim — el middleware los respeta.

Regla de listas y nulls (spec §8): claves siempre presentes; listas van como
`[]` nunca `null`; escalares ausentes van como `null` explícito.

`meta.emitted_by_entity` es el agregado que permite al consumidor validar de
un vistazo que el run cumple lo que se le pidió (ej. `ranking=0` si el caller
pidió `include_rankings=false`).

### 2.5 Decisión de diseño: multi-entidad en un solo `data[]`

Las alternativas descartadas:

| Opción | Por qué se descartó |
|---|---|
| Tres envelopes separados (`data_products`, `data_rankings`, `data_brands`) | Rompe el contrato cross-scraper uniforme definido en `core/envelope.py` — `data` tiene que ser `list`. |
| Dict anidado `{"products": [...], "rankings": [...], "brands": [...]}` | Misma razón que arriba. |
| **Elegida**: lista plana con discriminador `entity`. | Mantiene envelope uniforme + el consumidor filtra con un `if row["entity"] == "product"` o `pandas.groupby("entity")`. Se alinea con el patrón JSON que el scraper v2 está preparando para emitir en Stage 2 (ver §8). |

### 2.6 `TOOL_SCHEMA` (JSON Schema consumido por el repo de agentes)

Exportado en `tool_schema.py` como lista de **dos tools** (`cosme_trigger` +
`cosme_get_result`), escritos a mano (no `model_json_schema()` de pydantic) para
que el JSON que ve el agente sea explícito y reviewable. `additionalProperties:
false` en ambos, en línea con `extra="forbid"` del modelo de inputs.

---

## 3. Integración con BrightData API (dual-mode)

Idéntica a cosmetics-design — el middleware habla los dos transports y el
resource id es opaco (sin validar prefijos). Ver
[`middleware-dual-mode.md`](./middleware-dual-mode.md) para el detalle.

### 3.a Modo v3 (Datasets v3 / Scraper Studio)

- `POST /datasets/v3/trigger?dataset_id=gd_...` → `snapshot_id`.
- `GET /datasets/v3/progress/<snapshot_id>` → estado.
- `GET /datasets/v3/snapshot/<snapshot_id>?format=json` → payload.

### 3.b Modo DCA (legacy)

- `POST /dca/trigger?collector=c_...&queue_next=1` → `collection_id`.
- `GET /dca/dataset?id=<collection_id>` → `{"status": "building"}` mientras
  corre; array de rows cuando termina.

Resolución en el middleware: `CosmeClient(__init__)` llama a
`resolve_mode_and_id()` con precedencia v3 > DCA, y si ambas env vars están
vacías deja `api_mode="v3"` como default para no romper atributos — la falla
por credenciales faltantes aparece al llamar `trigger()` vía
`_ensure_credentials()`.

---

## 4. Reglas de post-procesamiento del envelope

Esto es la **única lógica de transformación** que el middleware aplica sobre
los rows que vienen de BrightData (el parseo vive en `scrapers/cosme/sc_code/`,
no acá).

### 4.1 Clasificación de entidad

`_classify_entity(raw)` decide el bucket antes de coercer. Prioridad:

1. Discriminador explícito (`raw["entity"]`, `_entity` o `type`) si el scraper
   lo emite literalmente como `"product"` / `"ranking"` / `"brand"`.
2. Heurística por claves presentes:
   - `source_type` + (`rank` | `product_id`) → `ranking`.
   - `product_id` o `product_url` → `product`.
   - `brand_id` + señal brand-level (`total_products` / `brand_total_products` /
     `total_reviews` / `brand_total_reviews`) **y sin `product_id`** →
     `brand`.
3. Ninguna → `None`. El row cuenta en `meta.skipped_by_reason["unknown_entity"]`
   pero **no se dropea silenciosamente** (se cuenta, no se emite).

### 4.2 Aliases scraper-native → spec §2

El JS parser emite **nombres qualified** (`product_url`, `product_name_raw`,
`brand_name`, `brand_total_products`, `award_year`, ...) para que su propio
output multi-entidad sea inambiguo en el lado scraper. **Spec §2 pide nombres
cortos** (`url`, `name_raw`, `name`, `total_products`, `year`, ...). El
middleware renombra por entidad:

| Entidad | Aliases (src → dst) |
|---|---|
| product | `product_url→url`, `product_name_raw→name_raw`, `product_name_clean→name_clean` |
| ranking | `award_year→year`, `award_group→group`, `award_category_slug→category_slug` |
| brand   | `brand_name→name`, `brand_url→url`, `brand_total_products→total_products`, `brand_total_reviews→total_reviews`, `brand_official_site→official_site`, `brand_country→country` |

**Política de colisión**: si el row trae **ambas** formas (`product_url` Y
`url` ya populado), el target canónico **se preserva** y el alias original
queda como key extra gracias a `ConfigDict(extra="allow")`. No se sobreescribe
un valor explícito.

### 4.3 Coerción al shape canónico

Para cada row clasificado:

1. Aplicar aliases.
2. Para cada campo del `*_FIELDS` tuple (todos los declarados en el modelo):
   si ausente, default a `None` para escalares o `[]` para list fields
   (`PRODUCT_LIST_FIELDS` / `RANKING_LIST_FIELDS` / `BRAND_LIST_FIELDS`).
3. Defensive: si un list field vino como string, se wrappa en `[value]` (la
   alternativa — dropear — pierde data).
4. Validar con el `pydantic` model. Si falla `ValidationError`, **no** se
   dropea: se devuelve el dict manualmente coercido. Criterio: data con
   shape inesperado > data perdida.
5. Se añade `entity: "<tipo>"` al final.

### 4.4 Clipping y disable flags

Aplicados en `_build_envelope` antes de emitir:

- `max_products`: solo sobre rows `entity=product`. Una vez alcanzado el cap,
  los siguientes products cuentan en `skipped_by_reason["max_products_cap"]`.
  Rankings y brands no se tocan.
- `include_rankings=false`: cada `entity=ranking` cuenta en
  `skipped_by_reason["rankings_disabled"]`.
- `include_brands=false`: análogo con `brands_disabled`.

### 4.5 Meta

```python
meta = {
    "rows": len(rows),                                # raw count BrightData
    "emitted": len(emitted),                          # final del envelope
    "emitted_by_entity": {"product":N,"ranking":M,"brand":K},
    "skipped_by_reason": {...},                       # diagnóstico cualitativo
    "blocked": count_of_products_with_block_flags,    # alimenta BLOCK_SATURATION
    "errors": count_of_non_dict_rows,                 # rows inválidos
    "started_at": iso, "ended_at": iso,
}
```

`meta.blocked` cuenta rows con `scraper_flags` que incluye
`rate_limit_blocked` o `name_extract_failed` — esas son las dos señales del
JS scraper que indican página bloqueada servida como HTML válido (spec §2:
`ご利用の環境からはアクセスできません`).

---

## 5. Catálogo de errores

### 5.1 Estándar (heredado de `core/errors.py`, sin modificar)

| code | retriable | cuándo |
|---|---|---|
| `SITE_BLOCKED` | false | BrightData reporta bloqueo sostenido |
| `STRUCTURE_CHANGED` | false | parser de `sc_code` falla en >20% rows |
| `TIMEOUT` | true | wall time sin respuesta |
| `INVALID_INPUTS` | false | pydantic falla **o** credenciales faltantes (no se llama a BrightData) |
| `BRIGHTDATA_ERROR` | true | 5xx de la API o `progress.status == "failed"` |
| `UNKNOWN` | false | fallback |

### 5.2 Extensión local — `COSME_ERROR_CODES` (en `client.py`)

| code | retriable | cuándo |
|---|---|---|
| `BLOCK_SATURATION` | false | >50% de rows `entity=product` cargan `rate_limit_blocked` o `name_extract_failed` |

Decisión explícita: **no se mutó el catálogo base** (`NORMALIZED_CODES`); la
extensión vive como dict local y se expone vía `COSME_ERROR_CODES`. El test
`test_per_scraper_error_codes_extendcore` valida que no haya colisión de
nombres con la base.

Analogía con cosmetics-design: `PAYWALL_SATURATION` (saturación del paywall
de nutraingredients) ↔ `BLOCK_SATURATION` (saturación del bloqueo anti-bot
de cosme.net). Mismo umbral (50%), misma política (no-retriable — sugiere
rotar pool residencial, no re-disparar).

`_maybe_block_saturation()` se ejecuta al final de `get_result()` solo
cuando `status == "done"`, sobre el envelope ya construido. Si dispara,
convierte la respuesta a `failed` preservando counters en `error.details`.

---

## 6. Límites operativos

| Knob | Valor | Fuente |
|---|---|---|
| `DEFAULT_ETA_SECONDS` | 3600 (60 min) | Spec §7 hard cap 120 min; run típico 45-75 min |
| `max_products` hard cap | 3000 | Spec §7 "product detail max 3000 unique" |
| `max_categories` hard cap | 30 | Spec §7 "category_ranking max 5 x 30 cats" |
| `year` range | 2000..2100 | Fat-finger guard; JS tolera 2000..currentYear+1 |
| `BLOCK_SATURATION_THRESHOLD` | 0.5 | Mismo criterio que PAYWALL_SATURATION |

La ETA es hint: el consumidor (agents repo) hace polling real con
`get_result()`.

Cache/TTL en el lado agents: cosme es cíclico anual — cachear por
`(year, max_categories, category)` probablemente tenga TTL de días/semanas,
no minutos. Recomendación para el consumidor, no enforzada acá.

---

## 7. Convenciones de naming

| Concepto | Valor |
|---|---|
| Paquete Python | `middlewares/cosme/` |
| Carpeta JS | `scrapers/cosme/` |
| Source en envelope | `"cosme"` |
| Tool 1 (Anthropic) | `cosme_trigger` |
| Tool 2 (Anthropic) | `cosme_get_result` |
| Env var v3 | `BRIGHTDATA_DATASET_ID_COSME` |
| Env var DCA | `BRIGHTDATA_COLLECTOR_ID_COSME` |
| Env var auth | `BRIGHTDATA_API_KEY` (compartida) |

Todos coherentes con cosmetics-design salvo la parte de nombre (sin
underscore porque `cosme` ya es Python-safe).

---

## 8. Dependencias del scraper JS (Stage 1 + Stage 2)

**Esta es la sección donde cosme se separa más del canónico**: el middleware
ya acepta las tres entidades, pero el scraper JS **hoy solo emite `product`**.

### 8.1 Estado actual — 2026-04-23

| Capa | Estado | Fuente |
|---|---|---|
| `scrapers/cosme/vendor/sc_browser/{interaction,parser}_code.js` | presente (v0 DB AI) | `vendor/` |
| `scrapers/cosme/vendor/sc_code/{interaction,parser}_code.js`    | presente (v0 DB AI) | `vendor/` |
| `scrapers/cosme/sc_browser/*`                                   | **vacío** (aún no hay `_v1.js`) | Etapa 2 pendiente |
| `scrapers/cosme/sc_code/*`                                      | **solo README**, sin `_v1.js` | Etapa 2 pendiente |

Mientras no exista una versión `_vN.js` nuestra, corremos contra el vendor
— que parsea `product` pero **no emite filas separadas para `ranking` ni
`brand`**. Los rankings viajan hoy dentro del product como el campo `rankings:
[...]` (spec §3 último bullet), no como fila independiente con
`entity=ranking`. Las brands solo aparecen como atributos `brand_id` /
`brand_name` dentro de product, no como filas con `entity=brand`.

**Consecuencia operativa**:

- Al correr el middleware hoy contra una snapshot real, `data[]` contendrá
  únicamente rows `entity=product` (más lo que el scraper haya marcado
  explícitamente — hoy, nada).
- `meta.emitted_by_entity` se verá como `{"product": N, "ranking": 0, "brand": 0}`.
- `include_rankings=false` / `include_brands=false` son no-op efectivos hoy.
- La capacidad de consumir rankings/brands **ya está lista en el middleware**
  — se activa sola el día que el scraper Stage 2 emita las filas.

### 8.2 Trabajo pendiente del lado JS (NO del middleware)

Etapa 2 (iteración `_vN`) del scraper tiene que:

1. **En Stage 1 `parser_code_vN.js`**: cuando el DOM es `/bestcosme/archive/{year}/{group}/`
   o `/bestcosme/archive/{year}/category/{slug}/`, además de llamar
   `next_stage()` con los product URLs, emitir **filas propias** con shape
   `{source_type: "bestcosme", year, group, category_slug, rank, product_id, product_url, ...}`
   (spec §4). Esas filas hoy no se emiten; el sidecar `next_stage` se pierde
   como fila standalone.
2. **En Stage 2 `parser_code_vN.js`** para `/brands/{id}/?nt=1`: emitir una
   fila con shape `{brand_id, brand_name, brand_url, brand_total_products,
   brand_total_reviews, ...}` (spec §5). Hoy las marcas solo aparecen
   embedded en product.
3. (Opcional) Considerar reescribir el scraper para emitir **directamente
   los nombres cortos de §2** (`url` en vez de `product_url`, `name` en vez
   de `brand_name`, etc.). Esto haría los aliases en §4.2 redundantes. Ver §9.

### 8.3 Qué NO gestiona el middleware

Para dejar claro (idéntico al canónico):

- Cache TTL + tabla `scraper_runs` → repo de agentes.
- `ServiceRegistry` + declaración de tool al agente Anthropic → repo de agentes.
- Loop de tool-use + polling hasta `done` → repo de agentes.
- Parsing / decoding Shift_JIS / detección de bloqueo → JS scraper
  (`sc_browser/` + `sc_code/`).
- Llamadas directas a cosme.net → JS scraper (el middleware solo habla con
  BrightData API).

El middleware es una capa delgada sobre BrightData + clasificación multi-entidad
+ aliases + clipping. Nada más.

---

## 9. Preguntas abiertas / decisiones pendientes

Heredadas del trabajo del agente `middleware-python` al cerrar `middlewares/cosme/`:

1. **Aliases vs naming nativo del scraper.** Hoy el middleware renombra
   `product_url → url`, `brand_total_products → total_products`, etc. Si la
   próxima iteración del scraper (`parser_code_v2.js`+) emite directamente
   los nombres cortos de §2, los aliases quedan como **código muerto** (pero
   seguro: el `_apply_aliases` es no-op si las keys src no están presentes).
   **Decisión pendiente**: ¿actualizamos el scraper para que emita §2
   literalmente y borramos los aliases, o los mantenemos como capa de
   traducción permanente? Trade-off:
   - A favor de scraper-emits-short-names: menos código en el middleware, más
     consistencia cross-entity.
   - A favor de mantener aliases: los nombres qualified son más legibles
     cuando se inspecciona el output crudo del scraper en `scrapers/cosme/results/`.
2. **`mode: full-refresh`**. Hoy se forwardea a `envelope.inputs` sin afectar
   nada en el middleware (el scraper JS no lo lee). ¿Es útil tenerlo como
   señal pura para el consumidor, o deberíamos removerlo de `CosmeInputs`
   hasta que haya semántica real? Conservarlo es gratis y deja la puerta
   abierta a que v2 del scraper honor `full-refresh` bypaseando su cache
   interno 24h por `product_id` (spec §7).
3. **Umbral de `BLOCK_SATURATION` = 0.5**. Es el mismo que el canónico usa
   para paywall. Para cosme el bloqueo es más silencioso (page 200 con HTML
   válido pero vacío); si en runs reales vemos que un 30-40% de rows
   blocked ya hace el envelope inservible, el umbral debería bajar. No hay
   datos empíricos todavía — se decide post primer run productivo.
4. **Fixture real vs fabricado**. Hoy `tests/fixtures/cosme_snapshot_s_demo01.json`
   es hand-crafted (ver README de fixtures). Se reemplaza por un snapshot
   real apenas uno de los dos env vars se pueble y se dispare el scraper
   en prod.
5. **Rankings embedded en product vs fila standalone**. Hoy el scraper emite
   rankings como `product.rankings: [{ranking_name, position, year, ...}]`
   (nested dentro de product). Esa info está duplicada respecto a lo que
   emitirá `entity=ranking` cuando Stage 2 cumpla §8.2 bullet 1. ¿Mantenemos
   las dos vistas (embedded + standalone) para consumidores que prefieran
   una u otra, o dropeamos `product.rankings[]` una vez que las filas
   standalone estén operativas? Decisión pendiente; no bloquea nada hoy.

---

## 10. Entregables al cierre

Ya presentes en el repo:

1. `middlewares/cosme/` con `__init__.py`, `client.py`, `config.py`,
   `models.py`, `tool_schema.py`.
2. `middlewares/cosme/tests/` con `conftest.py`, `fixtures/cosme_snapshot_s_demo01.json`
   (hand-crafted, TODO documentado para reemplazo por snapshot real) +
   `fixtures/README.md` que explica origen y scenarios cubiertos.
3. `middlewares/cosme/tests/test_client.py` — cobertura multi-entidad,
   aliases, max_products cap, include_rankings/include_brands, dual-mode,
   `BLOCK_SATURATION`, TOOL_SCHEMA, coerción defensive, invalid inputs.
4. Reutilización del `core/` de cosmetics-design — sin nuevas mutaciones al
   catálogo de errores ni al envelope.

Pendientes fuera del scope del middleware (repo de agentes + Etapa 2 del
scraper JS):

- Poblar `BRIGHTDATA_API_KEY` + uno de los dos resource id env vars.
- Correr una snapshot real y reemplazar el fixture fabricado.
- Iterar `scrapers/cosme/sc_{browser,code}/_vN.js` para que Stage 1 emita
  filas `ranking` y Stage 2 emita filas `brand` (ver §8.2).
- Declarar el scraper en `ServiceRegistry` del repo de agentes + cache TTL
  sobre `(year, max_categories, category)`.

---

[CREADO 2026-04-23 — post-facto; ratifica el middleware ya implementado en `middlewares/cosme/`]
