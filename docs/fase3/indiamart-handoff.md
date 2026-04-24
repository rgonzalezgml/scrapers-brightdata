# Handoff Fase 3 — indiamart

> **Destino del trabajo**: `middlewares/indiamart/` (este repo — ya implementado al 2026-04-21; este handoff es **post-facto**, ratifica decisiones tomadas en código antes del documento).
> **Consumidor**: repo de agentes. Importa este paquete como dependencia y encima coloca `ServiceRegistry`, persistencia (`scraper_runs` en PostgreSQL), cache TTL y declaración de tool al agente.
> **Agente responsable**: `middleware-python` (iteraciones) + `analista-de-scrapers` (cuando DB AI entregue el andamiaje en `scrapers/indiamart/vendor/`).
>
> **Estado al 2026-04-21**:
> - Middleware Python: **implementado** con tests, dual-mode v3/DCA, multi-entity (`product` + `supplier`), aliases asimétricos, ISO-2 supplier, errores locales `STRUCTURE_CHANGED` / `REGION_BLOCKED`.
> - Scraper JS (`scrapers/indiamart/vendor/sc_browser/*.js` + `sc_code/*.js`): **vacío (0 bytes)**. DB AI aún no entregó el andamiaje. El middleware asume el shape spec §2 en cuanto exista.
>
> **Precedente**: este handoff sigue el patrón del canónico `docs/fase3/cosmetics-design-handoff.md`. Diferencia principal: indiamart es **multi-entidad** (`product` + `supplier` discriminados por campo `entity`) mientras cosmetics-design es entidad única (`article`).

---

## 0. Antes de arrancar — inputs ratificados y preguntas abiertas

### 0.1 Decisiones ratificadas (ya en código)

Estas son las decisiones ya implementadas en `middlewares/indiamart/`. El handoff las documenta para que cualquier rework o regeneración las preserve.

1. **Multi-entidad con discriminador `entity`** ∈ `{"product", "supplier"}`.
   El classifier (`_classify_entity`) usa el siguiente orden:
   1. Campo explícito: `raw["entity"]` o `raw["_entity"]`.
   2. Campo `type` **literal** — solo si el valor es exactamente `"product"` o `"supplier"`.
      Caveat: `type="chemical"` / `"packaging"` / `"other"` es campo *de producto* por spec §8 y **NO** se interpreta como discriminador. El classifier distingue los dos usos por el valor.
   3. Heurísticas:
      - `price_currency` / `moq_quantity` / `price_min_usd` / `product_id` / `product_url` → `product`.
      - `supplier_id` presente + algún campo supplier-only (`business_type`, `member_since_year`, `trustseal`, `trustseal_verified`, `year_established`, `verified_exporter`, `gst`, `annual_turnover`) → `supplier`.
   4. Si nada matchea → `None` (counted bajo `meta.skipped_by_reason["unknown_entity"]`, nunca drop silencioso).

2. **Aliases asimétricos** (`models.py`):
   - **Product alias map**: solo `product_url → url`.
     `supplier_name`, `supplier_city`, `supplier_state`, `supplier_country` en una fila `product` son **FK denormalizadas** (referencias al supplier dueño), se preservan verbatim con su prefijo `supplier_*`. NO se renombran a `name` / `city` / `state` / `country` — esos slots pertenecen al producto en una fila product.
   - **Supplier alias map**: renombra las formas verbosas a §2:
     - `supplier_url → url`
     - `supplier_name → name`
     - `supplier_city → city`
     - `supplier_state → state`
     - `supplier_country → country`
     - `verified_exporter → verified`
     - `trustseal_verified → trustseal`
   - Regla de precedencia: si la fila carga ambos (alias source + canonical target) con el target ya seteado y no-null, el canonical gana — no sobreescribe valores explícitos.

