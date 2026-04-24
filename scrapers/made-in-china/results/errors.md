# made-in-china — errors y gotchas del sitio

Log vivo de problemas **específicos de made-in-china.com** encontrados durante runs. Errores del runtime de BrightData (no del sitio) van en `/workspace/docs/specs/brightdata-errors.md`.

Consultar antes de proponer v(N+1) de `sc_browser` o `sc_code`.

---

## E1 — `category_mic` hardcoded a "Oxide" en vendor v0

**Versión afectada**: `vendor/sc_code/parser_code.js`.

**Síntoma**: todo producto scrapeado emite `category_mic = "Oxide"` sin importar el breadcrumb real.

**Causa**: DB AI probó el scraper contra un solo fixture (N-Butyl Acetate, cuyo breadcrumb incluía "Oxide") y dejó hardcoded `$('.sr-QPWords-cont a[href*="Oxide"]').last().text_sane()`.

**Fix**: derivar del último item del `BreadcrumbList` JSON-LD:
```js
const bc = lds.find(x => x?.['@type'] === 'BreadcrumbList');
const items = bc?.itemListElement?.map(x => x.item.name) ?? [];
const category_mic = items[items.length - 1] ?? null;
const category_path = items.slice(1);  // sin "Home"
```

---

## E2 — `price_unit` contaminado del MOQ

**Versión afectada**: `vendor/sc_code/parser_code.js`.

**Síntoma**: `price_unit = "Ton"` cuando el producto es `$800/kg` con MOQ `1 Ton`.

**Causa**: vendor asigna `price_unit: moqData.unit` — usa la unidad del MOQ en vez del precio.

**Fix**: parsear el unit del `price_raw` del DOM o del offers del JSON-LD.
```js
const price_match = priceText.match(/US\$\s*[\d.,]+(?:-[\d.,]+)?\s*\/\s*([A-Za-z]+)/);
const price_unit = price_match?.[1]?.toLowerCase() ?? null;
```

---

## E3 — `supplier_country` no ISO-2

**Versión afectada**: `vendor/sc_code/parser_code.js`.

**Síntoma**: `supplier_country = "China"` literal; la spec §4 pide ISO-2 (`"CN"`).

**Causa**: vendor hace `addressText.split(',').pop().trim()`, que devuelve el nombre del país no el código.

**Fix**: mapa country name → ISO-2. Para MIC casi todos son `CN` porque el subdominio es `*.en.made-in-china.com`, pero hay excepciones (suppliers en Vietnam, Thailand, etc.).
```js
const COUNTRY_ISO = {
  'China': 'CN', 'Vietnam': 'VN', 'Thailand': 'TH', 'India': 'IN',
  'Taiwan': 'TW', 'Hong Kong': 'HK', 'South Korea': 'KR',
  // agregar según aparezcan
};
const country_name = addressText?.split(',').pop()?.trim();
const supplier_country = COUNTRY_ISO[country_name] ?? null;
```

---

## E4 — `supplier_audited` por image src (frágil)

**Versión afectada**: `vendor/sc_code/parser_code.js`.

**Síntoma**: `supplier_audited` inconsistente entre runs; depende de que la imagen `as-short.png` cargue y el selector `:has(img[src*="as-short.png"])` resuelva.

**Causa**: vendor usa `$('.sign-item:has(img[src*="as-short.png"])').length > 0`. El nombre del asset puede cambiar sin aviso del sitio.

**Fix**: buscar el texto literal "Audited Supplier" que la spec §6 declara:
```js
const supplier_audited = $('.sign-item, .bsc-item').toArray()
  .some(el => $(el).text_sane().includes('Audited Supplier'));
```

---

## E5 — `new URL()` como campo de retorno

**Versión afectada**: `vendor/sc_code/parser_code.js` línea 26, 75-77.

**Síntoma**: el campo `url` en el output es un objeto URL serializado raro, no un string.

**Causa**: `url: new URL(input.url)` — el constructor retorna un objeto, no string. Downstream ve `{"href":"...", "protocol":"...",...}`.

