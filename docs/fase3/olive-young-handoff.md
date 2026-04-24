# Handoff Fase 3 — olive-young

> **Destino del trabajo**: `middlewares/olive_young/` (este repo).
> **Consumidor**: repo de agentes. Importa este paquete como dependencia y
> encima coloca `ServiceRegistry`, persistencia (`scraper_runs` en PostgreSQL),
> cache TTL y declaración de tool al agente.
> **Agente responsable**: `middleware-python`.
>
> **Post-facto (2026-04-21)** — este handoff documenta un middleware **ya
> implementado**. La implementación vive en `middlewares/olive_young/` y
> siguió el patrón del POC `cosmetics-design` y del sibling multi-entidad
> `cosme`. El handoff actúa como contrato de referencia para el repo de
> agentes y como apoyo para las próximas iteraciones cuando el scraper JS
> exista.
>
> **Dual-mode** habilitado vía `middlewares/core/transports/` (Datasets v3
> + DCA legacy). Ver `docs/fase3/middleware-dual-mode.md`. Contrato público
> (`trigger` / `get_result` / `TOOL_SCHEMA`) idéntico a los demás middlewares.

---

## 0. Inputs ratificados + preguntas abiertas

Estado previo al cierre del handoff:

1. **Resource id de BrightData** — dos env vars soportadas (dual-mode). El
   middleware no conoce el id todavía; lo resuelve en runtime vía
   `middlewares.olive_young.config.resolve_mode_and_id`.
   - `BRIGHTDATA_DATASET_ID_OLIVE_YOUNG` (formato `gd_...`) si el scraper ya
     está migrado a Scraper Studio.
   - `BRIGHTDATA_COLLECTOR_ID_OLIVE_YOUNG` (formato `c_...`) si todavía vive
     como colector DCA legacy.
   Si ambos están seteados, **v3 gana**. El middleware trata el id como
   opaco — no valida prefijos.
2. **Env var `BRIGHTDATA_API_KEY`** — única, compartida cross-scraper. Se
   consume vía `BaseScraperClient._ensure_credentials` al momento del
   trigger, no al import. Si falta, el trigger devuelve
   `{"status": "failed", "error": {"code": "INVALID_INPUTS", ...}}` sin
   llamar a BrightData.
3. **Nombre del paquete Python**: `middlewares/olive_young/` (underscore).
   El scraper JS sigue en `scrapers/olive-young/` con hyphen. El campo
   `source` del envelope es `"olive-young"` (canónico con hyphen, el del
   xlsx y del spec).

Decisiones que este documento **ratifica**:

4. **Multi-entidad con discriminador `entity`** — spec §2 emite tres
   entidades (`ranking`, `product`, `brand`) en un solo `data[]`
   heterogéneo. Cada row lleva un campo `entity: "ranking" | "product" |
   "brand"`. Modelos pydantic (`RankingRow` / `ProductRow` / `BrandRow`)
   con `ConfigDict(extra="allow")` para que los §4-§6 extras pasen
   verbatim. Heurística de clasificación en
   `client._classify_entity(raw)` — prioridad: discriminador explícito
   (`entity` / `_entity` / `type`) → `ranking_id` presente → `rank + prdt_no + region` → `brand_no + total_in_rankings + sin prdt_no` → `prdt_no + category_ids`. Misma shape que
   `middlewares.cosme`.

5. **Aliases §4-§6 prosa → §2 short** — el spec §2 usa nombres cortos
   (`region`, `cat_id`, `name_en`, `promo`, `url`, `total_in_rankings`,
   `avg_rank`). Los §4-§6 prosa y el parser JS usan nombres largos
   calificados (`region_code`, `category_id`, `product_name_en`,
   `promotion_name`, `product_url`, `brand_total_products_in_rankings`,
   `brand_avg_rank`) para desambiguar el output multi-entidad. El
   middleware renombra **al emitir** en `client._apply_aliases` via los
   dicts `RANKING_ALIASES` / `PRODUCT_ALIASES` / `BRAND_ALIASES` en
   `models.py`. Regla de colisión: si el raw ya trae la clave canónica
   (`url`) con valor no-null, gana el canónico y el alias (`product_url`)
   se deja como extra key. Nunca se inventan valores.

