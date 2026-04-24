# Handoff Fase 3 — alibaba

> **Destino del trabajo**: `middlewares/alibaba/` (este repo).
> **Consumidor**: repo de agentes. Importa el paquete como dependencia y encima coloca `ServiceRegistry`, persistencia (`scraper_runs`), cache TTL y declaración de tool al agente.
> **Agente responsable**: `middleware-python` (ya implementó) — este handoff documenta el contrato **post-facto**.
>
> **Naturaleza de este documento**: a diferencia del cosmetics-design-handoff (que precedió al código), este handoff se redactó **después** de que el middleware ya existía — por instrucción del usuario el orden fue invertido. No es un plan de implementación; es el contrato congelado sobre el código vivo en `middlewares/alibaba/` (commit a determinar). Las **preguntas abiertas** del §9 existen porque nunca pasaron por la compuerta pre-implementación normal; resolverlas puede requerir un follow-up PR.
>
> **Categoría Precios — primer scraper del set**. cosmetics-design / cosme / olive-young son I+D (artículo, producto cosmético en retail). alibaba trae tres consideraciones nuevas que anclan el patrón para made-in-china e indiamart: **moneda** (conversión a USD), **unidades** (kg/ton/L/piece → normalización per-kg), **país ISO-2** (supplier origin normalizado para agregaciones cross-source).

---

## 0. Inputs ratificados + preguntas abiertas

Antes de declarar este handoff cerrado, el usuario debe ratificar/decidir:

1. **Resource id de BrightData** — el middleware soporta ambos modos; el usuario puebla uno:
   - `BRIGHTDATA_DATASET_ID_ALIBABA` (formato `gd_...`) — Studio / Datasets v3.
   - `BRIGHTDATA_COLLECTOR_ID_ALIBABA` (formato `c_...`) — DCA legacy, el modo que el spec genomma lab §2 describe explícitamente.
   - Si ambas están seteadas, **v3 gana** (ver `config.py::resolve_mode_and_id`).
2. **¿Existe `middlewares/core/`?** Sí. cosmetics-design es el POC y `alibaba` hereda del patrón `BaseScraperClient` + `DCATransport` + `V3Transport`. Nada que crear en `core/`; sí se extiende localmente el catálogo de errores.
3. **Env vars dependientes** — `BRIGHTDATA_API_KEY` (común) + uno de los dos resource id per-scraper anteriores. Toda otra config es constante en `config.py` (5 seeds default, `max_pages=5`, `max_products=2000`, `min_price=1`, `max_price=10000`).
4. **Paquete Python**: `middlewares/alibaba/` (underscore-safe; hyphen en `scrapers/alibaba/`).
5. **Confirmar con el usuario** (lista completa en §9):
   - ¿Promover `supplier` a entidad separada o mantenerlo denormalizado en `product`?
   - ¿Conversión de moneda (FX) en JS o en Python? — hoy middleware confía en `price_min_usd` / `price_max_usd` tal como el JS los emite.
   - ¿`type` / `category` Literal estrictos o string libre? — middleware eligió `Literal["chemical","packaging"]` para `type` y `str` libre para `category`.
   - Ratificar naming `BRIGHTDATA_COLLECTOR_ID_ALIBABA` (per-scraper, como cosmetics-design) vs el `BRIGHTDATA_COLLECTOR_ID` sin sufijo que el spec §2 menciona. Middleware usa el per-scraper; handoff recomienda fijar eso.

**Sin ratificación de §9 el handoff queda como "borrador cerrado" — el código funciona, pero la superficie pública puede ajustarse en el siguiente PR.**

---

## 1. Contexto del scraper

- **Nombre**: `alibaba` (carpeta JS) / `alibaba` (paquete Python — sin rename porque no lleva hyphen).
- **Categoría**: **Precios** (spec header). Primer scraper de esta categoría en el repo.
- **Función** (literal del xlsx): "Precios globales de químicos industriales y empaque".
- **Entidad única (spec §2)**: `product` — una fila por SKU comercial de un supplier. NO hay entidad `supplier` separada; los campos `supplier_*` viven denormalizados en cada product row (ver §9 para discusión).
- **Fuente canónica**: `https://www.alibaba.com/trade/search?SearchText={term}&has4Tab=true` (listing) + `/product-detail/{slug}_{PID}.html` (detalle).
- **País proxy default**: `CN` (spec §3 genomma lab). El middleware NO inyecta `supplier_country="CN"` en los seeds por default (ver §3); es el caller quien lo pide explícitamente si quiere restringir.
- **SPA**: listing y detail se pintan tras ejecutar JS; proxy HTTP plano no sirve. El JS corre bajo BrightData Scraping Browser (wrapper del DCA / del Studio).
- **Bot-check conocido**: h1 con texto "Access Denied" / CF challenge puede pasar el `wait()` silenciosamente; el scraper JS debe detectar + flagear `captcha_detected` / `rate_limit_blocked`, y el middleware cuenta esos flags para `BLOCK_SATURATION` (§5).