3. **ISO-2 solo en supplier**:
   La normalización `COUNTRY_NAME_TO_ISO2` (`"india" → "IN"`, `"china" → "CN"`, etc.) se aplica **solo** a la fila `supplier` en `_normalize_supplier_country`. En filas `product` el campo `supplier_country` es FK denormalizada y se preserva verbatim.
   - Ya-ISO-2 (`"IN"`, longitud 2, uppercase, alpha): passthrough.
   - Mapeable: sustituido.
   - Desconocido: preserva el original y agrega `"country_not_iso2"` a `scraper_flags` (no bloquea).

4. **Dos errores locales** (`INDIAMART_ERROR_CODES`, extienden catálogo base sin mutarlo):
   - **`STRUCTURE_CHANGED`** (no se redefine — existe en base catalog): se dispara cuando `meta.structure_failed / meta.emitted_by_entity["product"] > 0.5`. Cuenta como structure-failed cualquier fila product que: (a) no trae `product_id`, o (b) carga `jsonld_parse_fallback` / `breadcrumb_missing` / `spec_table_missing` en `scraper_flags`.
   - **`REGION_BLOCKED`** (nuevo, solo indiamart): se dispara cuando `meta.blocked / meta.emitted_by_entity["product"] > 0.5`. Cuenta como blocked cualquier fila product con `blocked` / `rate_limit_blocked` / `blocked_retried` en `scraper_flags`. Semántica: IndiaMART sirvió bot-check page (Access Denied + redirect a `/enquiry.html`) desde IP no-IN; acción sugerida: rotar a pool residencial IN.
   Ambos son `retriable=false` — el retry lógico es rebasar parser (STRUCTURE) o rotar IPs (REGION), no reintentar en seguida.

5. **Seeds translation** (`_build_brightdata_inputs`):
   - Una URL por MCAT slug: `https://dir.indiamart.com/impcat/{slug}.html`.
   - Una URL por industry hub: `https://dir.indiamart.com/indianexporters/ind_{industry}.html`.
   - Defaults spec §9: 12 MCATs (`caustic-soda`, `sodium-hydroxide-pellets`, `hydrochloric-acid`, `sulphuric-acid`, `sodium-carbonate`, `acetic-acid`, `industrial-drums`, `industrial-containers`, `plastic-drums`, `corrugated-box`, `packaging-materials`, `stretch-film`) + 2 hubs (`chem`, `packaging`).
   - Defensive: `include_industry_hubs=False` + `mcat_slugs=[]` (lista vacía explícita, no `None`) ⇒ `INVALID_INPUTS` con mensaje claro. `None` en ambos ⇒ defaults.

6. **Dual-mode `API_MODE`** (Datasets v3 + DCA legacy, ver `docs/fase3/middleware-dual-mode.md`):
   - Env var v3: `BRIGHTDATA_DATASET_ID_INDIAMART` (formato `gd_...`).
   - Env var DCA: `BRIGHTDATA_COLLECTOR_ID_INDIAMART` (formato `c_...`).
   - Precedencia: **v3 gana** cuando ambos están seteados (mismo patrón cosmetics-design).
   - Si ninguno está seteado → `INVALID_INPUTS` en trigger-time con `CREDENTIAL_HINT` que nombra las dos env vars.
   - Auth compartida: `BRIGHTDATA_API_KEY` (misma en los dos modos).

7. **`mode` ∈ {`"incremental"`, `"full-refresh"`}**:
   Se propaga a `envelope["inputs"]` pero **no modifica comportamiento del middleware ni del scraper JS hoy**. Es hint para el cache TTL del repo de agentes (mismo patrón cosmetics-design). El JS scraper no diferencia entre los dos modos — el 24h dedup por `product_id` (spec §9) vive conceptualmente del lado JS y el agents repo puede pasar por encima con `full-refresh` para su propia cache.

### 0.2 Confirmar con el usuario antes de disparar trigger real

