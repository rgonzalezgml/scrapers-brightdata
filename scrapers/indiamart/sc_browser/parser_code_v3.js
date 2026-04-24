// parser_code_v2 — IndiaMART Stage 1 MCAT listing (Browser worker).
//
// Cambios vs vendor (`vendor/sc_browser/parser_code.js`):
//   Idéntico en intención: extraer `a[href*="proddetail"]`, absolutizar con
//   `new URL(href, location.href)`, dedupe con Set, devolver
//   `{product_urls: [...]}`.
//
//   Añadido único: filtrar rutas Disallow del robots.txt (spec §3):
//     - `/pd/`
//     - `/proddetail1/`
//     - `/proddetail2/`
//   El selector `a[href*="proddetail"]` matchea también `/proddetail1/` y
//   `/proddetail2/`; esas rutas están Disallow en robots.txt y no deben
//   ser seeds del Stage 2.
//
// Hotfix preview (2026-04-23):
//   `.toArray().map(fn)` rompe en el Browser worker del runtime actual con
//   `TypeError: (intermediate value).toArray is not a function`. El patrón
//   portable cheerio/jQuery es `$(sel).map((_, el) => ...).get()` y
//   funciona tanto en Browser como Code worker. Reemplazo literal, misma
//   semántica, se preservan el filtro Disallow y la dedupe con Set.
//
// Output schema (mismo que vendor, compatible con dashboard actual):
//   { product_urls: string[] }

// Extract all product links from the page.
// El selector a[href*="proddetail"] funciona en IndiaMART MCAT listings.
const product_links = $('a[href*="proddetail"]')
    .map((_, el) => {
        const href = $(el).attr('href');
        if (href && href.includes('proddetail')) {
            // Absolutize (href puede ser relativo).
            const url = new URL(href, location.href);
            // Conservamos querystring (tracking params que BD puede necesitar).
            return url.href;
        }
        return null;
    })
    .get()
    .filter(Boolean)
    // Filtro robots Disallow (spec §3). `/proddetail/` legítimo pasa;
    // `/proddetail1/`, `/proddetail2/`, `/pd/` se descartan.
    .filter(href => !/\/(pd|proddetail[12])\//i.test(href));

// Remove duplicates.
const unique_urls = [...new Set(product_links)];

console.log(`Found ${unique_urls.length} unique product URLs`);

return {
    product_urls: [unique_urls[0]]
};