6. **`BLOCK_SATURATION` como código local** del middleware — no vive en
   `core/errors.py`. Definido en
   `client.OLIVE_YOUNG_ERROR_CODES["BLOCK_SATURATION"]` y disparado por
   `client._maybe_block_saturation` cuando **>50% de las ranking rows
   emitidas** llevan `cloudflare_challenge` o `api_400` en `scraper_flags`.
   Gate **solo sobre ranking rows** porque es la señal más abundante por
   run (≈2300 rows brutos pre-dedup, 11 KR × 100 + 12 USA × 100) y porque
   los failure modes dominantes son exactamente Cloudflare silente (spec
   §2 / `errors.md` E2) y 400 de la ranking API (`errors.md` E3). Products
   y brands son **passthrough** — no entran al denominador.

7. **Dual-mode `API_MODE`** — resuelto por `config.resolve_mode_and_id()`
   al construir el cliente. Precedencia v3 > DCA. Si ninguna env var está
   seteada, el cliente queda en `api_mode="v3"` por defecto y el error
   dispara en el primer `_ensure_credentials()` del trigger con el
   `CREDENTIAL_HINT` que nombra las dos env vars.

8. **Inputs públicos** — se fijan en `OliveYoungInputs`:
   - `regions: list[Literal["KR", "USA"]]` (min 1, max 2, default
     `["KR", "USA"]`).
   - `max_products: int ∈ [1, 3000]` (default 1000, cap post-download).
   - `max_brand_visits: int ∈ [0, 100]` (default 20, cap para visitas
     brand-page).
   - `include_rankings: bool = True`, `include_products: bool = True`,
     `include_brands: bool = True` (filtros post-download).
   - `categories: list[str] | None = None` (whitelist opcional de
     `category-id`).
   - `mode: Literal["incremental", "full-refresh"] = "incremental"`
     (hint para el cache TTL del repo de agentes — el middleware sólo lo
     reenvía en `envelope.inputs`).

   **No hay `window_days` ni `year`** — olive-young es catálogo por
   región, no una ventana temporal de artículos o reviews.

9. **`max_products` post-download** — aplicado solo a rows con
   `entity == "product"` en `_build_envelope`. Ranking y brand rows no
   se recortan (son tablas de referencia pequeñas: ~2300 rankings y
   ≤20 brands por run).

10. **Seed único a BrightData** — `_build_brightdata_inputs` emite una
    lista con un solo dict:
    ```python
    {
      "url": RANKINGS_API_HOST,                 # entry point conceptual
      "regions": ["KR", "USA"],                 # público → scraper
      "max_brand_visits": 20,                   # público → scraper
      "categories": ["..."]                     # opcional, si pasó whitelist
    }
    ```
    `max_products` **no se forwardea** al scraper (es clipping
    post-download, no knob del scraper).

**Preguntas abiertas** — ver §9 abajo.

---

## 1. Contexto del scraper

- **Nombre**: `olive-young` (carpeta JS + envelope `source`) /
  `olive_young` (paquete Python).
- **Categoría**: I+D (K-beauty Korea trends & bestsellers, **no precios**).
- **Proveedor**: CJ Group.
- **Entidades**: tres — `ranking`, `product`, `brand`. Multi-entidad en un
  único `data[]` heterogéneo.
- **Fuentes canónicas**:
  - API rankings: `https://product-ranking-service.oliveyoung.com/v1/pages/ranking/sales/{categories,products}`
    (regiones `KR` y `USA`, sin CSRF).
  - Detail Vue + CSRF: `https://global.oliveyoung.com/product/detail?prdtNo={GA...}`
    (Scraping Browser obligatorio — `errors.md` E6).
  - Brand page: `https://global.oliveyoung.com/display/page/brand-page?brandNo={B...}`.
  - Sitemap: `https://global.oliveyoung.com/sitemapindex-product.xml`.
- **AVOID**: `oliveyoung.co.kr` (HTTP 403 anti-bot, `errors.md` E1).
- **Spec completo**: `docs/specs/scrapers/olive-young.md` — leerlo entero
  antes de iterar.