1. **Resource id de BrightData** para indiamart. Puede ser cualquiera de los dos (dual-mode):
   - `BRIGHTDATA_DATASET_ID_INDIAMART` (formato `gd_...`) si el scraper ya fue publicado en Scraper Studio, **o**
   - `BRIGHTDATA_COLLECTOR_ID_INDIAMART` (formato `c_...`) si vive como colector legacy.
   Si se setean las dos, v3 gana. **No adivinar el id** — hoy no hay valor conocido.
2. **Env var `BRIGHTDATA_API_KEY`** — la misma llave que cosmetics-design (cuenta única BrightData del usuario).
3. **Nombre del paquete Python**: `middlewares/indiamart/` (sin underscore — el nombre del scraper es una sola palabra). El scraper JS vive en `scrapers/indiamart/` también sin hyphen.

### 0.3 Preguntas abiertas (ver §9 para detalle)

- ¿El JS convierte INR→USD o lo hace el middleware? (el middleware confía y NO convierte; spec §4 sugiere que el JS hace la conversión con `EXCHANGE_RATES`).
- ¿`verified_exporter` y `trustseal_verified` son los nombres que emite DB AI, o el vendor real va a emitir `verified` / `trustseal` directo? (aliases asumidos, confirmar al recibir `vendor/`).
- ¿Semántica operativa de `max_suppliers`? (hoy el middleware recorta post-download si el JS emite más de lo pedido, pero el JS ya tiene cap 300 spec §9).

---

## 1. Identidad y alcance

- **Nombre**: `indiamart` (carpeta JS y paquete Python — misma palabra, sin hyphen).
- **Categoría**: **Precios** (B2B India, tercera fuente alongside `alibaba` y `made-in-china`).
- **Fuente**: `https://www.indiamart.com/` (home + proddetail) + `https://dir.indiamart.com/` (impcat listings + city dir + sitemaps + industry hubs).
- **Entidades**: dos — `product` y `supplier` — compartiendo `envelope["data"]`, discriminadas por `entity`.
- **Spec completo**: `docs/specs/scrapers/indiamart.md`. Leerlo entero antes de iterar.
- **Proposito del scraper**: precios alternativos de materiales indios (químicos industriales y empaque) como tercera fuente comparable contra alibaba y made-in-china. Los tres schemas comparten nombres canónicos (`price_min_usd`, `moq_quantity`, `supplier_*`) para que downstream compare sin mapeos.
- **Lo que NO extrae**: reviews free-text, formularios enquiry, chat con supplier, galería completa de imágenes, catálogos de video, newsfeed, ratings con texto. Signal-focused, no content-focused.

Cadencia esperada (la decide el repo de agentes, no el middleware): semanal full-refresh para rotar fixtures de precios; incremental diario limitado para una cartera de MCATs prioritarios.

---

## 2. Shape `data[]` por entidad

`envelope["data"]` es una lista **heterogénea**: cada fila carga un `entity` discriminador + los campos de su entidad. El schema corresponde 1:1 a `docs/specs/scrapers/indiamart.md` §2 / §4 / §5 / §6. **Inmutable** entre versiones de implementación.

### 2.1 Fila `product`

Campos §2 strict (siempre presentes; `null` cuando faltan; listas vacías nunca `null`):

```
product_id, url, name_clean, type, category_mic, category_path,
price_min_usd, price_max_usd, price_unit, price_currency,
moq_quantity, moq_unit, supplier_id, supplier_city, scraped_date
```

Campos §4 / §5 additional (null cuando faltan):

```
site_code, product_name_original, product_description, image_primary,
industry_slug, price_raw, price_value_raw, availability,
supplier_name, supplier_state, supplier_country,
cas_no, grade, appearance, packaging_type, concentration,
price_normalized_per_kg
```

Flags (lista, nunca null):

```
scraper_flags
```

Discriminador: `entity == "product"`.