Cadencia de corridas esperada: on-demand (usuario dispara desde el agente) o semanal. No hay cron declarado en este repo — la decide el repo de agentes.

---

## 2. Contrato público del paquete

### 2.1 `trigger(inputs) -> dict`

```python
async def trigger(inputs: AlibabaInputs | dict | None = None) -> dict:
    """
    Returns: {"job_id": str, "eta_seconds": int}
    Nunca raisea — errores van por shape {"status": "failed", "error": {...}}.
    """
```

Módulo-level; internamente construye un `AlibabaClient()` efímero, llama `trigger`, cierra el cliente HTTP y devuelve. Estateless.

### 2.2 `get_result(job_id) -> dict`

```python
async def get_result(job_id: str) -> dict:
    """
    Returns un envelope con shape:
      {"status": "running",  "progress_pct": int}
      {"status": "done",     "data": <Envelope>}
      {"status": "failed",   "error": {"code": str, "message": str, "retriable": bool, "details"?: {...}}}
    """
```

### 2.3 Inputs — `AlibabaInputs` (pydantic v2)

```python
class AlibabaInputs(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    search_terms: list[str] | None = None           # None/[] => 5 seeds canónicos
    max_pages: int = 5                              # 1..10 (vendor clampea a 10)
    supplier_country: str | None = None             # ISO-2 filter opcional
    min_price: float | None = None                  # ge=0; None => scraper default 1
    max_price: float | None = None                  # ge=0; None => scraper default 10000
    max_products: int = 2000                        # 1..10000, post-download
    mode: Literal["incremental","full-refresh"] = "incremental"
```

- `extra="forbid"`: un key desconocido dispara `INVALID_INPUTS` sin llamar BrightData (ver `test_invalid_inputs_unknown_key`).
- `search_terms` mapea 1:1 a seeds del trigger. Cap implícito por la lista (se asume <20 en uso típico; no hay validador duro de tamaño de lista, la salvaguarda está en cada item: `min_length=1, max_length=120`).
- `mode` NO es consumido por el scraper — es una hint al agents repo sobre si honrar su cache (dedup por `product_url + scraped_date`, spec §10).

### 2.4 Envelope normalizado (cuando `status == "done"`)

```python
{
  "source": "alibaba",
  "scraped_at": "2026-04-21T15:30:00Z",
  "inputs": { ... echo de inputs efectivos validados ... },
  "data": [ { ... product row (spec §2 + §5 + middleware metadata) ... } ],
  "meta": {
    "rows": int,                                   # total rows recibidos de BrightData
    "emitted": int,                                # rows que pasaron a data[]
    "emitted_by_entity": {"product": int},         # forward-compat multi-entidad
    "skipped_by_reason": {                         # contadores de skip
      "non_dict_row": int,                         # defensive: rows no-dict
      "unknown_entity": int,                       # rows sin signal de entidad
      "max_products_cap": int                      # rows recortadas por el cap
    },
    "blocked": int,                                # rows con captcha/rate-limit flag
    "missing_price": int,                          # rows con price_min_usd=null
    "unmapped_country": int,                       # rows con country_unmapped flag
    "errors": int,                                 # rows malformadas (non-dict)
    "started_at": "...",
    "ended_at": "..."
  }
}
```

El schema de `data[]` (campos de `product`) está fijado en `docs/specs/scrapers/alibaba.md` §2 + §5 — **inmutable**. Siempre emitir todas las claves: `null` explícito para atómicos faltantes, `[]` para listas faltantes (scraper_flags). Ver `models.py::ProductRow` y `PRODUCT_FIELDS`.

**Citación literal del §2 de la spec** (16 keys de entidad `product`):

```json
{"product":["product_name_clean","product_name_original","type","category","price_raw","price_min_usd","price_max_usd","price_unit","price_normalized_per_kg","moq_quantity","moq_unit","supplier_name","supplier_country","supplier_verified","product_url","scraped_date"]}
```

Más 3 opcionales del §5 (reputación):

```
supplier_rating, supplier_reviews_count, supplier_response_rate
```

Más metadata middleware-added:

```
entity = "product"     (discriminador forward-compat)
site   = "alibaba"     (spec §1, inyectado, no sobreescribible)
scraper_flags: list[str]   (allow-list §10 + "country_unmapped" del middleware)
```