- **Scraper JS**: `scrapers/olive-young/sc_browser/` + `sc_code/` — **vacíos
  hoy**, ver §8.

Cadencia de corridas esperada (decidida por el repo de agentes, no por el
middleware): diaria o semanal, con dedup 24h por `prdt_no` para no
reabrir la misma ficha el mismo día (spec §8).

---

## 2. Shape de `data[]` por entidad

`envelope["data"]` es **heterogéneo**. Cada row lleva el campo `entity`
como discriminador. Las tres entidades siguen el §2 del spec del scraper
**literalmente** (nombres cortos) — el renombrado desde el scraper al
wire lo hace el middleware (ver §4).

### 2.1 `entity="ranking"` — spec §2 + §4

Clave primaria: `(region, cat_id, rank)`. Dedup por esa clave.

```python
{
  "entity": "ranking",
  # §2 estrictos
  "ranking_id":  "oliveyoung-global_KR_1000000001_1_2026-04-21",
  "region":      "KR" | "USA",
  "cat_id":      "1000000001",
  "rank":        1,
  "prdt_no":     "GA240824996",
  "name_en":     "...",
  "brand_no":    "B00051",
  "rate":        4.9,                # 0..5, null si rating_invalid
  "is_soldout":  False,
  "promo":       "Coupon" | None,
  "scraped_date":"2026-04-21",
  # §4 adicionales (null / [] si faltan — nunca se inventan)
  "site_code":            "oliveyoung-global",
  "category_name":        "All",
  "product_url":          "https://global.oliveyoung.com/product/detail?prdtNo=GA240824996",
  "product_name_kr":      "...",
  "brand_name_en":        "...",
  "brand_name_kr":        "...",
  "has_coupon":           True | False | None,
  "has_gift":             True | False | None,
  "thumbnail_img_url_raw":  "/prdtImg/...",
  "thumbnail_img_url_full": "https://cdn-image.oliveyoung.com/prdtImg/...",
  "scraper_flags":        []
}
```

### 2.2 `entity="product"` — spec §2 + §5

Clave primaria: `prdt_no`. Dedup por esa clave. El enriquecimiento
detail vía Scraping Browser se aplica **solo** cuando el producto aparece
en ≥2 rankings (spec §5).

```python
{
  "entity": "product",
  # §2 estrictos
  "prdt_no":        "GA240824996",
  "url":            "https://global.oliveyoung.com/product/detail?prdtNo=GA240824996",
  "name_clean_en":  "...",           # spec §7 reglas de cleaning
  "name_clean_kr":  "...",
  "brand_no":       "B00051",
  "category_ids":   ["1000000001", "1000000008"],
  "ranks":          [1, 3],          # paralelo a category_ids
  "best_regions":   ["KR", "USA"],
  "review_count":   1234 | None,     # null si no se enriqueció
  "claim_tags":     ["Vegan", "Clean Beauty"],
  # §5 adicionales
  "product_name_en":   "...",
  "product_name_kr":   "...",
  "brand_name_en":     "...",
  "brand_name_kr":     "...",
  "rate":              4.9,
  "is_soldout":        False,
  "thumbnail_img_url_full": "https://cdn-image.oliveyoung.com/prdtImg/...",
  "category_names":    ["All", "Skincare"],
  "new_yn":            True | False | None,
  "best_yn":           True | False | None,
  "flash_yn":          True | False | None,
  "scraped_date":      "2026-04-21",
  "scraper_flags":     []
}
```

### 2.3 `entity="brand"` — spec §2 + §6

Clave primaria: `brand_no`. Dedup por esa clave. Visita brand-page
**solo** para las top-20 marcas por `total_in_rankings` (spec §6 + §8).

```python
{
  "entity": "brand",
  # §2 estrictos
  "brand_no":           "B00051",
  "name_en":            "...",
  "url":                "https://global.oliveyoung.com/display/page/brand-page?brandNo=B00051",
  "total_in_rankings":  17,
  "avg_rank":           12.3,        # menor = mejor
  # §6 adicionales
  "name_kr":         "...",
  "brand_og_image":  "https://.../og.png" | None,
  "scraped_date":    "2026-04-21",
  "scraper_flags":   []             # puede contener "brand_page_404"
}
```