**Fix**: `url: input.url` directo, o `url: new URL(input.url).href` si hay que normalizar.

**Corrección 2026-04-21**: E5 fue diagnosticado mal. `url: new URL(input.url)` no es un bug — es el wrapper correcto para el tipo **URL** del Output Schema de BD Studio. El parser v2 lo removió por esta entrada del errors.md y rompió el schema (UI reportó `Expected URL, Actual Text` para `url`, `product_url`, `supplier_url`). **Restaurado en v3** para `product_url` y `supplier_url` (campos del §2 corregido). Este bloque queda como lección de "no modificar wrappers de tipo sin verificar contra el Output Schema del Studio".

---

## E6 — `new Money()` asumido sin confirmar que el runtime lo acepta

**Versión afectada**: `vendor/sc_code/parser_code.js` líneas 81-82.

**Síntoma**: TBD — hay que correr vendor y verificar si Money se serializa a `{amount, currency}` o si lanza error en el runtime de BrightData Scraper Studio actual.

**Nota**: según docs oficiales `new Money(value, 'USD')` está soportado. Confirmar en primer run y dejar o eliminar.

**Corrección 2026-04-21**: E6 nunca fue un bug. `new Money(value, 'USD')` es requisito del tipo **Price/Money** del Output Schema de BD Studio. Removerlo en v2 rompió la validación del schema (UI reportó `Expected Price/Money, Actual Number` para `price_min_usd` y `price_max_usd`). **Restaurado en v3** para `price_min_usd`, `price_max_usd` y `price_normalized_per_kg` (todos Price/Money en el §2 corregido). El null sigue siendo valor válido cuando no hay precio (Money opcional).

---

## E7 — `supplier_business_type` solo primero

**Versión afectada**: `vendor/sc_code/parser_code.js` línea 67.

**Síntoma**: un supplier "Manufacturer Exporter" emite `supplier_business_type = "Manufacturer"` perdiendo la segunda palabra.

**Causa**: `.first()` sobre `.sr-comInfo-sign .sign-item` toma solo el primer sign-item.

**Fix**: combinar todos los sign-items relevantes.
```js
const business_types = $('.sr-comInfo-sign .sign-item').toArray()
  .map(el => $(el).text_sane())
  .filter(t => /Manufacturer|Trader|Exporter|Importer|Retailer|Wholesaler/.test(t));
const supplier_business_type = business_types.join(' ') || null;
```

---

## E8 — `product` y `supplier` mezclados en un solo collect

**Versión afectada**: `vendor/sc_code/parser_code.js` (todo el return).

**Síntoma**: la spec §2 declara 2 entidades (`product` con 16 campos + `supplier` separada con 7 campos); vendor emite una sola fila con todos los campos mezclados.

**Fix**: emitir 2 `collect()` — uno para product, otro para supplier. El `supplier_id` en product apunta al supplier. Ver patrón multi-entidad de cosme (3 arrays) / olive-young (3 entidades).

---

## E9 — `.search-list .list-node` solo existe en catálogo, no en search

**Versión afectada**: `sc_browser/interaction_code_v1.js` (`wait('.search-list .list-node')`).

**Síntoma**: `Crawler error: waiting for selector ".search-list .list-node" failed: timeout 30000ms exceeded` al correr contra URL de tipo search (`/products-search/hot-china-products/{kw}.html`).

**Causa**: MIC renderiza el listing con **clases distintas según el tipo de URL**:
- `/products-search/hot-china-products/...` → **no** tiene `.list-node`; usa `.prod-item` y `.products-item`.
- `/Chemicals-Catalog/{subcat}.html` → tiene ambos `.prod-item` y `.list-node`.
- `/catalog/item{CAT_ID}/{subcat}-{N}.html` (paginación catálogo) → igual que el catálogo.

Vendor v0 testeó contra 1 sola URL (probablemente catálogo) y dejó el selector acoplado a esa variante.

**Fix (v2)**: multi-selector:
```js
wait('.prod-item, .list-node, .products-item');
```

