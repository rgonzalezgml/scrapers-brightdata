# cosme — errors y gotchas del sitio

Log vivo de problemas **específicos de cosme.net** encontrados durante runs. Errores del runtime de BrightData van en `/workspace/docs/specs/brightdata-errors.md`.

---

## E1 — Encoding Shift_JIS mal declarado

**Síntoma**: texto japonés corrupto (mojibake) si se asume UTF-8 ciegamente sobre el HTML del sitio.

**Causa**: cosme.net sirve Shift_JIS pero el header o meta charset no siempre declara correctamente; el MCP de BrightData al convertir a markdown muestra mojibake pero los enlaces/IDs quedan legibles.

**Fix**: precondición de decoding en sc_code antes de extraer.
```js
// Pedir body como buffer crudo
const body = request({url, encoding: null});
// Probar UTF-8 y validar que contenga al menos un char hiragana/katakana/kanji Y cero U+FFFD
let html = body.toString('utf-8');
const has_jp = /[぀-ゟ゠-ヿ一-龯]/.test(html);
const has_replacement = /�/.test(html);
if (!has_jp || has_replacement) {
  html = iconv.decode(body, 'shift_jis');
  scraper_flags.push('shift_jis_fallback');
}
```

---

## E2 — `/products/{id}/`, `/categories/item/{id}/ranking`, `/brands/{id}/product/` bloqueadas por geo

**Síntoma**: body menor a 10 KB + string literal `ご利用の環境からはアクセスできません` (bloqueo geo japonés).

**Causa**: el sitio requiere IP japonesa residencial. Proxy no-JP recibe 200 con pantalla de bloqueo.

**Fix**: `country('jp')` con zona residencial; si persiste tras 3 retries, `collect` fila con `blocked=true` + flag `blocked_retried`. Nunca seguir con página sospechosa aunque HTTP sea 200.

---

## E3 — `/brands/{id}/` sin `?nt=1` redirige a tieup PR

**Síntoma**: scrapeando `/brands/73/` devuelve página advertorial en vez de info de marca.

**Causa**: el sitio redirige la URL "desnuda" a un tieup de PR. La URL canónica requiere `?nt=1`.

**Fix**: siempre usar `/brands/{id}/?nt=1`. Para paginación de productos, usar `/brands/{id}/product/`.

---

## E4 — `price_text` fila `容量・税込価格` vs markdown muestra `希望小売価格`

**Síntoma**: el parser no encuentra la fila de precio si usa el header que vio en markdown.

**Causa**: el MCP convierte la tabla a markdown con un header distinto del DOM real. El DOM tiene `税込価格` (precio con impuestos); el markdown rinde `希望小売価格` (precio sugerido).

**Fix**: parser prueba ambos labels.

---

## E5 — `/categories/item/{id}/ranking` a veces bloquea, tomar id 800 como primary fixture

**Síntoma**: `/categories/item/802/` devolvió bloqueo en exploración inicial.

**Causa**: geo / rate limit.

**Fix**: `800` (skincare) es el id confirmado funcional; usar como fixture principal.

---

## E6 — `/bestcosme/archive/{year}/` devuelve 404 para el año en curso (y futuros)

**Síntoma**: Stage 1 del collector `c_mo7zv65x2914uyi2n4` (vendor v4 integration code) arranca en `https://www.cosme.net/bestcosme/archive/2025/` o `.../2026/` y t+60s después emite snapshot `{"status":"empty"}` sin rows. El middleware por default envía esa URL (`middlewares/cosme/config.py` `ARCHIVE_ROOT_URL_TMPL`).

**Causa**: `https://www.cosme.net/bestcosme/archive/{year}/` es `404 Not Found` a nivel servidor para `{year}` del año en curso / futuro (verificado 2026-04-22: 2025 → 404 con `<title>ページが見つかりません 404 Not Found...</title>`; 2026 → idem). Solo los años **cerrados** (2000…2024 al día de hoy) tienen una página real en esa ruta. Para el año en curso la **página de descubrimiento canónica es el hub** `https://www.cosme.net/bestcosme/` (también 200 OK, título `@cosmeベストコスメアワード2025`), que lista los mismos sub-paths (`/archive/2025/grand/`, `/archive/2025/hall/`, `/archive/2025/rookie/`, 63 `/archive/2025/category/{slug}/`, 6 `/archive/2025/category-group/{slug}/`, más awards nuevos como `shopping-rookie`, `store-rookie`, `high-price`, `mid-price`, `low-price`, `shopping`, `store`, `shopping-brand`, `store-brand`).