`ProductRow.model_config` usa `extra="allow"` — vendor fields como `cas_number` / `purity` pasan verbatim pero NO son parte del contrato.

### 2.5 `TOOL_SCHEMA` (JSON Schema consumido por el repo de agentes)

Exportado en `tool_schema.py`:

```python
TOOL_SCHEMA: list[dict] = [
    {"name": "alibaba_trigger",    "description": "...", "input_schema": {...}},
    {"name": "alibaba_get_result", "description": "...", "input_schema": {...}},
]
```

Dos tools separadas (trigger + get_result), `additionalProperties: false` en ambos schemas. Escrito a mano (no `model_json_schema()`) para evitar `$refs` y superficie implícita.

---

## 3. Traducción inputs públicos ↔ seed JS

El scraper JS espera un array con objetos de forma fija; el middleware construye **un seed por `search_term`**.

### 3.1 Construcción del seed

En `client.py::_build_brightdata_inputs`:

```python
for term in (public_inputs.search_terms or DEFAULT_SEARCH_TERMS):
    seed = {
        "url": search_url(term),                  # URL completa pre-construida
        "search_keyword": term,                   # fallback si url parseo falla
        "max_pages": public_inputs.max_pages,
        "min_price": min_price_resolved,          # always emitted
        "max_price": max_price_resolved,          # always emitted
    }
    if public_inputs.supplier_country:
        seed["supplier_country"] = public_inputs.supplier_country
    seeds.append(seed)
```

### 3.2 Encoding de URL

```python
# config.py::search_url
def search_url(term: str) -> str:
    encoded = str(term).strip().replace(" ", "+")
    return f"https://www.alibaba.com/trade/search?SearchText={encoded}&has4Tab=true"
```

**Regla dura**: espacios → `+`, NO `%20`. Alibaba usa `+` en sus propias querystrings; igualarlo mantiene la dedup downstream por URL canónica. Otros caracteres especiales no se escapan — el scraper JS tolera los terms que razonablemente llegan como seeds de negocio ("industrial chemicals", "sodium hydroxide industrial").

### 3.3 Seeds canónicos default (spec §3)

```python
DEFAULT_SEARCH_TERMS = (
    "industrial chemicals",                         # químico general
    "industrial packaging drums barrels",           # empaque (Packaging_Drum)
    "sodium hydroxide industrial",                  # Alkali/NaOH
    "hydrochloric acid industrial",                 # Acid/HCl
    "chemical packaging containers",                # empaque (Packaging_Container)
)
```

`search_terms=[]` o `None` → se aplica la tupla default (5 seeds). `search_terms=["x"]` → 1 seed.

### 3.4 `max_products` NO va en el seed

Spec §10 pide un hard cap sobre el emitted — el scraper JS no tiene un `input.max_products`. El middleware aplica el cap **post-download** en `_build_envelope` (después de fetch de la snapshot), incrementando `skipped_by_reason.max_products_cap` por cada fila clipeada. El test `test_input_translation_max_products_not_in_seed` garantiza esta regla.

### 3.5 `supplier_country` — inyección condicional

Si el caller pasa `supplier_country="CN"`, se inyecta en cada seed y el JS filtra Stage-1 por país (caída silenciosa si el flag del card no matchea). Si no pasa, **no se inyecta**: el middleware no pone CN por default — si lo hiciera, todos los non-CN suppliers desaparecerían del envelope y el agents-repo perdería la capacidad de consultar precios globales. El `country()` a nivel de **proxy** (spec §3) es otra cosa y la maneja el DCA/Studio setup, no el middleware.

---

## 4. Post-procesamiento en `_build_envelope`

Pipeline por cada row recibida de BrightData:

### 4.1 Defensiva (non-dict rows)

```python
if not isinstance(raw, dict):
    skipped_by_reason["non_dict_row"] += 1
    errors += 1
    continue
```

### 4.2 Clasificación de entidad

`_classify_entity(raw)` devuelve `"product"` o `None`. Hoy spec §2 declara solo `product`; la función tolera:

- `raw["entity"] == "product"` (discriminador explícito)
- `raw["_entity"] == "product"` (discriminador underscore-prefixed)
- `raw["type"] == "product"` (type como tag, NO como enum §9)
- Presencia de cualquier señal de producto: `product_url`, `url`, `product_name_clean`, `product_name_original`, `cleaned_product_name`, `name_raw`.

**Nota sutil**: `type` en spec §9 puede ser `"chemical"` o `"packaging"` — esos valores **no** son discriminadores (si lo fueran, rompería el forward-compat con otras entidades). Sólo `type="product"` dispara match explícito.