**Resuelto en v2 — 2026-04-21**.

---

## E10 — `.compnay-name` es placeholder de template Mustache, no clase real

**Versión afectada**: `sc_browser/parser_code_v1.js` línea 21 (`$('.compnay-name[href*="en.made-in-china.com"]').toArray()`).

**Síntoma**: `supplier_urls` siempre llega vacío. El parser loggea `Found 0 unique supplier URLs`.

**Causa**: `compnay-name` (typo `compnay`) aparece en el HTML como parte de un template JS de Mustache: `class="company-name" href="{{=compnayUrl}}"`. Es el template NO renderizado con la clase CORRECTA (`company-name`) y el placeholder `{{=compnayUrl}}` — pero el typo está en el placeholder del valor `href`, no en la clase. Vendor confundió buscando la clase con typo y solo matchea el elemento template (que no tiene href real). La clase productiva de los suppliers reales es `.company-name` (sin typo).

**Fix (v2)**: sin typo:
```js
$('.company-name[href*="en.made-in-china.com"]');
```

**Resuelto en v2 — 2026-04-21**.

---

## E11 — Pagination anchor class varía por tipo de URL

**Versión afectada**: `sc_browser/parser_code_v1.js` línea 41 (`$('.page-num a.next').attr('href')`).

**Síntoma**: `next_page_url = null` en URLs de search aunque exista siguiente página; paginación se queda en página 1.

**Causa**: el anchor "next page" tiene **clases diferentes por tipo de listing**:
- Search (`/products-search/find-china-products/0b0nolimit/{KW}-N.html`): `<a class="main nextpage" href="...">`.
- Catalog (`/catalog/item{CAT_ID}/{SubCat}-N.html`): `<a class="next" href="...">`.

Vendor solo buscó `.next` dentro de `.page-num`.

También: la URL de "siguiente" en search migra al path `/products-search/find-china-products/0b0nolimit/{KW}-{N}.html` — **NO** es `{KW}_{N}.html` como asume la spec §3 punto 1. Confirmar regex de paginación contra realidad observada.

**Fix (v2)**: union selector:
```js
$('a.main.nextpage, .pagination a.next, .page-num a.next').attr('href');
```

**Resuelto en v2 — 2026-04-21**.

> Nota para la spec: §3 del spec de made-in-china dice que la paginación search es `{KW}_N.html`. Observado: el anchor "next" apunta a `/products-search/find-china-products/0b0nolimit/{KW}-{N}.html` (guion, no underscore, y path distinto). **Pendiente validar con el usuario si actualizar la spec o si ambos formatos resuelven**.

---

## E12 — `next_page_url` malformada por doble prefijo en href protocol-relative

**Versión afectada**: `sc_browser/parser_code_v2.js` líneas 37-40 (vigente también en combinación "interaction v3 + parser v2").

**Síntoma**: scraper solo procesa página 1; `rerun_stage` falla silenciosamente al recibir una URL malformada tipo `https://www.made-in-china.comhttps://www.made-in-china.com/products-search/...`. La cadena de paginación se corta en la raíz.

**Causa**: el HTML real observado en `/products-search/hot-china-products/Industrial_Chemicals.html` contiene:
```html
<a href="//www.made-in-china.com/products-search/find-china-products/0b0nolimit/Industrial_Chemicals-2.html" class="main nextpage"
```

El href es **protocol-relative** (arranca con `//`). Traza del bug en v2:

1. `next_link = "//www.made-in-china.com/..."` — no empieza con `http`, entra al `else`.
2. `.replace(/^\/\//, 'https://')` lo convierte a `"https://www.made-in-china.com/..."`.
3. El template literal `` `https://www.made-in-china.com${...}` `` prefija **otra vez** el host → `"https://www.made-in-china.comhttps://www.made-in-china.com/..."`.

El branch `else` mezcla dos operaciones (prepend de host y reemplazo de `//`) que son mutuamente excluyentes según el tipo de href. El `replace` no evita el prepend posterior porque el ternario ya está comprometido con el else.