### 2.4 Reglas comunes a las tres entidades

- **Toda clave §2 presente en cada row** — `None` explícito para atómicos
  faltantes, `[]` para lista faltante. Nunca omitir la clave.
- **`extra="allow"`** — el scraper puede emitir claves adicionales no
  listadas en §2/§4/§5/§6 (p.ej. experimentales). Esas pasan verbatim.
  Esto permite iterar el scraper JS sin tocar el middleware.
- **`scraper_flags`** — siempre lista. Valores permitidos (spec §8):
  `source_gone`, `cloudflare_challenge`, `rating_invalid`,
  `name_clean_fallback`, `product_enrich_failed`, `brand_page_404`,
  `detail_csrf_missing`, `sold_out`, `api_400`.

---

## 3. Traducción de inputs públicos ↔ seed JS

`OliveYoungClient._build_brightdata_inputs(OliveYoungInputs)` es la única
frontera donde los nombres de la API pública del middleware se reescriben
a los knobs internos del scraper. El seed es **uno solo**.

| Input público (`OliveYoungInputs`) | Seed JS | Comportamiento |
|---|---|---|
| `regions: ["KR"\|"USA", ...]` | `input.regions` (list) | El scraper expande a 11 cats KR y/o 12 cats USA × 100 rows. |
| `max_brand_visits: int` | `input.max_brand_visits` (int) | Cap duro de visitas a `/display/page/brand-page`. Si `0`, deshabilita el paso brand-page (ver §9 item 4). |
| `categories: list[str] \| None` | `input.categories` (list, opcional) | Whitelist de `category-id`. Si ausente, el scraper hace `GET /v1/pages/ranking/sales/categories` y usa la lista completa. |
| `max_products: int` | — **no forwardeado** | Clipping post-download en el middleware; el scraper no recibe este knob. |
| `include_rankings \| include_products \| include_brands` | — **no forwardeados** | Filtros post-download. El scraper no deja de hacer el trabajo; el middleware descarta las rows en `_build_envelope`. |
| `mode: "incremental" \| "full-refresh"` | — **no forwardeado** | Hint para el cache TTL del repo de agentes. El middleware lo reenvía en `envelope.inputs` intacto. |
| (implícito) | `input.url = RANKINGS_API_HOST` | Entry point conceptual pineado desde `config.RANKINGS_API_HOST`. |

**No se crean seeds por región** — el scraper JS expande él mismo la
matriz `regions × categories`. El middleware sólo empuja un seed con los
tres / cuatro knobs.

---

## 4. Post-procesamiento (aliases, clipping)

Todo ocurre en `_build_envelope`. Orden de operaciones por row:

1. **Skip defensivo** — si el row no es `dict`, contar en
   `meta.skipped_by_reason["non_dict_row"]` y bump `meta.errors`.
2. **Clasificar** — `_classify_entity(raw)`. Si devuelve `None`, contar
   en `meta.skipped_by_reason["unknown_entity"]`. Nunca se drop silently
   (siempre aparece en el contador).
3. **Filtrar por `include_*`** — si la entidad está deshabilitada, contar
   en `rankings_disabled` / `products_disabled` / `brands_disabled`.
4. **Coerce a la entidad** — `_coerce_ranking` / `_coerce_product` /
   `_coerce_brand`. Orden interno:
   a. `_apply_aliases(raw, <ENTITY>_ALIASES)` — renombrar §4-§6 → §2.
      Si el canónico ya está presente con valor no-null, el alias se
      mantiene como extra key (no sobrescribe).
   b. Rellenar §2 + §4/§5/§6 faltantes con `None` o `[]`.
   c. Forwardear extras verbatim.
   d. Pasar por `RankingRow` / `ProductRow` / `BrandRow` (pydantic
      validación con `extra="allow"`). **Si la validación falla, se
      devuelve el dict manualmente coercionado — nunca se pierde un
      row**.
5. **Cap `max_products`** — sólo para `entity="product"`. Si
   `products_emitted >= max_products`, contar en
   `meta.skipped_by_reason["max_products_cap"]` y descartar. Rankings y
   brands no se recortan.