Sin señal → `skipped_by_reason["unknown_entity"] += 1`.

### 4.3 Alias rename (vendor → spec §2)

`_apply_aliases(raw, PRODUCT_ALIASES)`:

```python
PRODUCT_ALIASES = {
    # vendor-native (actual parser_code.js) → spec §2
    "cleaned_product_name":   "product_name_clean",
    "minimum_order_quantity": "moq_quantity",
    # defensive variants (otros scrapers del repo, código histórico)
    "name_raw":         "product_name_original",
    "name_clean":       "product_name_clean",
    "url":              "product_url",
    "moq":              "moq_quantity",
    "moq_unit_raw":     "moq_unit",
    "supplier":         "supplier_name",
    "country":          "supplier_country",
    "verified":         "supplier_verified",
    "rating":           "supplier_rating",
    "reviews_count":    "supplier_reviews_count",
    "response_rate":    "supplier_response_rate",
}
```

**Precedencia**: si raw trae tanto el alias source como el target canónico, gana el target. El alias source queda en el row (via `extra="allow"`) pero no pisa.

Por qué ambos sets de alias: el vendor `parser_code.js` actual emite los primeros dos (`cleaned_product_name`, `minimum_order_quantity`). Los defensive variants cubren (a) el código v1+ del `analista-de-scrapers` cuando reescriba el parser para alinearse con §2 nombres, (b) legacy payloads que nunca desaparecen totalmente, (c) paralelismo con made-in-china cuyo vendor usa shortnames similares.

### 4.4 Ensure §2/§5 keys present

```python
for key in PRODUCT_FIELDS:
    if key not in aliased:
        out[key] = [] if key in PRODUCT_LIST_FIELDS else None
```

Garantiza que cada row tenga exactamente 22 keys base (16 §2 + 3 §5 + `entity` + `site` + `scraper_flags`). Extra keys del vendor (`cas_number`, `purity`) se forwardean pero no son parte del contrato.

### 4.5 `supplier_country` → ISO-2

`config.py::country_to_iso2(value)` devuelve `(iso | None, unmapped: bool)`:

- Fast path: ya es ISO-2 (2 letras upper alpha) → passthrough `(value, False)`.
- Mapeo vía `COUNTRY_TO_ISO2` (~60 entradas, lowercase keys): "china" → "CN", "united states" → "US", "germany" → "DE", etc.
- `None` / vacío / whitespace → `(None, False)` (missing data, NOT unmapped).
- String no matcheable → `(None, True)` + el row gana flag `country_unmapped`.

Por qué la tabla vive local en Python y no external (pycountry / babel):

- El middleware es stateless y zero-runtime-deps más allá de httpx/pydantic/structlog.
- La cobertura necesaria (~60 países de supplier frecuente en Alibaba) cabe sin mantenimiento significativo.
- Unmapped lands visible (`country_unmapped` flag + `meta.unmapped_country` counter); la tabla crece por PR cuando aparece un país nuevo.

### 4.6 Flag merge

- `scraper_flags` del raw se respeta verbatim (nunca se remueve un flag que el JS puso).
- Si coerción añade `country_unmapped`, se appendea sin duplicar.
- Tipo: si el raw trajo un string en lugar de list (defensive), se envuelve en `[string]`.

### 4.7 Inyección de metadata (NO sobreescribible)

```python
out["entity"] = "product"
out["site"]   = "alibaba"    # spec §1 "Campo site fijo alibaba"
```

Si el raw viene con `site="evil.com"`, el middleware lo pisa. Test `test_coerce_product_site_cannot_be_overridden`.

### 4.8 Counters del `meta`

Por row emitida:

- `blocked++` si `scraper_flags` contiene `captcha_detected` o `rate_limit_blocked`.
- `missing_price++` si `price_min_usd is None` (pre-cap).
- `unmapped_country++` si `scraper_flags` contiene `country_unmapped`.

Estos counters alimentan las saturation checks del §5.

### 4.9 Cap `max_products`

```python
if len(emitted) >= max_products:
    skipped_by_reason["max_products_cap"] += 1
    continue
```

Clipping determinístico post-counters (las saturations se computan sobre los emitted definitivos, lo cual es correcto: si `max_products=2` y los primeros 2 rows son blocked, BLOCK_SATURATION = 2/2 = 100%, fail loud).

### 4.10 Pydantic coercion opcional

Se intenta instanciar `ProductRow(**out)` para validar tipos. Si falla (`ValidationError` por p.ej. un `price_min_usd` string en vez de float), se devuelve el dict manual sin romper el run — mejor tener la row visible con `scraper_flags` que perderla. El rationale: el middleware no es el validador autoritario de tipos; el JS parser tiene que salir correcto.