El vendor Stage 1 parser confía en que `location.href` contiene `/bestcosme/archive/{year}/` y que el DOM tiene anchors absolutos a `a[href*="/bestcosme/archive/{year}/category/"]`. Sobre una 404 page vacía esas queries retornan `[]` y el integration code emite 0 `next_stage()`s → el collector termina sin rows.

**Fix (v1)**: en el Stage 1 interaction code, **detectar** si después del `navigate()` la URL hace 404 (título `ページが見つかりません` o ausencia total de `a[href*="/bestcosme/archive/"]`). En ese caso, volver a `navigate('https://www.cosme.net/bestcosme/')` (el hub) y parsear desde ahí. Derivar `award_year` del primer anchor `a[href*="/bestcosme/archive/20XX/grand/"]` del DOM (no de la URL seed, que mintió). El parser no cambia nada en los selectores — `a[href*="/bestcosme/archive/${year}/grand/"]` funciona igual en el hub que en una archive root de año viejo. Mantener el branch original para años viejos (`/archive/2024/` etc.) que sí devuelven 200.

**Verificación wire-level (2026-04-22 vía curl)**:
- `GET /bestcosme/archive/2025/` → HTTP 200 pero body = 404 HTML, **0 matches** de `href="[^"]*bestcosme/archive/2025/"` en todo el payload.
- `GET /bestcosme/archive/2026/` → idem.
- `GET /bestcosme/archive/2024/` → HTTP 200 real, **63 matches** de `bestcosme/archive/2024/category/{slug}/`.
- `GET /bestcosme/` → HTTP 200 real, hub con los 3 awards + 63 category + 6 category-group para `archive/2025`.

---

## E7 — Vendor parser pre-wrap de Cheerio en array (diagnóstico parcial; ver E8 para el root cause real)

**Síntoma inicial (2026-04-22 mañana)**: al intentar guardar el collector `c_mo7zv65x2914uyi2n4` con los archivos v1 de cosme, BrightData Scraper Studio rechaza con:

```
Can't save since preview errored on step 2:
  Crawler error: (intermediate value).text is not a function
```

"Step 2" = el Stage 2 del collector (sc_code FETCH de producto).

**Hipótesis inicial (equivocada parcialmente)**: el bloque Source-1 del cascade de `product_name_raw` guardaba `$(el)` Cheerio pre-wrapped en un array y luego llamaba `.text()` sobre un elemento indexado:

```js
const candidates = crumbContainer.find('strong, span, a').toArray()
  .map(el => $(el))                // ← pre-wrap Cheerio en Array plano
  .filter($el => { const t = $el.text().trim(); ... });
const cand = candidates[candidates.length - 1].text().trim();
```

**Fix parcial aplicado (v1, `scrapers/cosme/sc_code/parser_code_v1.js`)**: mantener DOM elements crudos en el array y re-envolver con `$()` en el punto de uso (patrón R12 canónico). El cambio es correcto y se mantiene en v2 como defensa en profundidad, pero **no era la causa del preview error**.

**Por qué el diagnóstico fue parcial**: tras aplicar el fix, el preview siguió fallando con el mismo mensaje. El log de Scraper Studio agregó una línea nueva que cambió todo:

```
[20:21:33] $("body")
[20:21:33] Crawler error: (intermediate value).text is not a function
```

El `.text()` que rompía era el **primero del archivo** (línea 178: `const bodyText = $('body').text();`), muy antes de entrar al bloque breadcrumb. La raíz era otra. Ver **E8** abajo.

---

## E8 — `parse({html: ...})` es canal inválido en sc_code; `$` queda sin bindear

**Síntoma**: tras el fix parcial E7, el preview de `c_mo7zv65x2914uyi2n4` sigue rebotando con:

```
[20:21:33] $("body")
[20:21:33] Crawler error: (intermediate value).text is not a function
TypeError: (intermediate value).text is not a function
```