6. **Contadores `meta.blocked`** — en ranking rows, si `scraper_flags`
   contiene `cloudflare_challenge` o `api_400`, incrementar
   `meta.blocked`. Es el numerador del gate `BLOCK_SATURATION` (ver §5).

### 4.1 Envelope final (`status="done"`)

```python
{
  "source": "olive-young",
  "scraped_at": "2026-04-21T15:30:00Z",
  "inputs": { ... echo de OliveYoungInputs.model_dump() ... },
  "data":   [ ... rows heterogéneos ... ],
  "meta": {
    "rows":     2371,
    "emitted":  2347,
    "emitted_by_entity": {"ranking": 2300, "product": 32, "brand": 15},
    "skipped_by_reason": {"unknown_entity": 2, "max_products_cap": 22},
    "blocked":  0,
    "errors":   0,
    "started_at": "...",
    "ended_at":   "..."
  }
}
```

---

## 5. Catálogo de errores

### 5.1 Códigos base (heredados de `core/errors.py`)

| code | retriable | cuándo |
|---|---|---|
| `SITE_BLOCKED` | false | BrightData reporta bloqueo sostenido del sitio fuente. |
| `STRUCTURE_CHANGED` | false | El parser de `sc_code`/`sc_browser` falla en >20% de las rows (no disparado automáticamente por el middleware hoy — reservado para una futura verificación de shape). |
| `TIMEOUT` | true | Wall-time budget consumido. Lo surface el consumidor, no el transport. |
| `INVALID_INPUTS` | false | Validación pydantic falla (no se llama a BrightData). También cubre: `job_id` no-string, credenciales faltantes, DCA collection expired/deleted. |
| `BRIGHTDATA_ERROR` | true | 5xx de la API BrightData, transport error, malformed JSON, snapshot/collection no encontrado, poll → `failed`. |
| `UNKNOWN` | false | Fallback. |

### 5.2 Código local del middleware

| code | retriable | cuándo |
|---|---|---|
| `BLOCK_SATURATION` | false | `>50%` de las ranking rows emitidas llevan `cloudflare_challenge` o `api_400`. Disparado por `_maybe_block_saturation` antes de devolver `status="done"`. |

Definido en `middlewares/olive_young/client.py`
(`OLIVE_YOUNG_ERROR_CODES`). No muta `core/errors.py` — es una extensión
local (patrón documentado en el handoff de cosmetics-design §6 y en el
docstring de `core/errors.py`).

**Denominador**: `meta.emitted_by_entity["ranking"]`. Productos y brands
**no cuentan** (son tablas de referencia más pequeñas y no son la señal
dominante de bloqueo). Umbral: `BLOCK_SATURATION_THRESHOLD = 0.5` en
`config.py`.

Payload al surface:

```python
{
  "status": "failed",
  "error": {
    "code": "BLOCK_SATURATION",
    "message": "N/M emitted ranking rows are blocked (> 50% threshold).",
    "retriable": False,
    "details": {"rankings": M, "blocked": N}
  }
}
```

### 5.3 Mapeo HTTP → code (dual-mode, cross-scraper)

Heredado del base — ver `docs/fase3/middleware-dual-mode.md` §4.3 y la
docstring de `core/errors.py`. Olive-young no sobreescribe ningún
mapeo.

---

## 6. Límites operativos

Los límites **duros** los aplica el scraper JS según spec §8; el
middleware complementa con caps en los inputs públicos para que
fat-finger typos disparen `INVALID_INPUTS` sin tocar BrightData.

| Límite | Dónde | Valor | Fuente |
|---|---|---|---|
| Requests totales por run | scraper JS | 1000 | spec §8 |
| Wall time | scraper JS | 60 min | spec §8 |
| `max_products` (input público) | middleware pydantic | 1..3000 | `config.MAX_PRODUCTS_HARD_CAP` |
| `max_brand_visits` (input público) | middleware pydantic | 0..100 | default 20, spec §8 |
| Detail enrichments via Scraping Browser | scraper JS | ≤100 | spec §8 (productos en ≥2 rankings) |
| Brand-page visits | scraper JS | ≤20 | spec §8 (top por `total_in_rankings`) |
| Cache local por `prdt_no` | scraper JS | 24h | spec §8 (no tocado por el middleware) |
| `eta_seconds` devuelto por `trigger()` | middleware | 1500 (25 min) | `config.DEFAULT_ETA_SECONDS` — estimación conservadora dentro del hard cap de 60 min |
| `BLOCK_SATURATION_THRESHOLD` | middleware | 0.5 | `config.py` |

