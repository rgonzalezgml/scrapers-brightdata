# Handoff Fase 3 — made-in-china

> **Destino del trabajo**: `middlewares/made_in_china/` (este repo, ya
> implementado el 2026-04-21).
> **Consumidor**: repo de agentes. Importa este paquete como dependencia y
> encima coloca `ServiceRegistry`, persistencia (`scraper_runs` en
> PostgreSQL), cache TTL y declaración de tool al agente.
> **Agente responsable**: `middleware-python`.
>
> **Nota sobre el orden de trabajo (2026-04-21):** por pedido explícito del
> usuario el middleware se construyó antes que el handoff. Este documento es
> **post-facto**: consolida las decisiones ya tomadas en código, sirve de
> contrato público al repo de agentes, y cierra el loop con la plantilla
> canónica de `cosmetics-design-handoff.md`. El middleware sigue de cerca el
> patrón multi-entidad que cosme introdujo y los refinements de dual-mode de
> `docs/fase3/middleware-dual-mode.md`.
>
> **Madurez del scraper JS**: made-in-china es — junto con cosmetics-design —
> uno de los **dos únicos** middlewares donde el parser JS emite YA los campos
> §2 directos del spec, sin que el middleware tenga que reinterpretar valores.
> El parser relevante es `scrapers/made-in-china/sc_code/parser_code_v3.js`
> (emite 29 campos product + 14 supplier, §2 completo).

---

## 0. Inputs ratificados

Las decisiones tomadas durante la implementación ya fijadas en código:

1. **Resource id de BrightData** — dual-mode con dos env vars específicas:
   - `BRIGHTDATA_DATASET_ID_MADE_IN_CHINA` (formato `gd_...`) — modo v3.
   - `BRIGHTDATA_COLLECTOR_ID_MADE_IN_CHINA` (formato `c_...` / `j_...`) —
     modo DCA legacy.
   Si ambas están seteadas, **v3 gana** (spec dual-mode §3.3). Si ninguna
   está seteada, el middleware levanta `INVALID_INPUTS` en `trigger()` con
   el hint nombrando ambas env vars. El id es opaco — no se valida prefijo.
   Implementado en `config.py::resolve_mode_and_id`.
2. **Env var `BRIGHTDATA_API_KEY`** — auth compartida con los dos transports.
3. **Nombre del paquete Python**: `middlewares/made_in_china/` (underscore).
   El scraper JS vive en `scrapers/made-in-china/` (hyphen).
4. **Compatibilidad hacia atrás del constructor**: el `__init__` acepta el
   alias silencioso `dataset_id=` para que callers viejos (pre-dual-mode)
   no rompan.

---

## 1. Contexto del scraper

- **Nombre**: `made-in-china` (carpeta JS) / `made_in_china` (paquete Python).
- **Proveedor**: Focus Technology.
- **Categoría**: Precios. Es un scraper de **cotizaciones B2B chinas**,
  hermano temático de Alibaba.
- **Función**: precios alternativos de materiales China (químicos
  industriales y empaque) como segunda fuente comparable contra Alibaba.
- **Entidades**: `product` (29 campos) + `supplier` (14 campos). Multi-entidad
  — `data[]` es heterogéneo y cada row lleva discriminador `entity`.
- **Fuente**: `https://www.made-in-china.com/` y subdominios
  `{slug}.en.made-in-china.com`.
- **Spec completo**: `docs/specs/scrapers/made-in-china.md` (este repo).
  Leerlo entero antes de modificar el middleware; §2 es el wire shape
  inmutable; §4–§6 el catálogo de campos; §8 las skip rules; §9 los
  límites operativos y el catálogo de flags; §11 el fixture obligatorio.
- **Implementación JS de BrightData**: `scrapers/made-in-china/sc_browser/`
  + `sc_code/`. Parser maduro actual: `sc_code/parser_code_v3.js` +
  `sc_browser/interaction_code_v5.js`. El middleware consume lo que estos
  archivos emiten; **no reimplementa parsing**.

Cadencia de corridas esperada (la decide el repo de agentes, no el
middleware): diaria incremental de ~5 keywords via-1 + 12 subcategorías
via-2, con `max_pages=3` por seed. Full-refresh semanal opcional.

---

## 2. Contrato público del paquete

