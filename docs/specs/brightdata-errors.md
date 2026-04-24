# BrightData errors y runtime constraints (cross-scraper)

Log vivo de errores del runtime de BrightData Scraper Studio que aplican a **todos** los scrapers del proyecto. Se alimenta de reportes de runs fallidos. Consultar antes de proponer cambios en `interaction_code` o `parser_code`.

Errores **específicos de un sitio** (selectores cambiados, CAPTCHA específico, encoding raro) van en `scrapers/<name>/results/errors.md`, no aquí.

---

## R1 — `navigate()` solo plano top-level

**Error observado**: `Crawler error: async code is not allowed in sync functions`.

**Causa**: `navigate()` es **async internamente**. El runtime solo lo acepta cuando se invoca directamente en el scope top-level de `interaction_code.js`. Envolverlo en cualquier función síncrona (helper, for-loop con await, try/catch, setTimeout) rebota.

**Prohibido**:
```js
function navigateWithRetry(url) {
  for (let i = 0; i < 3; i++) {
    try { navigate(url); break; } catch (e) { sleepSync(1000); }
  }
}
const doNav = (url) => navigate(url);
setTimeout(() => navigate(url), 1000);
```

**Correcto**:
```js
navigate(input.url);  // plano, top-level
wait('h1');
// lógica posterior puede estar en helpers síncronos, el problema es SOLO navigate()
```

**Fix si necesitás retry**: dejar que la plataforma retire con nueva peer session a nivel de job. NO loops custom.

---

## R2 — `parse()` sin argumentos (valida schema)

**Error observado**: `parse validation error: [0].<field> is not allowed`.

**Causa**: `parse()` valida el input contra el schema del scraper y rechaza campos no declarados. Llamar `parse({foo: 'bar'})` con un campo no en el schema rompe.

**Correcto**:
- `parse()` sin args — el parser deriva del DOM y `location.href`.
- Para pasar datos a la próxima etapa, usar el "sidecar" de `next_stage({campo: valor})` — ese payload NO pasa por `parse()`.

**Ejemplo Stage 1 → Stage 2**:
```js
// Stage 1: derivar year del location.href, pasarlo via next_stage
const year = location.href.match(/\/archive\/(\d+)\//)?.[1];
next_stage({ url, year, page_type: 'category' });

// Stage 2: leer input.year directo, NO parse({year})
navigate(input.url);
collect({ ...parse(), year: input.year });
```

---

## R3 — Funciones Browser-only rompen en Code worker

**Error observado**: al cambiar el worker type, funciones como `wait`, `click`, `tag_response`, `solve_captcha` lanzan errores porque el Code worker no tiene browser.

**Browser-only** (lanza error en Code worker): `wait`, `wait_any`, `wait_visible`, `wait_hidden`, `wait_for_text`, `wait_for_parser_value`, `wait_network_idle`, `wait_page_idle`, `click`, `right_click`, `hover`, `mouse_to`, `type`, `press_key`, `select`, `scroll_to`, `scroll_to_all`, `load_more`, `close_popup`, `solve_captcha`, `bounding_box`, `el_exists`, `el_is_visible`, `tag_response`, `tag_all_responses`, `tag_script`, `tag_window_field`, `tag_image`, `tag_video`, `tag_screenshot`, `tag_download`, `tag_serp`, `capture_graphql`, `browser_size`, `emulate_device`, `font_exists`, `freeze_page`, `track_event_listeners`, `disable_event_listeners`, `html_capture_options`.

**Fix**:
- En sc_code/ solo usar: `navigate/request`, `parse`, `collect`, `next_stage/run_stage/rerun_stage`, `load_sitemap`, `resolve_url`, `response_headers`, `status_code`, `load_html`, `country`, `proxy_location`, `preserve_proxy_session`, `set_session_cookie`, `set_session_headers`, constructores (`Money`, `URL`, `Image`, `Video`).
- Regla general: empezar con Code worker; cambiar a Browser solo si el raw HTML no tiene el dato.

---

## R4 — Dead page detection nunca en try/catch

**Error observado**: `wait()` timeout hace que el worker muera con parcial; try/catch alrededor no captura de forma confiable y mezcla con R1.

**Prohibido**:
```js
try { wait('.product-title'); } catch (e) { dead_page('not found'); }
```

**Correcto**:
```js
wait('.product-title, .not-found-banner');
if (el_exists('.not-found-banner')) dead_page('not found');
```

---

## R5 — Timeouts mayores a 60s enmascaran problemas