Los campos `supplier_*` en fila `product` son **FK denormalizadas** — referencia al supplier dueño del producto. NO se renombran a `name` / `city` / `state` / `country` (esos slots pertenecen al producto). Permanecen verbatim con su prefijo.

### 2.2 Fila `supplier`

Campos §2 strict:

```
supplier_id, url, name, country, city, state, business_type,
member_since_year, verified, trustseal
```

Campos §6 additional (null cuando faltan):

```
year_established, gst, annual_turnover, certifications, scraped_date
```

Flags:

```
scraper_flags
```

Discriminador: `entity == "supplier"`.

En filas supplier, `country` ES ISO-2 (`"IN"`) — la normalización se aplica solo aquí, no en filas product.

### 2.3 Regla de puntos ciegos

- Claves siempre presentes (null explícito, nunca omitir) — spec §5 literal: "Todos los campos con null explicito cuando faltan; nunca omitir la clave."
- Campos lista siempre `[]` cuando vacíos — spec §5 / §6 literal: "listas vacias nunca null".
- `extra="allow"` en los pydantic models — el JS puede emitir campos debug futuros (`_price_source`, `_moq_source`, etc.) y el middleware los forwarded verbatim. El agents repo opta in.

---

## 3. Traducción inputs públicos ↔ seeds JS

### 3.1 Inputs públicos — `IndiamartInputs` (pydantic v2, `extra="forbid"`)

```python
class IndiamartInputs(BaseModel):
    mcat_slugs: list[str] | None = None           # None ⇒ defaults §9 (12 MCATs)
    industry_hubs: list[str] | None = None        # None ⇒ defaults §9 (chem, packaging)
    include_industry_hubs: bool = True             # False ⇒ no emit hub seeds
    max_products: Annotated[int, Field(ge=1, le=1500)] = 500
    max_suppliers: Annotated[int, Field(ge=0, le=300)] = 150
    include_suppliers: bool = True                 # False ⇒ drop supplier rows
    mode: Literal["incremental", "full-refresh"] = "incremental"
```

### 3.2 Traducción a Stage 1 seeds

`_build_brightdata_inputs` emite una lista de dicts `[{"url": <seed>}, ...]` que el interaction code del scraper consume:

- **MCAT listings**: por cada slug en `mcat_slugs` (o defaults), emite `https://dir.indiamart.com/impcat/{slug}.html`. El scraper expande cada listing en top-N products + subcats hijas (max 2 niveles, spec §9).
- **Industry hubs**: si `include_industry_hubs=True`, por cada hub en `industry_hubs` (o defaults), emite `https://dir.indiamart.com/indianexporters/ind_{industry}.html`. Cada hub enumera hasta 100 MCATs adicionales.
- Dedup: el scraper deduplica internamente por `product_id` — el middleware no lo hace.
- Guard: si después del build no hay seeds (i.e. `mcat_slugs=[]` **y** (`include_industry_hubs=False` o `industry_hubs=[]`)) ⇒ `INVALID_INPUTS` explícito. No mandamos triggers vacíos.

### 3.3 Filtros post-download (solo en middleware, no en JS)

- `max_products`: recorta la lista de productos emitidos después de parsear el snapshot. El scraper tiene su propio cap a 1500 (spec §9). El middleware recorta a `max_products` (default 500). Las filas clipadas caen a `meta.skipped_by_reason["max_products_cap"]`.
- `max_suppliers`: idem para suppliers. Cap scraper 300, cap middleware 150.
- `include_suppliers=False`: todas las filas supplier se cuentan bajo `meta.skipped_by_reason["suppliers_disabled"]`. Nunca tocan `data[]`.

---

## 4. Post-procesamiento — aliases, ISO-2, meta

### 4.1 Aliases asimétricos

Ver §0.1.2. El middleware renombra las formas verbosas del JS a las formas cortas §2 solo en supplier; en product preserva `supplier_*` porque son FK denormalizadas, no campos propios.

### 4.2 ISO-2 supplier-only