---

## 5. Catálogo de errores

### 5.1 Base (compartidos cross-scraper — `middlewares/core/errors.py`)

| code | retriable | cuándo |
|---|---|---|
| `SITE_BLOCKED` | false | BrightData reporta bloqueo sostenido (HTTP 451 al trigger) |
| `STRUCTURE_CHANGED` | false | no se raisea en alibaba hoy — reservado |
| `TIMEOUT` | true | wall-time budget agotado sin estado final (consumidor lo decide) |
| `INVALID_INPUTS` | false | validación pydantic falla, o env vars no pobladas, o `job_id` vacío |
| `BRIGHTDATA_ERROR` | true | 5xx / transport / JSON malformado / poll "failed" |
| `UNKNOWN` | false | default fallback del catálogo |

Mapping HTTP-status → code vive en `core/transports/{v3,dca}.py` + resumen en `core/errors.py`.

### 5.2 Extensión local (alibaba-specific, `client.py::ALIBABA_ERROR_CODES`)

**No se mutan los códigos base** — se extienden en un dict local del paquete. Dos códigos:

| code | retriable | cuándo | threshold |
|---|---|---|---|
| `BLOCK_SATURATION` | false | `blocked / emitted_product > 0.5` en post-process | spec §2 "h1 bot-check", §10 flags `captcha_detected` / `rate_limit_blocked` |
| `PRICE_MISSING_SATURATION` | false | `missing_price / emitted_product > 0.7` | **nuevo para categoría Precios** — Alibaba sin precio no tiene valor |

`BLOCK_SATURATION` es el hermano de `cosme::BLOCK_SATURATION` y de `cosmetics-design::PAYWALL_SATURATION`. `PRICE_MISSING_SATURATION` es **inédito** — la categoría Precios obliga a fallar loud si el envelope no trae datos comparables; RFQ-gated suppliers + selector drift en `.price-item` son las causas típicas. Thresholds en `config.py`:

```python
BLOCK_SATURATION_THRESHOLD = 0.5
MISSING_PRICE_SATURATION_THRESHOLD = 0.7
```

### 5.3 Mapeo HTTP → code (resumen relevante para alibaba)

| condición | code |
|---|---|
| v3/dca 5xx | `BRIGHTDATA_ERROR` |
| 451 trigger | `SITE_BLOCKED` |
| 401/403 | `INVALID_INPUTS` (clave mal, resource id ajeno) |
| 4xx trigger | `INVALID_INPUTS` |
| 404 poll | `INVALID_INPUTS` (job_id no existe) |
| 4xx poll/download | `BRIGHTDATA_ERROR` |
| JSON malformado | `BRIGHTDATA_ERROR` |
| v3 sin `snapshot_id` | `BRIGHTDATA_ERROR` |
| DCA "expired" / "deleted" | `INVALID_INPUTS` |
| poll → "failed" | `BRIGHTDATA_ERROR` |

El middleware SOLO normaliza — no decide retry ni alarmas. Eso lo hace el agents repo.

---

## 6. Límites operativos

| knob | valor | origen |
|---|---|---|
| Seeds por trigger | hasta 20 terms (soft — no validator duro); 5 default | spec §3, middleware config |
| `max_pages` por seed | 1..10, default 5 | vendor interaction_code clampea a 10 |
| `max_products` post-download | 1..10000, default 2000 | middleware, spec §10 |
| `min_price` / `max_price` | default 1 / 10000 USD | spec §3 |
| `eta_seconds` hint | 600 (10 min) | estimación para 5 terms × 5 pages × ~40 cards |
| Timeout total BrightData | 15 min | spec §2 ("timeout_minutes=15") — lo maneja BrightData side |
| Poll interval | 10s default | spec §2, vive en `core/transports/` |
| Retry policy | pendiente | spec §2 (backoff 2s/4s/8s) no implementado; consumidor decide |
| HTTP timeout per-call | 60s | `BaseScraperClient.DEFAULT_HTTP_TIMEOUT` |

`eta_seconds=600` se devuelve en `trigger()`; es una hint, no un hard guarantee. La corrida típica observada en la spec sugiere 8-15 min.

---

## 7. Convenciones de naming

### 7.1 Tool names

```
alibaba_trigger
alibaba_get_result
```

Pattern: `{source}_{verb}`. Consistente con `cosmetics_design_trigger` / `cosmetics_design_get_result`.

### 7.2 Env vars

| var | uso |
|---|---|
| `BRIGHTDATA_API_KEY` | bearer token, común a todos los scrapers |
| `BRIGHTDATA_DATASET_ID_ALIBABA` | resource id v3 (`gd_...`) |
| `BRIGHTDATA_COLLECTOR_ID_ALIBABA` | resource id DCA (`c_...`) |