**Error observado**: páginas que "cargan en 2 minutos" casi siempre están bloqueadas o tienen un bug de selector; el wait eventual devuelve basura.

**Correcto**:
- Default 30s → usar salvo evidencia concreta de lentitud.
- 45-60s solo con evidencia documentada.
- **Nunca 120s**. Si una página no responde en 60s, hay otra cosa rota.

---

## R6 — `rerun_stage()` paralelo, no secuencial

**Error observado**: llamar `rerun_stage()` dentro de cada página serializa todo el crawl (1 página a la vez) y multiplica el tiempo de corrida.

**Prohibido**:
```js
navigate(input.url);
// ...parse...
if (has_next_page) rerun_stage({page: input.page + 1});
```

**Correcto**:
```js
navigate(input.url);
if (input.page) return;  // ya es un rerun, solo procesar ésta

const total = Math.ceil(total_items / per_page);
for (let page = 2; page <= total; page++)
  rerun_stage({ url: input.url, page });  // todos se paralelizan
```

---

## R7 — Popups con `close_popup()` watcher, no polling

**Error observado**: polling con `wait_visible('.popup', {timeout: 5000})` agrega 5s a cada navigate cuando el popup no aparece; cuando aparece a mitad de click bloquea la interacción.

**Prohibido**:
```js
navigate(url);
if (el_exists('.cookie-popup')) click('.cookie-close');
click('.open-product');  // si popup aparece aquí, falla
```

**Correcto**: registrar watcher en background al inicio del stage.
```js
close_popup('.cky-btn-accept', '.cky-btn-accept');  // dispara en cualquier momento
navigate(url);
click('.open-product');
```

---

## R8 — Tagged responses + `wait_for_parser_value()`

**Error observado**: `tag_response()` captura pero `parse()` corre antes de que la respuesta llegue → parser ve `parser.api_data === undefined`.

**Correcto**:
```js
tag_response('api_data', /api\/products/);
navigate(url);
wait_for_parser_value('api_data.items.0');  // asegura llegó
collect(parse());
```

---

## R9 — `text_sane()` siempre, no `.text().trim()`

**Error observado**: `$(sel).text().trim()` deja dobles espacios del HTML (`"  foo   bar\n baz  "` → `"foo   bar\n baz"`) que rompen regex de parsing downstream.

**Correcto**: `$(sel).text_sane()` → `"foo bar baz"` (whitespace colapsado + trim).

---

## R10 — `.toArray().map()` no `.each()`

**Error observado**: `.each()` con push a array externo es más verboso, menos legible y rompe patrones funcionales.

**Prohibido**:
```js
let arr = [];
$('.item').each((_, el) => arr.push($(el).attr('href')));
```

**Correcto**:
```js
const arr = $('.item').toArray().map(el => $(el).attr('href'));
```

---

## R11 — Parser sin try/catch en accesos

**Error observado**: try/catch escondía `undefined` en nested access y emitía `null` silencioso donde había un bug real.

**Prohibido**:
```js
let price;
try { price = data.offers[0].price.amount; } catch { price = null; }
```

**Correcto**: optional chaining + nullish coalescing explícitos.
```js
const price = data?.offers?.[0]?.price?.amount ?? null;
```

---

## R12 — Error handling con las 3 funciones del runtime

En lugar de try/catch o logging, usar las señales declarativas del runtime:

| Función | Cuándo | Efecto |
|---|---|---|
| `bad_input(msg)` | input malformado / falta campo requerido | **No retry**. El job marca input inválido. |
| `blocked(msg)` | CAPTCHA, body < 10KB con "Access Denied", redirect a login | `error_code=blocked`. Plataforma retira con **nueva peer session**. |
| `dead_page(msg)` | 404, 410, product eliminado | **No retry**. Link muerto. |
| `detect_block({selector}, {exists?, has_text?})` | check declarativo al inicio | Equivale a `blocked()` si matchea |

---

## Patrón de contribución al archivo

Cada vez que un run falla con un error nuevo del runtime:

1. Copiar el mensaje literal de error al principio de la sección nueva (`**Error observado**:`).
2. Explicar la causa en 1-2 líneas.
3. Mostrar el bloque **Prohibido** que lo disparó.
4. Mostrar el bloque **Correcto** que lo evita.
5. Numerar la regla como `R{N+1}`.

Si el error es **específico de un sitio** (selector, encoding, taxonomía), va en `scrapers/<name>/results/errors.md`, no acá.