`_normalize_supplier_country` se aplica exclusivamente a filas `entity="supplier"` tras el coerce:

1. Si `country` ya es ISO-2 válido (longitud 2, alfabético, uppercase): passthrough literal.
2. Si está en `COUNTRY_NAME_TO_ISO2` (case-insensitive): sustituye por el ISO-2.
3. Si está pero es desconocido: preserva el original, agrega `"country_not_iso2"` a `scraper_flags` (dedup — no se duplica si ya existía).

No se aplica a `supplier_country` en filas `product` (sigue verbatim, podría ser `"India"` literal).

### 4.3 Meta del envelope

```python
meta = {
  "rows": <input rows>,
  "emitted": <output rows>,
  "emitted_by_entity": {"product": int, "supplier": int},
  "skipped_by_reason": {
    "non_dict_row": int,              # fila no-dict, defensive
    "unknown_entity": int,             # classifier devolvió None
    "suppliers_disabled": int,         # include_suppliers=False
    "max_products_cap": int,           # hit max_products
    "max_suppliers_cap": int,          # hit max_suppliers
  },
  "blocked": int,                      # product rows con blocked* flags
  "structure_failed": int,             # product rows sin product_id o con parse-fail flags
  "errors": int,                       # non-dict rows + shape errors
  "started_at": "YYYY-MM-DDTHH:MM:SSZ",
  "ended_at":   "YYYY-MM-DDTHH:MM:SSZ",
}
```

Las claves son estables; el agents repo puede confiar en ellas para dashboards/alertas.

---

## 5. Catálogo de errores

### 5.1 Base (compartidos con todos los scrapers)

| code | retriable | cuándo |
|---|---|---|
| `SITE_BLOCKED` | false | transport 451 al trigger |
| `STRUCTURE_CHANGED` | false | >50% product rows sin product_id o con parse-fallback flags |
| `TIMEOUT` | true | wall-time budget agotado sin final state |
| `INVALID_INPUTS` | false | pydantic validation falla, o seeds vacíos, o resource id sin setear |
| `BRIGHTDATA_ERROR` | true | 5xx / poll→failed / malformed JSON |
| `UNKNOWN` | false | uncategorizado |

Mapeo HTTP status → code delegado al `BaseTransport` (ver `middlewares/core/errors.py` docstring): 401/403 / 4xx trigger → `INVALID_INPUTS`; 5xx → `BRIGHTDATA_ERROR`; 451 trigger → `SITE_BLOCKED`.

### 5.2 Extensiones locales (indiamart-only)

Declaradas en `INDIAMART_ERROR_CODES` del `client.py` — **extienden** el catálogo base, no lo mutan.

| code | retriable | cuándo |
|---|---|---|
| `STRUCTURE_CHANGED` | false | Ver `_maybe_structure_changed`: `structure_failed / emitted_products > 0.5`. No se redefine el código (es base); se dispara localmente. |
| `REGION_BLOCKED` | false | Nuevo. Ver `_maybe_region_blocked`: `blocked / emitted_products > 0.5`. Semántica: IndiaMART bloquea IPs no-IN. Acción: rotar pool residencial IN. |

Ambos thresholds configurables en `config.py` (`STRUCTURE_CHANGED_THRESHOLD = 0.5`, `BLOCK_SATURATION_THRESHOLD = 0.5`).

Cuando `_maybe_region_blocked` o `_maybe_structure_changed` disparan, el envelope completo se reemplaza por `{"status": "failed", "error": {...}}` — el agents repo no ve `data[]` parcial. Los counts relevantes van en `error.details`.

---

## 6. Límites operativos

Spec §9 define los caps scraper-side. El middleware NO re-enforce el global request cap (vive en el runtime BrightData) pero sí clipa emitidos post-download.