La línea apuntada es la primera llamada `.text()` del parser (línea 178, `const bodyText = $('body').text();`). Esto es antes del bloque breadcrumb; el fix E7 corrigió un bug latente distinto.

**Causa**: el **vendor** Stage 2 interaction code (y su copia literal en `sc_code/interaction_code_v1.js`) invoca:

```js
navigate(input.url);
const response = request({ url: input.url, encoding: null });
// ... decodificación manual con iconv-lite ...
collect(parse({ html: decoded_html, shift_jis_fallback: true }));
```

El problema son los argumentos de `parse()`. Por runtime-rule **R2** (`docs/specs/brightdata-errors.md`), `parse()` valida su input contra el schema del scraper y rechaza (o, peor, deja el runtime en estado raro) cualquier campo no declarado. `html` y `shift_jis_fallback` no son campos del schema de cosme. El efecto observado es que **`$` queda sin bindear a un cheerio wrapper válido**: `$('body')` devuelve algo que no expone `.text()` en su prototipo.

Nunca hubo un run real que ejecutara este código path con éxito contra BrightData (el vendor lo shipeo antes del intento de save del collector). Es un bug latente del vendor que solo salta ahora porque recién ahora se intenta guardar el collector.

El canal correcto para decodificar Shift-JIS manualmente en sc_code — documentado en la skill `scraper-implementation` §4 (DSL reference → `load_html(html)`) y §7 ("Encoding no-UTF-8") — es:

```js
const response = request({ url: input.url, encoding: null });
// ... decodificar con iconv-lite ...
load_html(decoded_html);   // rebinda $ al HTML decodificado
collect(parse());          // parse() SIN args (R9 de la skill / R2 runtime)
```

`load_html()` es una primitiva explícita de sc_code para cargar una cheerio instance ad-hoc. El vendor la ignoró y trató de sideloadar el HTML vía `parse()`, lo cual no es un canal soportado.

**Fix (v2, `scrapers/cosme/sc_code/interaction_code_v2.js` + `parser_code_v2.js`)**:

1. *Integration*: reemplazar `collect(parse({html, shift_jis_fallback}))` por `load_html(decoded_html); collect(parse());`. Degraded path (si `request()` tira): bare `parse()` contra lo que dejó `navigate()`.
2. *Parser*: eliminar el bloque que lee `input.shift_jis_fallback` (esa llave nunca llegó realmente al parser por la ruta válida). La detección de mojibake ya existía self-contained en el parser (líneas 179-186 de v1) y sigue siendo la única fuente del flag `shift_jis_fallback`.

No cambia ningún selector, ninguna regla de extracción, ningún campo del output. Solo corrige el binding de `$`.

**Nota sobre E7**: el fix del array de breadcrumb (E7) se mantiene en v2 — es R12 canónico y habría sido un bug latente eventual. Lo que se corrige con E7 es "real pero no bloqueaba preview". E8 es "no real hasta que se intenta save preview, y sí bloquea".

**Verificación pendiente en BrightData Scraper Studio (a cargo del usuario)**:

1. Pegar `scrapers/cosme/sc_code/interaction_code_v2.js` en el step 2 del collector `c_mo7zv65x2914uyi2n4` (reemplazar el interaction code actual).
2. Pegar `scrapers/cosme/sc_code/parser_code_v2.js` en el parser del step 2.
3. Click **Preview**. Criterio de éxito:
   - NO aparece `Crawler error: (intermediate value).text is not a function`.
   - El preview sample muestra un objeto con `product_id`, `brand_name`, `product_name_raw` poblados (o al menos `$('body')` ejecutándose sin tirar).
4. Si preview pasa → click **Save**. El collector debería guardar sin rechazo.
5. Si el preview sigue rompiendo: capturar el log de Scraper Studio COMPLETO y pasarlo al orquestador — significaría que `load_html()` también tiene un comportamiento distinto del que asume la skill.

**Verificación local**: `node --check` limpio en ambos archivos (chequeo sintáctico).

---

## Patrón de contribución

Cada run fallido → `E{N+1}` con: síntoma, causa, fix. Si el error es del runtime (no del sitio), va en `docs/specs/brightdata-errors.md`.