Pattern: `BRIGHTDATA_{DATASET|COLLECTOR}_ID_{SCRAPER_UPPER}`. `ALIBABA` sin underscore interno porque el source name es una sola palabra; `COSMETICS_DESIGN` sí lleva underscore (sigue patrón de cosmetics-design-handoff §0.1).

**Divergencia con spec**: el spec genomma lab §2 menciona `BRIGHTDATA_COLLECTOR_ID` **sin sufijo per-scraper**. Middleware usa el sufijado. Razón: evitar colisión cuando el agents repo monte múltiples scrapers en el mismo proceso. Ratificar en §9 — si el usuario prefiere sin sufijo, hay que actualizar tanto middleware como spec §2.

### 7.3 Source / site / entity

- `source = "alibaba"` (envelope-level, hyphen-free porque el folder es `alibaba`).
- `site   = "alibaba"` (row-level, spec §1 "campo fijo").
- `entity = "product"` (row-level, forward-compat).

### 7.4 Package name

`middlewares/alibaba/` (underscore-safe trivialmente porque no hay hyphen en el source). Scraper JS sigue en `scrapers/alibaba/`.

---

## 8. Dependencias del scraper JS (gap crítico — acción para `analista-de-scrapers`)

**Este es el gap más importante de este handoff.** El middleware está implementado asumiendo que el JS parser emite el shape §2 completo (+ §5 opcionales). El vendor JS actual emite **solo 10 campos**, **faltan 8 del §2** + **3 del §5**.

### 8.1 Shape actual del vendor (`scrapers/alibaba/vendor/sc_code/parser_code.js` líneas 53-64)

```js
return {
  cleaned_product_name,    // aliased a product_name_clean (middleware OK)
  product_url,             // OK (§2)
  supplier_name,           // OK (§2)
  price_raw,               // OK (§2)
  price_min_usd,           // OK (§2) — JS lo emite, asume ya convertido a USD
  price_max_usd,           // OK (§2)
  price_unit,              // OK (§2)
  minimum_order_quantity,  // aliased a moq_quantity (middleware OK)
  cas_number,              // NOT §2 — vive via extra="allow", no contractual
  purity                   // NOT §2 — idem
};
```

### 8.2 Faltantes del §2 (8 campos — middleware los completa con null hoy)

| campo | cómo derivar | responsabilidad |
|---|---|---|
| `product_name_original` | Stage 2 detail: `h1.title-first-column` con fallbacks `.product-title h1`, `h1[class*="title"]`, `h1` (spec §4) | JS |
| `type` | `classify()` sobre clean_name → `"chemical"` \| `"packaging"` (spec §9) | JS |
| `category` | `classify()` sobre clean_name → enum §9 (Alkali, Acid, Packaging_Drum, etc.) | JS |
| `price_normalized_per_kg` | `parse_price` regla 13: si unit=kg → price_min_usd; ton/mt → /1000; L/piece/set → null (spec §8) | JS |
| `moq_unit` | actualmente parseado parcialmente por regex de la quantity string; debería ser enum `{kg, ton, piece, ...}` explícito (spec §4) | JS |
| `supplier_country` | Stage 1: `.country-flag img` src (ISO-2 directo); Stage 2: `.supplier-country` text con fallbacks (spec §4) | JS emite, middleware normaliza a ISO-2 |
| `supplier_verified` | bool desde badge "Gold Supplier" / "Verified" en supplier card (selector pendiente en spec §4) | JS |
| `scraped_date` | runtime date `YYYY-MM-DD` (spec §4) — trivial de agregar en el parser | JS |

### 8.3 Faltantes del §5 (3 campos reputación — opcionales)

| campo | derivación | estado |
|---|---|---|
| `supplier_rating` | selector de estrellas en supplier card (spec §5: "selector pendiente") | JS — selector pendiente en la propia spec |
| `supplier_reviews_count` | int desde supplier card (spec §5: "selector pendiente") | JS |
| `supplier_response_rate` | string "98%" (spec §5: "selector pendiente") | JS |

### 8.4 Acción concreta para `analista-de-scrapers`

- Crear `scrapers/alibaba/sc_browser/interaction_code_v1.js` + `parser_code_v1.js` (copia verbatim del vendor) — primer paso del flujo Etapa 2.
- Iterar a v2 cerrando los 8 gaps del §2 arriba. `category` + `type` derivan de `classify()` vía keywords (spec §9) — ya definido en la prosa.
- Iterar a v3 cerrando los 3 gaps del §5 cuando los selectores estén definidos en la spec (hoy dicen "selector pendiente").
- Documentar cada run en `scrapers/alibaba/results/registry.md`.