| Recurso | Cap scraper (§9) | Cap middleware (`IndiamartInputs`) | Default |
|---|---|---|---|
| PRODUCT_ID detail pages | 1500/run | `max_products` 1..1500 | 500 |
| Supplier home visits | 300/run | `max_suppliers` 0..300 | 150 |
| Requests totales | 3000/run | — (BrightData) | — |
| Wall time | 90 min | — (BrightData) | — |
| MCAT seeds | 12 default + ~100 por hub | `MAX_MCAT_SEEDS_HARD_CAP = 50` (sanity fence) | 12 |
| Dedup | 24h cache por product_id | — (scraper) | — |
| `eta_seconds` (surface) | — | `DEFAULT_ETA_SECONDS` | 45 min |

---

## 7. Convenciones de naming

- **Paquete Python**: `middlewares/indiamart/` — una sola palabra, lowercase, sin hyphen ni underscore.
- **Scraper JS**: `scrapers/indiamart/` — misma convención.
- **Source name en envelope**: `"indiamart"` (ver `SOURCE_NAME` en config).
- **Env vars**: `BRIGHTDATA_DATASET_ID_INDIAMART` y `BRIGHTDATA_COLLECTOR_ID_INDIAMART` (UPPER, underscore).
- **Tools agents-repo**: `indiamart_trigger`, `indiamart_get_result` (ver `tool_schema.py`).

---

## 8. Dependencias del scraper JS — CRÍTICA

### 8.1 Estado al 2026-04-21

Los cuatro archivos del andamiaje están en cero bytes:

```
scrapers/indiamart/vendor/sc_browser/interaction_code.js   0 bytes
scrapers/indiamart/vendor/sc_browser/parser_code.js        0 bytes
scrapers/indiamart/vendor/sc_code/interaction_code.js      0 bytes
scrapers/indiamart/vendor/sc_code/parser_code.js           0 bytes
```

DB AI aún no entregó el scraper. **Toda la spec §2 / §4 / §5 / §6 está en juego** hasta que exista un vendor real contra el que validar. El middleware Python asume el shape spec §2 + los aliases verbosos §4/§6 — si DB AI entrega nombres distintos, los aliases (`PRODUCT_ALIASES`, `SUPPLIER_ALIASES`) del `models.py` hay que revisarlos.

### 8.2 Acciones cuando DB AI entregue el vendor

Responsable: `analista-de-scrapers`. Flujo canónico (ver `docs/specs/memory.md` Etapa 2):

1. DB AI entrega los 4 archivos → usuario los pone en `scrapers/indiamart/vendor/`.
2. Primer boot — copia verbatim con sufijo `_v1` a `scrapers/indiamart/sc_browser/` + `sc_code/`. No editar en este paso.
3. Gap analysis vendor vs spec — revisar §4-§9 contra lo que vendor produce. Documentar en `scrapers/indiamart/results/errors.md`.
4. Iteración en root (`_v2`, `_v3`, ...), dejando vendor archivado.
5. **Cross-check con middleware**: cada vez que se observe un campo emitido por el JS que el middleware no matchea:
   - Si el nombre es una forma verbosa (`supplier_name_full` en vez de `supplier_name`) → actualizar `PRODUCT_ALIASES` / `SUPPLIER_ALIASES` en `middlewares/indiamart/models.py`.
   - Si es un campo nuevo no previsto por spec §4/§6 → `extra="allow"` en pydantic lo preserva, pero actualizar spec + modelo para convertirlo en campo catalogado.
   - Si falta un campo spec §2: el middleware ya lo setea a `None` / `[]` defensivamente; el gap es del JS, no del Python.

### 8.3 Fixture de regresión obligatorio

Spec §11: el product_id `22408594448` (Caustic Soda Flakes 99%, ₹50/kg, MOQ 20000 KG, supplier Vats International, New Delhi) **debe** emitir los siguientes valores exactos una vez el vendor esté vivo:

```
product_id                   "22408594448"
product_name_original        "Caustic Soda Flakes"
price_currency               "INR"
price_value_raw              "50"
price_unit                   "kg"
moq_quantity                 20000
moq_unit                     "kg"
supplier_name                "Vats International"
supplier_city                "New Delhi"
supplier_state               "Delhi"
supplier_country             "IN"          (verbatim en product row, FK denormalizada)
type                         "chemical"
category_mic                 "Caustic Soda"
category_path                ["Industrial Chemicals & Supplies", "Chemical Compound", "Caustic Soda"]
industry_slug                "chem"
```

URL: `https://www.indiamart.com/proddetail/caustic-soda-flakes-22408594448.html`.

Este fixture es criterio de aceptación del vendor: cualquier versión del JS que no lo produzca limpio es rechazada. El middleware tiene tests independientes (en `middlewares/indiamart/tests/`) que validan la coerción + aliases contra un mock row con esos mismos valores — cuando llegue el JSON real, sustituir el mock por un snapshot real de BrightData.

---

## 9. Preguntas abiertas

Estas quedan documentadas para ratificar cuando DB AI entregue el andamiaje o el usuario tome la decisión.

### 9.1 Conversión INR → USD: ¿en JS o en Python?

Spec §4: "price_min_usd y price_max_usd numericos convertidos con EXCHANGE_RATES (INR~0.012)".
Spec §7: "convertir a USD con EXCHANGE_RATES["INR"]".

Lectura actual del middleware: el JS hace la conversión (el scraper tiene la exchange rate table y emite los campos `*_usd` ya convertidos). El middleware **no convierte nada** — confía en el valor del JS y lo pasa verbatim.

`DEFAULT_INR_TO_USD = 0.012` en `config.py` es solo valor de referencia; no se usa para conversión.

**Acción cuando llegue el vendor**: verificar que el JS efectivamente emita `price_min_usd` y `price_max_usd` como numéricos convertidos. Si emite solo `price_value_raw` sin conversión, o emite `*_inr` en vez de `*_usd`, decidir:

- Opción A (preferida): pedir a DB AI que el JS haga la conversión — es parte del contrato §4.
- Opción B: el middleware asume la responsabilidad (agregar `_convert_inr_to_usd` en `_coerce_product`) y actualizar spec.

### 9.2 Naming de aliases `verified` / `trustseal`

Spec §6 menciona `verified_exporter` (bool) y `trustseal` (bool literal "TrustSEAL Verified"). Pero spec §2 schema usa `verified` + `trustseal`.

Alias asumido en `SUPPLIER_ALIASES`:

```
verified_exporter  → verified
trustseal_verified → trustseal
```

¿Qué nombre va a emitir el vendor? Dos posibilidades:

- (a) DB AI lee §2 y emite directo `verified` / `trustseal` — los aliases no disparan (idempotentes).
- (b) DB AI lee §6 y emite `verified_exporter` / `trustseal_verified` — los aliases renombran.

Ambos casos funcionan con el código actual. **Acción**: verificar al recibir `vendor/` y, si DB AI inventó una tercera variante (ej. `is_verified`, `trust_seal`), agregarlo al alias map.

### 9.3 Semántica de `max_suppliers` vs cap scraper-side

Spec §9 cap: 300 supplier home por run.
Cap middleware: `max_suppliers` (default 150, max 300).

Semántica actual (post-download clip): si el JS emite 250 suppliers y `max_suppliers=150`, los últimos 100 caen a `meta.skipped_by_reason["max_suppliers_cap"]`. El JS ya hizo el trabajo de visitar esos 100 — el gasto está hecho.

**Ambigüedad**: ¿el cap debería ser pre-download (pasarlo al JS como input y que el JS se detenga temprano) o post-download (como hoy)?

Decisión implementada: **post-download**. Razones:

1. El JS scraper (spec §9) ya tiene su propio cap duro 300 — pasar un cap más bajo requeriría modificar el interaction code para leer un input adicional, que DB AI puede no soportar elegantemente.
2. La emisión de supplier rows es batch al final; el scraper no puede saber cuántos va a emitir hasta visitar todos los products y ver cuántos suppliers únicos salen.
3. El cost model del usuario es por request (BrightData cobra por page fetch), no por row emitido — el ahorro de clipar pre-download es marginal.

**Acción**: si el usuario prioriza costo (quiere que el JS se detenga temprano), rediseñar pasando `max_suppliers` como input al JS y que el interaction code lo respete. Eso requiere cambio en el vendor + el middleware lo pasaría en `_build_brightdata_inputs`. Hoy no está implementado.

### 9.4 Observabilidad de `entity` en el JS

Decisión abierta: ¿el JS emite el campo `entity` explícito en cada row (recomendado), o el middleware lo infiere siempre por heurística?

Hoy el `_classify_entity` soporta ambos caminos (explícito primero, heurística fallback). Si DB AI entrega un JS que no emite `entity`, el classifier funciona pero es frágil a evoluciones del schema.

**Acción sugerida**: pedir a DB AI que el JS emita `entity: "product"` o `entity: "supplier"` explícito — elimina la ambigüedad con el campo `type` (que en product es `"chemical"` / `"packaging"` / `"other"`).

---

## 10. Entregables ya cerrados al 2026-04-21

Referenciados aquí para no duplicar esfuerzo en el próximo rework:

1. `middlewares/indiamart/__init__.py` — exports públicos (`trigger`, `get_result`, `TOOL_SCHEMA`).
2. `middlewares/indiamart/client.py` — `IndiamartClient` con dual-mode, classifier multi-entidad, coerción por entidad, ISO-2 supplier-only, `REGION_BLOCKED` + `STRUCTURE_CHANGED` locales.
3. `middlewares/indiamart/models.py` — `IndiamartInputs`, `ProductRow`, `SupplierRow` + alias maps + ISO-2 country map.
4. `middlewares/indiamart/config.py` — defaults §9 (MCATs, hubs), env vars v3/DCA, thresholds saturación.
5. `middlewares/indiamart/tool_schema.py` — declaración de dos tools para el agents repo.
6. `middlewares/indiamart/tests/` — conftest + fixtures + test_client (pasando bajo pytest-asyncio).

Pendiente:

- Scraper JS vendor (ver §8). Bloquea la corrida end-to-end real. El middleware corre unit/fixture hoy; corrida live pide `BRIGHTDATA_API_KEY` + uno de los dos resource ids + vendor JS existente.
- Snapshot real de BrightData para `tests/fixtures/indiamart_snapshot_<id>.json` — hoy hay un mock fabricado.
- Actualizar `docs/fase3/README.md` marcando este handoff como **abierto** (fecha 2026-04-21) — cerrarlo cuando el vendor entregue y los tests corran end-to-end.

---

## 11. Qué NO hacer

- **No reimplementar parsing del product/supplier** dentro del middleware. El JS scraper (cuando exista) ya extrae JSON-LD + breadcrumb + spec table según spec §4/§5/§6. El middleware solo renombra/coerciona.
- **No modificar el schema §2** sin pasar por re-spec explícita.
- **No mutar `NORMALIZED_CODES`** de `core/errors.py`. Extender localmente vía `INDIAMART_ERROR_CODES`.
- **No saltarse el cap `max_products`/`max_suppliers`** — el clipping post-download es parte del contrato del middleware.
- **No hardcodear el resource id** ni la API key en `config.py`. Todo viene de env vars.
- **No crear `client_v1.py` / `client_v2.py`** — versionado por git commit.
- **No inventar campos** fuera de spec §4/§6 salvo vía `extra="allow"`. Si un campo nuevo es candidato al catálogo, actualizar spec primero.
- **No interpretar `type="chemical"` como discriminador de entidad** — es campo de producto §8. El discriminador es `entity` o, literalmente, `type == "product" | "supplier"`.