**Fix (v4)**: helper `absolutize` que ramifica por prefijo sin mezclar operaciones:

```js
function absolutize(href) {
    if (!href) return null;
    if (href.startsWith('http')) return href;
    if (href.startsWith('//')) return `https:${href}`;
    if (href.startsWith('/')) return `https://www.made-in-china.com${href}`;
    return href;
}
const next_page_url = absolutize(next_link);
```

Aplicado también a `product_urls` y `supplier_urls` para consistencia — hoy esos campos usan `href.startsWith('http') ? href : \`https:${href}\``, que asume implícitamente que todo href no-http es protocol-relative. Si alguna vez viniera un href root-relative (`/product/...`), produciría `https:/product/...` malformada. El helper lo cubre.

**Resuelto en v4 — 2026-04-21**.

---

## E13 — `.J-baseInfo-name` clase inexistente → `product_name_clean` siempre null — **Resuelto en v2 — 2026-04-21**

**Versión afectada**: `sc_code/parser_code_v1.js` línea 29 (`$('.sr-proMainInfo-baseInfoH1.J-baseInfo-name span').text_sane()`).

**Síntoma**: `name_clean` (v1) o `product_name_clean` (spec §4) siempre `null` o vacío en el output, sin importar el fixture.

**Causa**: DB AI asumió una clase compuesta `.sr-proMainInfo-baseInfoH1.J-baseInfo-name` que no existe en el HTML real del detail (verificado 2026-04-21 contra fixture `IEFUtrGOCdRZ`: 0 matches de `.J-baseInfo-name`). La clase `.sr-proMainInfo-baseInfoH1` sí existe y contiene el H1 del producto, pero la segunda clase es inventada.

**Fix (v2)**: consumir JSON-LD `Product.name` como fuente primaria (spec §4 declara JSON-LD autoritativo), con fallback a `.sr-proMainInfo-baseInfoH1` pelado:

```js
const product_name_original = product?.name ?? $('.sr-proMainInfo-baseInfoH1').text_sane() ?? null;
```

**Resuelto en v2 — 2026-04-21**.

---

## E14 — `.info-label` / `.info-fields` selectores inexistentes → `supplier_country` null — **Resuelto en v2 — 2026-04-21**

**Versión afectada**: `sc_code/parser_code_v1.js` línea 63 (`$('.info-item:has(.info-label:contains("Address")) .info-fields').text_sane()`).

**Síntoma**: `supplier_country` siempre `null` en output de product detail, aunque el dominio sea `*.en.made-in-china.com` (debería inferirse `CN` al menos).

**Causa**: ni `.info-label` ni `.info-fields` existen en el HTML del product detail (0 matches cada uno, verificado 2026-04-21). El supplier profile solo se renderiza completo en el supplier home (`https://{slug}.en.made-in-china.com/`), no en el detail.

**Fix (v2)**: separar responsabilidades según entidad (spec §6). En la rama product NO se extrae `supplier_country` (no está en los campos §4+§5 de product); solo se emite `supplier_id` (derivado del subdominio de la URL). En la rama supplier home se busca "Address" recorriendo `.info-item` con `text_sane()` y se aplica el mapa `COUNTRY_ISO` con fallback null + flag `country_iso_unknown` (E3):

```js
// solo en rama supplier home:
const addressText = $('.info-item').toArray()
  .map(el => $(el).text_sane())
  .find(t => /address/i.test(t)) ?? null;
const country_name = addressText?.split(/[,:]/).map(s => s.trim()).filter(Boolean).pop() ?? null;
const supplier_country = country_name ? (COUNTRY_ISO[country_name] ?? null) : null;
if (country_name && !supplier_country) flags.push('country_iso_unknown');
```

**Resuelto en v2 — 2026-04-21**.

---

## E15 — `.sa-only-property-price.only-one-priceNum-price span` selector compuesto falla (2da clase inexistente) → MOQ siempre null — **Resuelto en v2 — 2026-04-21**