**Hasta que eso ocurra, el envelope que el middleware devuelve tiene los 8 campos §2 faltantes como `null` y los 3 §5 como `null`.** El agent repo recibe un envelope shape-válido pero con cobertura incompleta para analítica.

### 8.5 Fixture hand-crafted (no hay run real)

`middlewares/alibaba/tests/fixtures/alibaba_snapshot_s_demo01.json` NO viene de una snapshot real — fue fabricado por el agente middleware con 6 rows que cubren el row-scenario map documentado en `fixtures/README.md`. Las 3 primeras rows usan vendor-native keys (`cleaned_product_name`, `minimum_order_quantity`); las otras 3 usan spec §2 names — para ejercitar el alias path en tests. El `TODO` del fixture README indica reemplazar con snapshot real cuando el usuario corra el scraper por primera vez.

---

## 9. Preguntas abiertas

Ninguna bloquea la funcionalidad del middleware; todas pueden resolverse en un follow-up PR.

### 9.1 ¿Promover `supplier` a entidad separada?

**Estado actual**: todos los campos `supplier_*` viven denormalizados en cada `ProductRow`. Spec §2 declara solo `product`. Un supplier con 50 SKUs aparece 50 veces con los mismos `supplier_name` / `supplier_country` / `supplier_rating`.

**Argumentos a favor de separar**:
- Normalización del warehouse downstream (Snowflake) más limpia.
- Reputación (rating / reviews_count / response_rate) se actualiza a nivel supplier, no a nivel producto — duplicación es desinformación.
- Alineación con cosme (que sí tiene `supplier` aparte).

**Argumentos en contra**:
- Spec §2 de alibaba lo declara denormalizado explícitamente (prompt v2 §1 "output plano, sin nested objects").
- Un supplier en alibaba no existe fuera de sus productos — no hay URL pública autónoma del supplier que valga como PK.
- Requiere cambio de spec §2 (NO es cambio de versión del parser; es cambio de contrato). Dedupe en JS a nivel `supplier_name` + `supplier_country` sería costoso y frágil.

**Plumbing del middleware ya está listo**: `_classify_entity` tolera forward-compat; `_build_envelope` ya trackea `emitted_by_entity`; añadir `SupplierRow` en `models.py` + un clasificador adicional en `client.py` es una jornada de trabajo SIN tocar `core/`.

**Decisión a tomar por producto/data-eng**, no por middleware — afecta el shape que el agents repo consume.

### 9.2 ¿Conversión de moneda (FX) en JS o en Python?

**Estado actual**: spec §8 declara `EXCHANGE_RATES` como tabla fija en el JS (refresh pendiente). El middleware confía en `price_min_usd` / `price_max_usd` tal como el JS los emite y NO re-convierte. Si el JS emite en moneda local (ej `price_raw="€1.20/kg"` con `price_min_usd=1.20` en EUR no USD), el middleware no lo detecta y el dato es incorrecto silenciosamente.

**Trade-off**:
- **FX en JS** (status quo per spec §8): el scraper corre con rates hardcoded; refresh manual. Tabla `EXCHANGE_RATES` centralizada en un module del scraper.
- **FX en Python** (middleware): middleware detecta moneda del `price_raw` + aplica rate fresco (ECB daily feed). Cost: dep nueva (httpx call al feed), complejidad de cache del rate, nuevo error `FX_RATE_UNAVAILABLE`.

**Recomendación del handoff**: FX en JS por ahora (spec intacta); marcar TTL al cache de rates (ej 7 días) + flag `price_fx_needed` (ya está en la allow-list §10) para surface refresh-required a nivel row. Si se observa drift significativo, migrar a Python en un segundo PR.

### 9.3 ¿`type` y `category` Literal estrictos o string libre?

**Estado actual**:

```python
type: Literal["chemical", "packaging"] | None = None
category: str | None = None
```

Spec §9 lista 10 categorías canónicas + valores implícitos ("Glycol", "Silicate", "Polymer", "Corrosion", "Bleach", "Fertilizer") que no aparecen en el enum del §4 — son sub-categorías químicas que `classify()` asigna. Total observado: ~16 valores.

**Middleware eligió `str`** para `category` porque:
- Spec §4 lista 10 enums; spec §9 agrega ~6 más implícitos.
- Flexibilidad para que el scraper agregue una categoría nueva sin romper pydantic.
- La validación real de categorías canonicals vive en el downstream warehouse (ETL).