### 2.1 `trigger(inputs) -> dict`

```python
async def trigger(inputs: MadeInChinaInputs | dict) -> dict:
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

### 2.3 Inputs — `MadeInChinaInputs` (pydantic v2)

```python
class MadeInChinaInputs(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    urls: list[str] | None = None                  # 1..MAX_SEED_URLS (50); None → DEFAULT_LISTING_URL
    max_pages: int = 3                             # -1..500; 0 se normaliza a -1 en el interaction JS
    max_products: int = 400                        # 1..800 — cap post-download spec §9
    max_suppliers: int = 100                       # 1..200 — cap post-download spec §9
    include_suppliers: bool = True                 # False dropea todas las rows entity=supplier
    require_price: bool = False                    # True dropea product rows con price_min_usd y price_max_usd ambos null
    mode: Literal["incremental", "full-refresh"] = "incremental"
```

Notas:
- `urls` aceptan los tres tipos de seeds permitidos por spec §3: listing
  (via-1 `/products-search/...` o via-2 `/{Chem|Packaging-Printing}-Catalog/...`),
  detail (`.../product/{ID}/...`), o supplier home
  (`{slug}.en.made-in-china.com/`). El middleware NO discrimina — el
  interaction JS hace el branching.
- `max_pages` se propaga **verbatim** a `input.max_pages` de cada seed:
  `-1` = procesar hasta `total_pages` del widget `.page-total` del listing;
  `N > 0` = procesar `min(N, total_pages)`; `0` lo normaliza la interaction
  v5 a `-1` y emite flag `max_pages_invalid` a nivel run. Aplica SOLO a
  URLs de listing (detail y supplier home ignoran `max_pages`).
- `max_products` / `max_suppliers` son **post-download clipping**: el
  scraper sigue sus propios caps internos (spec §9: 800 / 200); el
  middleware refina por run para predicibilidad del envelope.
- `require_price` es red de seguridad: el scraper ya skipea en §8 cuando
  falta `price_raw`, pero si una regresión deja una row con `null` price,
  este flag la dropea.
- `mode` es un hint para el repo de agentes (cache 24h incremental vs
  full-refresh). El middleware lo forwardea en `envelope["inputs"]`.

### 2.4 Envelope normalizado (cuando `status == "done"`)

```python
{
  "source": "made-in-china",
  "scraped_at": "2026-04-21T15:30:00Z",
  "inputs": { ... echo de inputs efectivos ... },
  "data": [
    { "entity": "product",  ... 29 campos §2 ... },
    { "entity": "supplier", ... 14 campos §2 ... },
    ...
  ],
  "meta": {
    "rows": 123,
    "emitted": 119,
    "emitted_by_entity": {"product": 104, "supplier": 15},
    "skipped_by_reason": {
       "suppliers_disabled": 0,
       "price_missing": 3,
       "max_products_cap": 0,
       "max_suppliers_cap": 1,
       "unknown_entity": 0,
       "non_dict_row": 0
    },
    "blocked": 0,
    "structural_degraded": 2,
    "errors": 0,
    "started_at": "...",
    "ended_at": "..."
  }
}
```

El schema de `data[]` (campos de `product` y `supplier`) está fijado en
`docs/specs/scrapers/made-in-china.md` §2 — **inmutable**. Siempre emitir
todas las claves (null explícito si faltan; lista vacía en vez de null
para las claves lista `category_path`, `scraper_flags`,
`management_certifications`).

### 2.5 `TOOL_SCHEMA` (JSON Schema consumido por el repo de agentes)

Exportado en `tool_schema.py` como **lista** de dos tools:
`made_in_china_trigger` y `made_in_china_get_result`. El repo de agentes
hace `tools=[...*TOOL_SCHEMA]` al llamar la API de Anthropic. Escrito a
mano (no `model_json_schema()`) para mantener el contrato reviewable.

---

## 3. Traducción inputs públicos ↔ seed JS

Implementado en `client.py::MadeInChinaClient._build_brightdata_inputs`.

**Stage 1 JS inputs (por seed):**

| JS input (`scrapers/made-in-china/sc_browser/interaction_code_v5.js`) | Derivado de |
|---|---|
| `url` | cada elemento de `MadeInChinaInputs.urls` (o `DEFAULT_LISTING_URL` si `urls is None`) |
| `max_pages` | `MadeInChinaInputs.max_pages` verbatim |
| `is_rerun` | **siempre `False`** — `is_rerun=True` sólo lo usa el propio scraper en el fan-out paralelo de paginación (spec §9, punto 3); los seeds externos jamás lo emiten |

Una seed por URL (fan-out flat: si caller manda 5 URLs → 5 seeds → 5
trabajos paralelos en BrightData). Cap de seeds: `MAX_SEED_URLS=50` (ver
§6).

**Inputs que NO viajan al scraper** (son de post-procesamiento Python-side,
no del runtime JS):

- `max_products`, `max_suppliers` — clipping en `_build_envelope`.
- `include_suppliers`, `require_price` — filtros en `_build_envelope`.
- `mode` — solo para `envelope["inputs"]`, el scraper no lo lee.

---

## 4. Post-procesamiento del envelope

Implementado en `client.py::_build_envelope` + helpers.

### 4.1 Clasificación de entidad (`_classify_entity`)

Cada row del snapshot puede ser product o supplier. El scraper v3 emite
cada rama con el shape de su entidad (son dos ramas de `parse()` en
`parser_code_v3.js` según `isProductDetail` del pathname), pero NO emite
un marker `entity` explícito — el marker `__entity` fue eliminado en v3
(no forma parte de §2). El middleware agrega su propio discriminador a
partir de dos estrategias en orden:

1. **Discriminador explícito** (si el scraper algún día lo agrega):
   `entity`, `_entity`, `__entity`, o `type == "product" | "supplier"`.
   Atención al falso amigo `type`: en product rows es enum category
   (`chemical | empaque | other`, spec §8), NO discriminador. Sólo se
   acepta cuando el valor es literalmente `"product"` o `"supplier"`.
2. **Heurística sobre claves presentes**:
   - Tiene `product_id`, `product_url` o `price_raw` → `product`.
   - Tiene `supplier_id` sin `product_id` y al menos una supplier-specific
     (`business_type`, `member_level`, `employees_raw`, `audited_supplier`,
     `management_certifications`, `year_established`, `supplier_name`,
     `main_products`) → `supplier`.
3. **Ninguna** → row contada en `skipped_by_reason["unknown_entity"]` y
   no emitida.

### 4.2 Aliases defensivos

`PRODUCT_ALIASES` / `SUPPLIER_ALIASES` (en `models.py`) renombran claves
legacy a §2 canónico. El parser v3 emite §2 directo — estos aliases son
red de seguridad:

- Para parsers v1/v2 previos (o regresiones): `url → product_url`,
  `name_raw → product_name_original`, `category → category_mic`,
  `moq_qty → moq_quantity`, etc.
- Para el vendor original (E8 de `errors.md` — vendor mezclaba
  supplier fields en product).

Regla de colisión: si la row trae ambos (canónico + alias) con el
canónico no-null, el canónico gana. El alias se forwardea en los extras
(model `extra="allow"`).

### 4.3 Fill de keys §2

`_coerce_row` garantiza que toda key §2 esté presente en cada row:
- Atómica faltante → `None`.
- Lista faltante o `null` → `[]` (`PRODUCT_LIST_FIELDS` =
  `{category_path, scraper_flags}`, `SUPPLIER_LIST_FIELDS` =
  `{management_certifications, scraper_flags}`).
- Extras del scraper (debug, futuras keys) → forwarded vía pydantic
  `extra="allow"`.

### 4.4 ISO-2 safety net para `supplier_country`

Implementado en `_normalize_country_inplace` + `config.iso2_for_country`
+ mapa `COUNTRY_NAME_TO_ISO2`.

El parser v3 ya aplica su propio mapa `COUNTRY_ISO` sobre rows supplier;
la mayoría llega normalizada (`"CN"`, `"VN"`, etc). El middleware
**re-verifica**:

- Si el valor actual es 2 letras uppercase (`len==2 and isupper()`) →
  asume ISO-2 válido, no toca.
- Si es free-text (ej. `"Vietnam"`, `"China"`) → mappea vía la tabla
  ampliada del middleware (mapa más grande que el del parser para
  cubrir regresiones).
- Si no mappea → setea `supplier_country = None` y añade flag
  `country_unmapped` a `scraper_flags`.

**Aplica SOLO a `supplier.supplier_country`.** El campo
`product.origin_country` (spec §5) es free-text derivado de
`additionalProperty.name = "Origin"` del JSON-LD — NO se reescribe
(puede ser "China", "Shandong", "Japan", etc, y downstream lo toma así).

### 4.5 Meta counters

- `rows`: total raw rows recibidas del snapshot.
- `emitted`: rows que sobrevivieron a filtros y quedaron en `data[]`.
- `emitted_by_entity`: dict con contadores por entidad.
- `skipped_by_reason`: dict con razones de skip (`unknown_entity`,
  `suppliers_disabled`, `price_missing`, `max_products_cap`,
  `max_suppliers_cap`, `non_dict_row`).
- `blocked`: count de rows que tenían `blocked` o `route_disallowed` en
  `scraper_flags`.
- `structural_degraded`: count de product rows con
  `jsonld_parse_fallback`, `price_unit_unknown` o `metric_unit_missing`.
- `errors`: rows inválidas (no-dict).

Estos counters alimentan las dos saturation checks del §5.

---

## 5. Catálogo de errores

### 5.1 Base (heredados de `middlewares/core/errors.py`)

| code | retriable | cuándo |
|---|---|---|
| `INVALID_INPUTS` | false | validación pydantic falla en `trigger()` (no llama BrightData); o `job_id` vacío en `get_result()`; o dual-mode no puede resolver resource_id |
| `BRIGHTDATA_ERROR` | true | 5xx / error reportado por la API BrightData (v3 `failed` o DCA `failed`) |
| `TIMEOUT` | true | wall time del poll excedido (hard cap spec §9: 90 min) |
| `SITE_BLOCKED` | false | BrightData reporta bloqueo sostenido explícito |
| `STRUCTURE_CHANGED` | false | el parser degradó — extendido por el middleware con el criterio de 5.2 |

### 5.2 Extensiones locales de made-in-china

Definidas en `client.py::MADE_IN_CHINA_ERROR_CODES` y aplicadas en
`_maybe_block_saturation` / `_maybe_structure_degraded`. Umbrales 50%
(mismo cutoff que PAYWALL_SATURATION de cosmetics-design y
BLOCK_SATURATION de cosme).

| code | retriable | cuándo |
|---|---|---|
| `BOT_BLOCK_SATURATION` | false | `blocked / emitted > 0.5` — más de la mitad de rows emitted traen flag `blocked` o `route_disallowed` (spec genomma lab §2 — Access Denied / Cloudflare / waf). Re-run con la misma pool de proxies es inútil; escalar a BrightData para rotar pool residencial. |
| `STRUCTURE_CHANGED` | false | `structural_degraded / products_emitted > 0.5` — más de la mitad de product rows trae flags de degradación del parser (`jsonld_parse_fallback`, `price_unit_unknown`, `metric_unit_missing`). Señal de que el DOM / JSON-LD del vendor cambió y hay que iterar `parser_code_vN+1.js`. |

Ambas son **post-envelope**: el middleware construye el envelope `done`
normalmente y sólo si el umbral se cruza, lo reemplaza por
`{"status": "failed", "error": {...}}`. El consumidor siempre puede
ignorar la saturation check y pedir el envelope crudo vía
`client.build_envelope_for_rows(rows, ...)` (helper público expuesto para
re-derivar envelopes desde rows cacheadas por el repo de agentes).

---

## 6. Límites operativos

Consolidados en `config.py`:

| constante | valor | justificación |
|---|---|---|
| `DEFAULT_LISTING_URL` | `https://www.made-in-china.com/products-search/hot-china-products/Industrial_Chemicals.html` | spec §10 fixture keyword via-1 p1 |
| `DEFAULT_MAX_PAGES` | `3` | spec §9 default histórico |
| `MAX_PRODUCTS_HARD_CAP` | `800` | spec §9 "hasta 800 unique PRODUCT_ID detail" |
| `MAX_SUPPLIERS_HARD_CAP` | `200` | spec §9 "hasta 200 supplier home" |
| `MAX_SEED_URLS` | `50` | headroom para los 12 slugs default (5 kw + 8 chem + 4 pack) × 4 para diversificación; spec §9 hard cap 2000 requests / 90 min |
| `BLOCK_SATURATION_THRESHOLD` | `0.5` | mismo cutoff que cosme |
| `STRUCTURE_DEGRADED_THRESHOLD` | `0.5` | mismo cutoff que cosme |
| `DEFAULT_ETA_SECONDS` | `45 * 60` | banda típica 30–60 min observada; hard cap spec §9 = 90 min |

Pagination `max_pages` bounds: `[-1, 500]` (pydantic valida); 500 es
techo arbitrario grande para no bloquear casos de catálogos gigantes
(via-2 `Alkali` tiene decenas de páginas posibles).

---

## 7. Convenciones de naming

- **Paquete Python**: `middlewares/made_in_china/` (underscore, ver
  README Fase 3).
- **`SOURCE_NAME`** (emitted en `envelope["source"]`): `"made-in-china"`
  (hyphen — se mantiene el slug del scraper JS).
- **Env vars**: `BRIGHTDATA_DATASET_ID_MADE_IN_CHINA` /
  `BRIGHTDATA_COLLECTOR_ID_MADE_IN_CHINA` (snake upper).
- **Tool names** (JSON Schema): `made_in_china_trigger` /
  `made_in_china_get_result` (underscore).
- **Carpeta fixtures tests**:
  `middlewares/made_in_china/tests/fixtures/made_in_china_snapshot_<id>.json`.

---

## 8. Dependencias del scraper JS

### 8.1 Parsers que el middleware asume en producción

- `scrapers/made-in-china/sc_browser/interaction_code_v5.js` — Stage 1
  interaction. Maneja la paginación paralela v5 (§9): desde pagina 1
  encola en paralelo pages `2..cap` donde
  `cap = max_pages === -1 ? total_pages : Math.min(max_pages, total_pages)`.
  Los reruns (`is_rerun=true`) NO re-encolan fan-out (evita explosión
  exponencial). Normaliza `max_pages == 0` a `-1` + flag
  `max_pages_invalid` a nivel run.
- `scrapers/made-in-china/sc_code/parser_code_v3.js` — Code worker
  parser. Emite los **29 campos product + 14 campos supplier** del §2
  directamente, con los nombres canónicos del spec. **Ésto es lo que hace
  a made-in-china único junto con cosmetics-design**: el middleware NO
  reinterpreta valores; sólo fill de keys faltantes + normalización ISO-2
  defensiva.

### 8.2 Contraste con hermanos

| scraper | estado parser vs §2 |
|---|---|
| cosmetics-design | parser emite §2 directo — middleware delgado |
| **made-in-china** | **parser v3 emite §2 directo** — middleware delgado |
| cosme | parser emite shape intermedio — middleware re-mapea en los 3 entities (product, sku, review) |
| olive-young | parser emite shape intermedio — middleware re-mapea |
| alibaba | parser emite shape intermedio — middleware re-mapea |
| indiamart | parser emite shape intermedio — middleware re-mapea |

La madurez del parser permite que los aliases (§4.2) existan **solo como
red de seguridad**. Si una regresión rompe el v3 y vuelve a emitir
nombres legacy (v1/v2), los aliases atrapan los casos conocidos. Si
aparecen nombres nuevos no mapeados, la row se emite pero con `None` en
las keys §2 correspondientes — esto sube `structural_degraded` y
dispara `STRUCTURE_CHANGED` si cruza el 50%.

### 8.3 Campos `rating_avg` con flag sintético

El parser v3 agrega flag `rating_synthetic` cuando detecta
`ratingValue == 5 AND author == MIC_BUYER` (spec §5: MIC pone en promedio
5 o rating ficticio). El middleware **solo forwardea el flag** — no
recalcula `rating_avg`. La lógica de decisión de confiar o descartar el
rating vive downstream (repo de agentes).

### 8.4 Wrappers del Output Schema de BD Studio

El parser v3 devuelve los siguientes campos envueltos en constructores
del runtime de BD Studio:

- `product.product_url`, `product.image_primary`,
  `supplier.supplier_url` → `new URL(value)`.
- `product.price_min_usd`, `product.price_max_usd`,
  `product.price_normalized_per_kg` → `new Money(numericValue, "USD")`.

BrightData serializa estos wrappers a **tipos planos** en el snapshot
final (string URL / número USD). El middleware confía en esta
serialización: los tests de fixture usan strings/números directos.

**Regresión observable**: si algún día BrightData cambia el formato del
snapshot y los wrappers llegan como dicts (`{"amount": ..., "currency":
...}` o `{"href": "..."}`), el middleware los forwardearía tal cual y
pydantic fallaría la coerción (los campos están tipados `str | None` y
`float | None`). Ver §9 como pregunta abierta.

---

## 9. Preguntas abiertas / riesgos

1. **Serialización de wrappers `Money` / `URL` del BD Studio.** El
   middleware asume que el snapshot llega con strings / números planos.
   Si en algún run live los wrappers llegan como dicts, los tests de
   fixture (actualmente hand-crafted) no lo detectarían — sería regresión
   visible sólo en producción. **Mitigación**: cuando el primer run real
   termine, capturar el snapshot, validar que los tipos llegan planos, y
   si no, actualizar `_coerce_product` para desempaquetar `{amount,
   currency}` → número y `{href}` → string.

2. **Semántica de `rating_synthetic`.** El parser v3 solo marca la row
   con el flag, no mueve `rating_avg`. ¿Downstream debe descartar esos
   ratings del promedio, o conservarlos y tratar el flag como metadata?
   Decisión del repo de agentes — no responsabilidad del middleware.

3. **Fixture todavía hand-crafted.** `tests/fixtures/made_in_china_snapshot_s_demo01.json`
   tiene 6 rows construidas a mano (4 product + 2 supplier), con row 1
   fiel al fixture obligatorio del spec §11 (`product_id=IEFUtrGOCdRZ`,
   N-Butyl Acetate, supplier WEIHAI JINDO). **Reemplazar con snapshot
   real** cuando corra el scraper en producción — ver README en la
   carpeta fixtures.

4. **Heterogeneidad de `data[]`.** Consumidores menos cuidadosos pueden
   olvidar filtrar por `entity` y sumar `price_min_usd` sobre supplier
   rows (donde no existe). El repo de agentes debe documentar en el
   prompt del LLM que `data[]` es heterogéneo y que cada row lleva
   `entity` discriminator. El envelope meta carry `emitted_by_entity`
   como señalizador.

5. **`include_suppliers=False` corta supplier counters.** Si el caller
   pasa `include_suppliers=False`, los supplier rows se cuentan en
   `skipped_by_reason["suppliers_disabled"]` pero NO en
   `emitted_by_entity["supplier"]` (que queda en 0). Es el comportamiento
   intencional — `emitted_by_entity` refleja lo que está en `data[]`. Si
   downstream necesita saber cuántos suppliers vio el scraper, debe mirar
   `skipped_by_reason["suppliers_disabled"]`.

6. **`origin_country` free-text (product).** A diferencia de
   `supplier_country`, el middleware NO normaliza `origin_country` en
   product rows porque el spec §5 lo define como free-text derivado del
   `additionalProperty.name = "Origin"` del JSON-LD. Downstream debe
   tratar este campo como no-ISO2 (puede traer "China", "Shandong",
   "Jiangsu", "Japan", o incluso frases largas). Documentado pero no
   mitigado en el middleware.

---

## 10. Estado del paquete al 2026-04-21

Implementado y presente en el repo:

```
middlewares/made_in_china/
├── __init__.py           — exports trigger, get_result, TOOL_SCHEMA
├── client.py             — MadeInChinaClient, dual-mode, multi-entidad
├── config.py             — env resolution, COUNTRY map, umbrales, defaults
├── models.py             — MadeInChinaInputs, ProductRow, SupplierRow, aliases
├── tool_schema.py        — 2 tools JSON Schema
└── tests/
    ├── conftest.py       — fixture loader + marker brightdata
    ├── fixtures/
    │   ├── README.md
    │   └── made_in_china_snapshot_s_demo01.json   ← HAND-CRAFTED
    └── test_client.py
```

Pendiente del usuario:
- Poblar `BRIGHTDATA_API_KEY` + uno de los dos env vars de resource id.
- Reemplazar el fixture hand-crafted por un snapshot real cuando se corra
  el scraper por primera vez.
- Actualizar `docs/fase3/README.md` marcando el handoff como **cerrado**
  cuando pase el primer run live + commit SHA.