Delay entre requests (3-5s para el host público, Crawl-delay 5 para el
microservicio rankings, spec §2) es responsabilidad exclusiva del
scraper JS.

---

## 7. Convenciones de naming

Cuatro capas distintas, con sus convenciones:

| Capa | Convención | Ejemplo |
|---|---|---|
| Carpeta del scraper JS | hyphen | `scrapers/olive-young/` |
| Paquete Python del middleware | underscore | `middlewares/olive_young/` |
| `envelope.source` (wire format) | hyphen (canónico, xlsx + spec) | `"olive-young"` |
| Env vars | SCREAMING_SNAKE con underscore | `BRIGHTDATA_DATASET_ID_OLIVE_YOUNG` |
| Tool names (schema para Anthropic) | snake_case con prefijo módulo | `olive_young_trigger`, `olive_young_get_result` |

Entity discriminators: siempre en minúsculas, singular —
`"ranking"` / `"product"` / `"brand"`.

---

## 8. Dependencias del scraper JS

**Estado al 2026-04-21: el scraper JS está vacío.**

```
scrapers/olive-young/
├── vendor/
│   ├── sc_browser/        ← vacío
│   ├── sc_code/           ← vacío
│   └── README.md          ← describe el proceso (ver abajo)
├── sc_browser/            ← vacío
├── sc_code/               ← vacío
└── results/
    └── errors.md          ← catálogo vivo E1..E6
```

DB AI todavía no entregó el andamiaje `vendor/sc_browser/` ni
`vendor/sc_code/`. El flujo pendiente (ver `docs/specs/memory.md`
Etapa 2):

1. Usuario entrega la sección `databrightdata` (§1-§3) de
   `docs/specs/scrapers/olive-young.md` a DB AI.
2. DB AI genera `interaction_code.js` y `parser_code.js` en
   `vendor/sc_browser/` y `vendor/sc_code/`.
3. First boot — copia verbatim con sufijo `_v1` a
   `scrapers/olive-young/sc_browser/` y `sc_code/`.
4. Iteración `_v2`, `_v3`, ... hasta que el output respete §2 y las
   reglas §4-§9 de la spec.

### Qué espera el middleware del scraper JS

El middleware está diseñado para consumir rows con el shape §2 + §4-§6
(nombres largos, que el middleware renombra vía aliases). Cuando el
scraper exista, debe emitir:

- **Rows multi-entidad** en un único array/stream de snapshot.
  Preferentemente cada row con un campo `entity: "ranking" | "product" | "brand"`; si no, el heurístico
  `_classify_entity` cae sobre las keys presentes.
- **Claves §2 estrictas** siempre presentes por entidad (atómicos
  pueden ser `null`, listas pueden ser `[]`).
- **Claves §4-§6 adicionales** con los nombres largos que los dicts de
  alias del middleware ya contemplan (ver `models.py`
  `RANKING_ALIASES` / `PRODUCT_ALIASES` / `BRAND_ALIASES`).
- **`scraper_flags` como lista** (nunca string), con valores del
  catálogo spec §8.

### Qué NO hace el middleware

- **No reimplementa parsing**. No hace requests al sitio. No arma
  URLs. No implementa las reglas §7 (`name_clean_en`, `name_clean_kr`,
  `rate` clamp, `thumbnail_img_url_full` derivation). Todo eso vive en
  el parser JS.
- **No inventa campos**. Si el scraper no emite `review_count`, la row
  llega con `review_count: null` + flag `product_enrich_failed` (si el
  scraper la marcó). El middleware nunca dispara un request para
  completar un campo.
- **No modifica el shape §2**. Si el scraper evoluciona y quiere agregar
  un campo, pasa verbatim por `extra="allow"` sin tocar el middleware.

### Cuando el scraper exista

No deberían necesitarse cambios estructurales en el middleware. Las
tareas mínimas:

1. Reemplazar el fixture fabricado de tests (si hoy existe) por uno
   real de un snapshot conocido.
2. Revisar que los alias cubran todas las claves que el scraper
   realmente emite — si el scraper introduce una nueva clave larga
   para una clave §2 corta, agregar al dict de alias correspondiente.
3. Confirmar que la clasificación heurística (`_classify_entity`) no
   deja rows en `unknown_entity` > 0 en runs reales.

---

## 9. Preguntas abiertas

1. **Ambigüedad de naming ranking** — ¿qué emite el scraper?
   - spec §2: `promo` / §4 prosa: `promotion_name`.
   - spec §2: `name_en` / §4 prosa: `product_name_en`.
   - spec §2: `cat_id` / §4 prosa: `category_id`.
   - spec §2: `region` / §4 prosa: `region_code`.
   El middleware está preparado para **ambas** (alias §4 → §2). Cuando
   exista el scraper, confirmar con el primer run y limpiar los alias
   innecesarios si no aparecen.

2. **Ambigüedad de naming product** — mismo caso:
   - spec §2: `url` / §5 prosa: `product_url`.
   - spec §2: `name_clean_en` / §5 prosa: `product_name_clean_en`.
   - spec §2: `name_clean_kr` / §5 prosa: `product_name_clean_kr`.

3. **Ambigüedad de naming brand** — mismo caso:
   - spec §2: `name_en` / §6 prosa: `brand_name_en`.
   - spec §2: `url` / §6 prosa: `brand_url`.
   - spec §2: `total_in_rankings` / §6 prosa: `brand_total_products_in_rankings`.
   - spec §2: `avg_rank` / §6 prosa: `brand_avg_rank`.

4. **`review_count` opcional**. Spec §2 lo lista en la entidad product,
   pero spec §5 lo describe como enriquecimiento vía Scraping Browser
   **sólo cuando el producto aparece en ≥2 rankings**. El middleware
   acepta `null` + `scraper_flags=["product_enrich_failed"]` cuando el
   enriquecimiento no ocurrió. Confirmar con el primer run: ¿el scraper
   distingue "no intentado" (producto visto una sola vez) vs
   "intentado y falló" (flag)? Opción sugerida: `review_count=null` sin
   flag cuando es "no intentado", con flag cuando es "intentado y
   falló".

5. **`max_brand_visits=0`** — interpretación actual: "deshabilitar
   visitas brand-page pero seguir emitiendo brand rows desde la
   agregación de ranking" (los campos `name_en`, `brand_no`,
   `total_in_rankings`, `avg_rank` se derivan de ranking sin visitar la
   página). Campos que sólo se llenan con la visita (`brand_og_image`,
   `name_kr` si la página es KR-only) quedan `null`. Si la spec quiere
   "mínimo 1 visita", ajustar el `Field(ge=0, le=100)` a
   `Field(ge=1, le=100)` en `models.py` y el JSON Schema en
   `tool_schema.py`.

6. **`mode="full-refresh"`** — el middleware lo reenvía al scraper via
   `envelope.inputs` pero **no lo forwardea al seed**. La spec §8 dice
   "cache local 24h por prdt_no". ¿El scraper JS debería exponer un
   knob `full_refresh` para saltearse el cache? Hoy el flag es hint
   para el repo de agentes — el scraper ignora su existencia.

7. **`STRUCTURE_CHANGED` automático** — spec §5 del handoff base lo
   define como "parser falla en >20%". El middleware hoy **no
   monitorea** este ratio en olive-young — sería un gate adicional
   análogo a `BLOCK_SATURATION` pero sobre rows con `entity=None`
   (unknown) o sin `prdt_no` cuando la entidad es product/ranking.
   Decidir si vale la pena agregarlo cuando el scraper produzca el
   primer run real.

8. **Identificador del snapshot** — el middleware asume un único
   `snapshot_id` / `collection_id` por run que retorna el array entero
   al hacer fetch. Si el scraper JS particiona el output en múltiples
   snapshots (uno por región, por ejemplo), habría que coordinarlos en
   el middleware. **No documentado en la spec hoy** — asumir `1
   snapshot → 1 run` hasta que el scraper demuestre lo contrario.
