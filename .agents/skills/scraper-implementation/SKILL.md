---
name: scraper-implementation
description: >
  Iterar v1 → v2 → vN de un scraper (sc_browser/*.js, sc_code/*.js) en
  /workspace/scrapers/<name>/. Cubre la DSL completa de BrightData Scraper
  Studio (navigate/wait/parse/collect/next_stage/tag_*/...), el modelo de
  2 workers (Browser vs Code), reglas de mejores prácticas y patrones por
  tipo de sitio. Usar cuando el usuario sube un result al registry y pide
  proponer la próxima versión, o cuando hay que escribir/corregir parser o
  interaction code.
---

# SKILL: scraper-implementation

Etapa 2 del flujo de scrapers del proyecto (Etapa 1 = análisis/spec, skill `scraper-spec-analysis`).
Memoria canónica: `/workspace/docs/specs/memory.md`. Biblia del runtime: **BrightData Scraper Studio**.

---

## 1. Cuándo se activa

- Usuario dice: "arrancá v2 de X", "corregí el parser", "proponé fixes para v3".
- Usuario sube un JSON a `scrapers/<name>/results/` y pide la próxima versión.
- Hay un gap claro entre output del scraper y schema §2 de la spec.
- Hay que agregar/cambiar selectores, validación, skip rules, flags.

Antes de empezar, **leer en este orden**:
1. Spec completa del scraper: `docs/specs/scrapers/<name>.md`.
2. Runtime errors cross-scraper: `docs/specs/brightdata-errors.md` (R1..RN).
3. Errors del sitio específico: `scrapers/<name>/results/errors.md` (E1..EN).
4. Registry: `scrapers/<name>/results/registry.md`.
5. JSON más reciente en `scrapers/<name>/results/`.

Los dos archivos de errores son la memoria de qué NO repetir. Si un gap ya está documentado ahí con fix propuesto, aplicar el fix en vez de re-descubrirlo.

---

## 2. Arquitectura de 2 capas (obligatorio entenderla)

Todo scraper de BrightData tiene **dos archivos por modo**:

```
sc_browser/    ← Browser worker (headless browser con JS)
  interaction_code_vN.js   ← orquestación: navigate, wait, click, tag_*, parse, collect, next_stage
  parser_code_vN.js        ← extracción: usa $ (cheerio) sobre el HTML/DOM

sc_code/       ← Code worker (HTTP puro, sin browser — como curl)
  interaction_code_vN.js   ← navigate/request, parse, collect, next_stage (sin wait/click/tag_*)
  parser_code_vN.js        ← igual: extracción con $
```

**Flujo**: `interaction_code` carga la página, llama `parse()` que ejecuta `parser_code`, luego `collect()` empuja los datos al output.

```js
// interaction_code_v1.js
navigate(input.url);
wait('h1');
let data = parse();          // ejecuta parser_code, retorna su return
collect(data);               // append al output stream

// parser_code_v1.js
return {
  title: $('h1').text_sane(),
  price: new Money(100, 'USD'),
};
```

**Multi-stage** (para catálogos / listados → detalle):

```js
// Stage 1: discovery
navigate(input.url);
wait('.product-grid');
const { urls } = parse();
for (const url of urls) next_stage({ url });

// Stage 2: detail
navigate(input.url);
wait('h1');
collect(parse());
```

Cada stage es una sesión nueva; BrightData paraleliza.

---

## 3. Browser worker vs Code worker

| | Browser | Code |
|--|---|---|
| JS render | ✅ | ❌ |
| Click/scroll/type/hover | ✅ | ❌ |
| `wait*`, `tag_*`, `solve_captcha`, `close_popup` | ✅ | ❌ lanza error |
| Performance | Lento (startup + page load) | Rápido (1 HTTP roundtrip) |
| Costo | Alto | Bajo |

**Regla**: empezar con **Code**. Cambiar a Browser **solo si el dato no está en el HTML crudo** (o si la página requiere interacción, login, popup-close, network tagging).