**Versión afectada**: `sc_code/parser_code_v1.js` línea 43 (`$('.sa-only-property-price.only-one-priceNum-price span').first().text_sane()`).

**Síntoma**: `moq_quantity` y `moq_unit` siempre `null` en el output, aunque el DOM tenga "1 Ton" visible.

**Causa**: la clase `.only-one-priceNum-price` no existe en el DOM (0 matches). La clase correcta que envuelve el MOQ es `.sa-only-property-price` (singular). El selector compuesto del vendor requiere que AMBAS clases estén presentes en el mismo elemento — falla siempre.

**Fix (v2)**: selector simple + regex del spec §7 para parsear cantidad + unidad:

```js
const moq_raw = $('.sa-only-property-price').text_sane() ?? null;
// regex spec §7: (\d+(?:[,.]\d+)?)\s*([A-Za-z]+)
const m = moq_raw?.match(/(\d+(?:[,.]\d+)?)\s*([A-Za-z]+)/);
const moq_quantity = m ? parseFloat(m[1].replace(/,/g, '')) : null;
const moq_unit = m?.[2] ?? null;
```

Contra fixture `IEFUtrGOCdRZ`: `"1 Ton"` → `moq_quantity=1, moq_unit="Ton"`.

**Resuelto en v2 — 2026-04-21**.

---

## E16 — Vendor ignora JSON-LD aunque spec §4 lo declara autoritativo — **Resuelto en v2 — 2026-04-21**

**Versión afectada**: `sc_code/parser_code_v1.js` (el parser entero).

**Síntoma**: todos los campos del product (name, sku, price, brand, rating, additionalProperty → cas_no / grade / formula / einecs / appearance / origin_country, image) se extraen con selectores DOM frágiles en vez de del JSON-LD Product estable. Varios de esos selectores son inexistentes o están hardcoded (E1, E13, E15), lo que produce el output vacío.

**Causa**: DB AI generó el parser contra 1 fixture y sin consumir el JSON-LD. La spec §4 dice explícitamente "Fuente autoritaria: JSON-LD Product embebido en el detail (script type application/ld+json @type Product)". El vendor no itera `script[type="application/ld+json"]` en absoluto.

**Fix (v2)**: reescritura completa del parser con JSON-LD como fuente primaria y DOM como fallback para los campos que no viven en JSON-LD (price range, breadcrumb — porque `BreadcrumbList` viene vacío en el fixture real, verificado 2026-04-21). Ver `parser_code_v2.js`:

```js
const lds = $('script[type="application/ld+json"]').toArray()
  .map(el => { const raw = $(el).html(); if (!raw) return null;
               try { return JSON.parse(raw); } catch { return null; } })
  .filter(Boolean).flat().filter(Boolean);
const product = lds.find(x => x?.['@type'] === 'Product') ?? null;
// additionalProperty → { name → value } map
// product.name, product.sku, product.brand.name, product.offers.priceCurrency,
// product.image, product.aggregateRating.ratingValue directos.
```

Si JSON-LD Product no aparece → flag `jsonld_parse_fallback` (spec §9 catálogo), seguir con DOM-only. NO skip a menos que la URL no sea `/product/`.

**Resuelto en v2 — 2026-04-21**.

---

## E17 — `product_links` / `supplier_links` solo cubren `.prod-item` → 0 URLs en via-2 catalog

**Versión afectada**: `sc_browser/parser_code_v5.js`.

**Síntoma**: parser retorna `product_urls = []` y `supplier_urls = []` al correr contra las 12 seeds via-2 del modo primario v6 (ej. `/Chemicals-Catalog/Alkali.html`, `/Packaging-Printing-Catalog/Stretch-Film.html`). Las tarjetas se renderan con clase `.list-node` o `.products-item`, no `.prod-item`.

**Causa**: el selector de product_links era `$('.prod-item a[href*="en.made-in-china.com/product/"]')` — ancla fija a `.prod-item`. El interaction_code_v5 ya usa multi-selector `wait('.prod-item, .list-node, .products-item')` para el wait, pero el parser no fue actualizado en paralelo.