**Argumento para Literal estricto**: detectar typos del JS parser (ej `"Alkalli"` en lugar de `"Alkali"`) en el boundary del middleware. Pero eso rompe cuando el parser mete una categoría legítima nueva — el agents repo caería en un ValidationError por algo que no es un bug, solo es nuevo.

**Decisión**: quedarse con `str` para `category`; mantener `Literal` para `type` (sólo 2 valores, enum estable). Ratificar.

### 9.4 Naming `BRIGHTDATA_COLLECTOR_ID_ALIBABA` vs `BRIGHTDATA_COLLECTOR_ID`

**Estado actual**: middleware usa `BRIGHTDATA_COLLECTOR_ID_ALIBABA` (per-scraper). Spec §2 genomma lab menciona literalmente `BRIGHTDATA_COLLECTOR_ID` sin sufijo.

**Problema del naming sin sufijo**: cuando el agents repo monta múltiples scrapers (alibaba + made-in-china + indiamart juntos), `BRIGHTDATA_COLLECTOR_ID` colisiona entre los tres. Cada scraper necesita su propio resource id.

**Recomendación**: ratificar per-scraper naming; actualizar spec §2 para reflejar el patrón `BRIGHTDATA_COLLECTOR_ID_{SCRAPER_UPPER}`. Esto es el patrón que cosmetics-design ya usa (`BRIGHTDATA_DATASET_ID_COSMETICS_DESIGN`).

### 9.5 Fixture real

Reemplazar `alibaba_snapshot_s_demo01.json` por un snapshot real cuando el usuario corra el scraper por primera vez contra BrightData. Comando en `fixtures/README.md`. Una vez real, el fixture pasa a cubrir los escenarios observados (no los ficticios actuales) y los tests `test_get_result_done_from_fixture`, `test_envelope_shape`, `test_product_keys_complete` cubren la realidad del dataset.

---

## 10. Qué NO hacer

- **No reimplementar parsing en Python**. `cleaned_product_name`, `price_raw → price_min_usd`, `classify()`, `clean_name` viven en el JS parser. Middleware solo alias-renames y normaliza country.
- **No modificar el schema de `product`**. Fijado en spec §2. Nuevas entidades (si se aprueba §9.1) requieren cambio de spec.
- **No inyectar `supplier_country="CN"` por default en los seeds**. Rompería la cobertura global de precios (ver §3.5).
- **No hardcodear `BRIGHTDATA_API_KEY` ni el resource id**. Ambos viven en env vars.
- **No gestionar cache / DB / ServiceRegistry**. Eso vive en el agents repo (`scraper_runs` PostgreSQL + dedup por `product_url + scraped_date`).
- **No tratar `type="chemical"` o `type="packaging"` como discriminadores de entidad** — son valores del enum §9, no del `entity` discriminator (ver §4.2).
- **No usar MCP** — middleware es Python plano.
- **No saltar las saturation checks** — si `BLOCK_SATURATION` o `PRICE_MISSING_SATURATION` dispara, el envelope se cambia a `{"status": "failed", ...}` y NO se devuelven rows parciales.

---

## 11. Entregables (estado al cierre de este handoff)

1. ✅ `middlewares/alibaba/__init__.py` — exports `trigger`, `get_result`, `TOOL_SCHEMA`, `AlibabaClient`, `AlibabaInputs`, `ProductRow`.
2. ✅ `middlewares/alibaba/client.py` — `AlibabaClient(BaseScraperClient)`, `trigger`, `get_result`, `build_envelope_for_rows`, `_coerce_product`, `_classify_entity`, saturation checks.
3. ✅ `middlewares/alibaba/models.py` — `AlibabaInputs`, `ProductRow`, `PRODUCT_FIELDS`, `PRODUCT_LIST_FIELDS`, `PRODUCT_ALIASES`.
4. ✅ `middlewares/alibaba/config.py` — env var resolution, `COUNTRY_TO_ISO2`, thresholds, default seeds/prices, `search_url()`.
5. ✅ `middlewares/alibaba/tool_schema.py` — 2 tools.
6. ✅ `middlewares/alibaba/tests/` — `conftest.py`, `test_client.py` (~40 tests), `fixtures/alibaba_snapshot_s_demo01.json` (hand-crafted).
7. ⏳ Fixture real — pendiente primera corrida.
8. ⏳ `docs/fase3/README.md` — actualizar "Handoffs por scraper" listando alibaba como cerrado con fecha y commit SHA.
9. ⏳ Resolución de §9 — follow-up PR.
10. ⏳ **Scraper JS v1+** cerrando los 11 gaps del §8 (8 §2 + 3 §5) — bloqueo para cobertura real del envelope. Trabajo de `analista-de-scrapers`.