**Browser-only** (lanzan error en Code): `wait`, `wait_any`, `wait_visible`, `wait_hidden`, `wait_for_text`, `wait_network_idle`, `wait_page_idle`, `click`, `right_click`, `hover`, `mouse_to`, `type`, `press_key`, `select`, `scroll_to`, `scroll_to_all`, `load_more`, `close_popup`, `solve_captcha`, `tag_response`, `tag_all_responses`, `tag_script`, `tag_window_field`, `tag_image`, `tag_video`, `tag_screenshot`, `tag_download`, `tag_serp`, `capture_graphql`, `browser_size`, `emulate_device`, `freeze_page`.

**En sc_code/**: solo `navigate()` o `request()`, `parse()`, `collect()`, `next_stage()`, `run_stage()`, `rerun_stage()`, `load_sitemap()`, `resolve_url()`, `redirect_history()`, `response_headers()`, `status_code()`, `load_html()`, `country()`, `proxy_location()`, `preserve_proxy_session()`, `set_session_cookie()`, `set_session_headers()`, constructores (`Money`, `URL`, `Image`, `Video`).

---

## 4. DSL reference — interaction code

### Navegación

| Función | Parámetros | Retorna | Nota |
|---|---|---|---|
| `navigate(url, opt?)` | `opt: {wait_until: 'load'|'domcontentloaded'|'networkidle0'|'networkidle2', timeout: ms, referer, allow_status: number[], fingerprint}` | — | Carga URL |
| `request(url \| {url, method, headers, body})` | HTTP directo sin browser | — | Útil en sc_code para POST/PUT |
| `next_stage(input)` | `input` object | — | Queue para próxima etapa, nueva sesión |
| `run_stage(n, input)` | `n: number` | — | Ejecuta etapa nombrada |
| `rerun_stage(input)` | `input` | — | Re-ejecuta ACTUAL (paginación) |
| `load_sitemap({url})` | — | `{pages}` o `{children}` | XML sitemap |
| `resolve_url(url)` | — | URL final tras redirects | |
| `redirect_history()` | — | `string[]` | Chain de redirects |
| `response_headers()` | — | `{...}` | Headers del último load |
| `status_code()` | — | `number` | HTTP status |

### Waits (browser-only)

| Función | Ejemplo |
|---|---|
| `wait(sel, {timeout=30000, hidden, inside})` | `wait('.product', {timeout: 45000})` |
| `wait_any([sels])` | `wait_any(['#title', '#notfound'])` |
| `wait_visible/wait_hidden/wait_for_text` | — |
| `wait_for_parser_value(field, validate_fn?, {timeout})` | `wait_for_parser_value('listings.0.price', v => parseInt(v) > 0)` |
| `wait_network_idle({timeout, ignore})` | Espera red quieta |
| `wait_page_idle({idle_timeout, ignore})` | Espera DOM quieto |

### Interacción (browser-only)

`click(sel | [sel,shadow,sel], {coordinates})`, `right_click`, `hover`, `mouse_to(x,y)`, `type(sel, text | ['text','Enter'], {replace})`, `press_key`, `select(sel, value)`, `scroll_to(target, {immediate})`, `scroll_to_all(sel)`, `load_more(container, {children, trigger_selector, timeout})`, `close_popup(popup_sel, close_sel, {click_inside})`, `solve_captcha({type?})`, `el_exists(sel, timeout?)`, `el_is_visible(sel, timeout?)`, `bounding_box(sel)`.

### Network tagging (browser-only, crítico para SPAs)

```js
tag_response('products', /api\/search/, {jsonp: true});
navigate(url);
wait_network_idle();
let data = parse();  // en parser: parser.products tiene la respuesta
```

| Función | Uso |
|---|---|
| `tag_response(field, pattern, {jsonp, allow_error})` | 1 respuesta que matchea |
| `tag_all_responses(field, pattern)` | array de respuestas |
| `tag_script(field, sel)` | JSON desde `<script>` |
| `tag_window_field(field, key)` | `window.__KEY__` |
| `tag_image/tag_video/tag_screenshot/tag_download/tag_serp` | captura archivos |
| `capture_graphql({payload, url?})` | graphql replay |

### Data

| Función | Uso |
|---|---|
| `parse()` | ejecuta parser_code, retorna su return |
| `collect(data, validate_fn?)` | append record a output |
| `set_lines([...])` | override output (idempotent) |
| `load_html(html)` | cheerio instance ad-hoc |

### Error handling

```js
if (status_code() === 404) dead_page('removed');
if ($('.captcha').length) blocked('captcha');
if (!input.url) bad_input('missing url');
detect_block({selector: '.waf-ban'}, {exists: true});
```

- `bad_input(msg)` — input inválido, **no retry**.
- `blocked(msg)` — sitio bloquea (`error_code=blocked`), plataforma retries con peer nuevo.
- `dead_page(msg)` — link muerto (`error_code=dead_page`), **no retry**.
- `detect_block({selector}, {exists?, has_text?})` — check declarativo.

### Session & routing

```js
country('us');
proxy_location({country: 'us', lat: 37.77, long: -122.42, radius: 100});
preserve_proxy_session();  // reusar peer en child stages
set_session_cookie('example.com', 'session_id', 'abc123');
set_session_headers({'X-Custom': 'value'});
```

### Constructores (usar cuando BrightData los espera)

`new Money(value, currency)`, `new URL(href)`, `new Image(src)`, `new Video(src)`.

---

## 5. DSL reference — parser code

### Globals disponibles

| Nombre | Tipo | Uso |
|---|---|---|
| `$` | Cheerio | HTML cargado |
| `input` | object | Stage input actual |
| `location` | `{href}` | URL actual |
| `parser` | object | Datos `tag_*` de interaction |

### Custom cheerio

- `$(sel).text_sane()` — whitespace colapsado + trim. **Usar siempre** en vez de `.text().trim()`.
- `$(sel).filter_includes(text)` — filtrar selección por substring (chainable).

### Ejemplo bien estructurado

```js
// Leer JSON-LD (recomendado para sitios con structured data)
const ld = [];
$('script[type="application/ld+json"]').each((_, el) => {
  try { ld.push(JSON.parse($(el).html())); } catch {}
});
const product = ld.flat().find(x => x?.['@type'] === 'Product');

return {
  product_id: input.url.match(/product-detail\/.*?_(\d+)/)?.[1] ?? null,
  name: product?.name ?? $('h1').text_sane(),
  price_min_usd: product?.offers?.price ? Number(product.offers.price) : null,
  price_currency: product?.offers?.priceCurrency ?? 'USD',
  image: product?.image ?? $('meta[property="og:image"]').attr('content') ?? null,
};
```

---

## 6. Best practices (reglas duras, no sugerencias)

### R1 — Dead page detection

❌ **No envolver `wait()` en try/catch** para llamar `dead_page()` en el catch. El runtime no lo acepta siempre y puede romper con `async code is not allowed in sync functions`.

✅ Usar `wait_any` y condicional:
```js
wait('.product, .not-found');
if (el_exists('.not-found')) dead_page();
```

### R2 — Request batching

❌ `if (!el_exists('#a') && !el_exists('#b') && !el_exists('#c'))` — 3 trips.
✅ `if (!el_exists('#a, #b, #c'))` — 1 trip.

### R3 — Paginación paralela

❌ Paginación secuencial con `rerun_stage` dentro de cada página (serializa todo).
✅ `rerun_stage()` una vez desde la raíz con bucle for:
```js
let url = new URL(input.url);
if (input.page) url.searchParams.set('page', input.page);
navigate(url);
if (input.page) return;  // ya es rerun, solo procesar ésta

const total = Math.ceil(total_products / 20);
for (let page = 2; page <= total; page++)
  rerun_stage({ url: input.url, page });
```

### R4 — Popups

❌ Polling con `wait_visible()` antes de cada interacción.
✅ Watcher en background:
```js
close_popup('.cky-btn-accept', '.cky-btn-accept');
navigate(url);
click('.open-product');
```

### R5 — Timeouts

- Default 30s para `wait()`. **Usar el default**.
- 45-60s solo si página confirmada lenta.
- **Nunca 120s** — enmascara problemas reales.

### R6 — Retries

❌ Loops de retry manuales en interaction code.
✅ Dejar que la plataforma retire con nueva peer session al nivel de job.

### R7 — Parser: sin try/catch en accesos

❌ `try { x = obj.a.b.c } catch { x = null }`
✅ `x = obj?.a?.b?.c ?? null`

### R8 — Navigate solo top-level (descubierto empíricamente en cosme v5.2)

`navigate()` es async internamente. Solo se acepta plano en el scope top-level del archivo. Envolverlo en `function retry() { ... }` rebota con `async code is not allowed in sync functions`.

### R9 — parse() sin args

`parse()` valida input contra schema y rechaza campos no declarados. Llamar `parse()` sin args; el parser deriva del DOM y `location.href`. Para pasar datos a stage siguiente, usar `next_stage({campo: valor})`.

### R10 — Tagged responses + wait

Siempre seguir `tag_response()` con `wait_for_parser_value()` para asegurar que la respuesta llegó antes de `parse()`:
```js
tag_response('api_data', /api\/products/);
navigate(url);
wait_for_parser_value('items.0');
collect(parse());
```

### R11 — text_sane siempre

`$(sel).text().trim()` deja doble-espacios. Usar `$(sel).text_sane()`.

### R12 — .map((_,el)=>...).get() no .each()

❌ `let arr = []; $('.item').each((_,el) => arr.push(...))`
✅ `let arr = $('.item').map((_, el) => $(el).attr('href')).get()`

**Portabilidad Browser vs Code worker** (descubierto empíricamente en
indiamart sc_browser/parser_code_v2.js, 2026-04-23):

`$(sel).toArray().map(fn)` funciona en **Code worker** (cheerio full)
pero rompe en **Browser worker** del runtime actual con
`TypeError: (intermediate value).toArray is not a function`. El wrapper
DOM-cheerio del headless no expone `.toArray()` en todas las versiones
del runtime.

El patrón `$(sel).map((_, el) => ...).get()` es el jQuery/cheerio core
portable y funciona en ambos workers. Usarlo siempre en sc_browser/.
En sc_code/ cualquiera de los dos es aceptable, pero por consistencia
cross-worker preferir el mismo patrón.

---

## 7. Patrones por tipo de sitio

### Marketplace B2B con JSON-LD (alibaba, made-in-china, indiamart)
Preferir JSON-LD Product + BreadcrumbList sobre selectores DOM. El JSON-LD es más estable.

```js
// Patrón portable Browser + Code worker (ver R12).
const lds = $('script[type="application/ld+json"]')
  .map((_, el) => { try { return JSON.parse($(el).html()); } catch { return null; } })
  .get()
  .filter(Boolean)
  .flat();
const product = lds.find(x => x?.['@type'] === 'Product');
const breadcrumb = lds.find(x => x?.['@type'] === 'BreadcrumbList');
const category_path = breadcrumb?.itemListElement?.map(x => x.item.name).slice(1) ?? [];
```

### SPA con API interna (olive-young)
Usar `tag_response` para capturar el JSON en red; parser lee de `parser`.
```js
tag_response('detail', /product-detail-data/);
navigate(url);
wait_for_parser_value('detail.productInfo');
collect(parse());
```

### Noticias Arc XP Fusion (cosmetics-design)
```js
tag_window_field('fusion', '__INITIAL_STATE__');
// parser: parser.fusion.globalContent es el objeto completo
```

### Encoding no-UTF-8 (cosme.net Shift_JIS)
En sc_code usar `request(encoding: null)` y decodificar manualmente con `iconv-lite` antes de `load_html()`.

### Consent wall / paywall
`close_popup` al inicio. Si el paywall oculta el contenido después de N pageviews, flaggear `paywalled: true` y seguir.

### Infinite scroll
```js
load_more('.results-container', { children: '.item', timeout: 10000 });
```

### Sitemap como seed
```js
const { pages } = load_sitemap({ url: 'https://site.com/sitemap.xml' });
for (const p of pages) next_stage({ url: p });
```

---

## 8. Flujo de iteración (v1 → v2 → ...)

1. **Leer inputs** (en este orden):
   - Spec: `docs/specs/scrapers/<name>.md` (§2 schema, §4-§9 reglas)
   - Runtime errors: `docs/specs/brightdata-errors.md` (R1..RN)
   - Site errors: `scrapers/<name>/results/errors.md` (E1..EN)
   - Último JSON: `scrapers/<name>/results/<archivo>.json`
   - Registry: `scrapers/<name>/results/registry.md`
   - Código actual: `scrapers/<name>/sc_browser/interaction_code_vN.js` + `parser_code_vN.js` (y sc_code)

2. **Gap analysis**:
   - Campos del schema §2 ausentes en el JSON → agregar a parser
   - Campos con null donde debería haber valor → selector roto, agregar fallback o JSON-LD
   - Flags esperados (§9 spec) no emitidos → agregar en interaction
   - Errores (`error_code=blocked/dead_page`) → agregar `detect_block` o `solve_captcha`
   - **Cross-referenciar contra `brightdata-errors.md` y `errors.md` del scraper** — si el gap ya aparece ahí con fix, aplicar ese fix; si es nuevo, agregar entrada tras resolverlo.

3. **Proponer v(N+1)**:
   - Crear `interaction_code_v{N+1}.js` y/o `parser_code_v{N+1}.js` al lado de los vN (no reemplazar).
   - Cada cambio debe atar a un gap concreto. No features extras.
   - Respetar R1-R12 (best practices).

4. **Reportar**:
   - Qué cambió (diff semántico, no literal).
   - Qué gap cierra cada cambio.
   - Qué queda abierto (dependencias del output real del vN+1).

5. **Documentar errores nuevos**: si el análisis encontró un error no listado:
   - Del **runtime** (mensaje genérico de BrightData): agregar `R{N+1}` a `docs/specs/brightdata-errors.md`.
   - Del **sitio**: agregar `E{N+1}` a `scrapers/<name>/results/errors.md`.

6. **Esperar**: el usuario corre vN+1 → nuevo JSON → nueva entrada en registry → iteración siguiente.

---

## 9. Qué NO hacer

- **NO editar `vendor/`** — es archivo histórico (v0).
- **NO inventar campos** fuera del schema §2 de la spec.
- **NO usar** `Math.random()` ni `Date.now()` como clave / id en parser (debe ser determinístico por input).
- **NO loops de retry** manuales.
- **NO try/catch** para esconder errores — usar `dead_page`, `blocked`, `bad_input`.
- **NO wrappers async** alrededor de `navigate()` (R8).
- **NO pasar args a `parse()`** — el runtime valida schema (R9).
- **NO mezclar entidades** en un solo `collect()` — si la spec distingue `product` y `supplier`, hacer 2 llamadas a `collect()` con `__schema: 'product'` / `'supplier'` o usar stages separados.
- **NO descontinuar versiones previas** — v1 queda al lado de v2 para A/B y rollback.

---

## 10. References (BrightData docs oficiales)

- Intro: https://docs.brightdata.com/datasets/scraper-studio/introduction.md
- Basics (2-phase, stages, workers): https://docs.brightdata.com/datasets/scraper-studio/basics-of-web-scraping.md
- Worker types (Browser vs Code): https://docs.brightdata.com/datasets/scraper-studio/worker-types.md
- **Functions reference completa**: https://docs.brightdata.com/datasets/scraper-studio/functions.md
- Best practices: https://docs.brightdata.com/datasets/scraper-studio/best-practices.md
- Develop a scraper: https://docs.brightdata.com/datasets/scraper-studio/develop-a-scraper.md
- IDE interface: https://docs.brightdata.com/datasets/scraper-studio/scraper-studio-ide-interface.md
- Self-healing tool: https://docs.brightdata.com/datasets/scraper-studio/self-healing-tool.md
- Specs/limits: https://docs.brightdata.com/datasets/scraper-studio/specifications.md

Llms.txt completo: `https://docs.brightdata.com/llms.txt`

---

## 11. Activación típica (ejemplo)

**Usuario**: "subí este json de made-in-china v1 a results/, armá v2 con los fixes necesarios".

**Flujo**:
1. `Read docs/specs/scrapers/made-in-china.md` (§2 schema, §4-§9 reglas).
2. `Read scrapers/made-in-china/results/<nuevo>.json`.
3. `Read scrapers/made-in-china/results/registry.md`.
4. `Read scrapers/made-in-china/sc_browser/interaction_code_v1.js` + `parser_code_v1.js`.
5. Diff output vs schema → lista de gaps.
6. Propuesta al usuario ANTES de codear: qué voy a cambiar en v2 y por qué.
7. Si ok → Write `interaction_code_v2.js` y/o `parser_code_v2.js` al lado de v1.
8. Agregar fila al registry con entrada inicial (tentative — el usuario la completa con "next run: v2").
9. Reportar al usuario con resumen de cambios.