**Fix (v6)**: ampliar ambos selectores con union de las tres clases de card:

```js
// product_links
const product_links = $('.prod-item a, .list-node a, .products-item a').toArray()
    .filter(el => {
        const href = $(el).attr('href') || '';
        return href.includes('en.made-in-china.com/product/');
    });

// supplier_links
const supplier_links = $('.company-name[href*="en.made-in-china.com"], .prod-item .company-name, .list-node .company-name, .products-item .company-name').toArray()
    .map(el => $(el).attr('href'))
    .filter(href => href && href.includes('en.made-in-china.com') && !href.includes('/product/'));
```

**Resuelto en v6 — 2026-04-24**.

---

## E18 — wait() puede resolver en carrusel ads (.prod-item) antes de que el listing principal cargue — Fix en v6 — 2026-04-24

**Versión afectada**: `sc_browser/interaction_code_v5.js`.

**Síntoma**: el scraper parece "nunca navegar a la subcategoría" — wait resuelve inmediatamente en `.prod-item` del carrusel de anuncios (presente en el SSR desde el principio), pero el listing principal aún no está disponible para el parser. Alternativamente, en páginas via-2 catalog el `wait` podría fallar si el browser no renderiza el carrusel (`.prod-item` es JS-lazy) antes del timeout.

**Causa**: el selector `wait('.prod-item, .list-node, .products-item')` usa `.prod-item` como primer candidato. En el browser (Chromium), `.prod-item` corresponde al carrusel de anuncios cuyo render puede ser asincrónico o diferido. El listing principal usa:
- Via-2 catalog (`/Chemicals-Catalog/{SubCat}.html`): `div.list-node` (dentro de `div.search-list.search-list-wrapper`).
- Via-1 search (`/products-search/...`): `div.products-item`.

El wrapper `div.search-list` está presente en ambas variantes desde el SSR y es el indicador más fiable de que la página de listing cargó.

**Fix (v6)**: wait amplía a 4 selectores con `.search-list` como candidato adicional rápido:
```js
const wait_selector = '.search-list, .list-node, .products-item, .prod-item';
wait(wait_selector);
```
El guard `el_exists` mantiene solo las 3 clases de card para verificar que hay contenido real:
```js
const listing_selector = '.list-node, .products-item, .prod-item';
if (!el_exists(listing_selector)) dead_page('no listing cards found');
```

**Resuelto en v6 — 2026-04-24**.

---

## E19 — Supplier fan-out removido temporalmente (solo productos)

**Versión afectada**: `sc_browser/interaction_code_v5.js`, `sc_browser/parser_code_v6.js`.

**Síntoma** (intencional, no bug): el usuario requiere una versión que scrape SOLO productos sin disparar stages de supplier home. La extracción de supplier_urls agrega requests de supplier home que no son necesarios en la corrida actual.

**Causa**: el interaction v5 emitía `next_stage({url})` para cada `url` en `supplier_urls`. El parser v6 calculaba `supplier_urls` con selector `.company-name`.

**Fix (v6 interaction + v7 parser)**:
- Interaction v6: elimina el bucle `for (let url of supplier_urls) next_stage({url})`.
  El parse() ya no devuelve `supplier_urls` (lo elimina parser v7), por lo que el destructuring también se actualiza.
- Parser v7: elimina el bloque `supplier_links` / `supplier_urls` y no los incluye en el return.

**Resuelto en v6 (interaction) + v7 (parser) — 2026-04-24**.

---

## Patrón de contribución

Cada vez que un run expone un problema nuevo del sitio:

1. Numerar `E{N+1}` en la siguiente sección.
2. **Versión afectada**: qué `_vN.js` produjo el síntoma.
3. **Síntoma**: output observado en el JSON (en `results/`).
4. **Causa**: línea + selector/regla que lo dispara.
5. **Fix**: cambio concreto propuesto o aplicado.
6. Si se resolvió en `v(N+1)`, agregar `**Resuelto en v2 — 2026-04-21**` al título.
