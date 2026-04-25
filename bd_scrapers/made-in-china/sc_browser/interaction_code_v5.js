// v5 — paginación PARALELA (fan-out desde página 1) reemplaza la cadena
// secuencial de v3. Patrón: alibaba/vendor/sc_browser/interaction_code.js (R3).
//
// Diff vs v3 (interaction) + v4 (parser):
//   - Parser v5 devuelve `total_pages` (span.page-total del widget MIC).
//   - En página 1 (`!input.is_rerun`), el interaction encola en paralelo
//     las URLs de páginas 2..cap con `rerun_stage({..., is_rerun: true})`.
//     Cap: `max_pages === -1 ? total_pages : Math.min(max_pages, total_pages)`.
//   - En rerun (`input.is_rerun === true`), solo se extraen product_urls /
//     supplier_urls y se emite `next_stage`. NO se encolan más reruns
//     (evita explosión exponencial).
//   - Helper `buildPageUrl(baseNextUrl, targetPage)`: sustitución numérica
//     del `-{N}.html` final del pathname del `next_page_url` canónico.
//     Cubre via-1 search (`find-china-products/0b0nolimit/{KW}-{N}.html`)
//     y via-2 catalog paginado (`/catalog/item{CAT_ID}/{SubCat}-{N}.html`).
//   - `max_pages=0` → normalizado a `-1` (spec §9: 0 es inválido).
//   - `current_page` ya NO se propaga (todas las páginas 2..cap se conocen
//     desde página 1; las reruns no necesitan saberlo).
//
// Fixes previos que se mantienen vigentes:
//   E9  multi-selector listing (search + catalog): `.prod-item, .list-node, .products-item`.
//   E10 `.company-name` sin typo (parser v5).
//   E11 union pagination selector (parser v5).
//   E12 absolutize para href protocol-relative / root-relative (parser v5).
//
// Reglas duras preservadas:
//   R3  un solo fan-out de rerun_stage desde la raíz (no cadena secuencial).
//   R5  timeout default (no subir).
//   R8  navigate solo top-level.
//   R9  parse() sin args.

// Helper: construye la URL de `targetPage` a partir del `next_page_url`
// canónico (página 2) sustituyendo `-{N}.html` al final del pathname.
// Ej:
//   buildPageUrl('https://www.made-in-china.com/products-search/find-china-products/0b0nolimit/Industrial_Chemicals-2.html', 5)
//     → '.../Industrial_Chemicals-5.html'
//   buildPageUrl('https://www.made-in-china.com/catalog/item999i132/Alkali-2.html', 5)
//     → '.../Alkali-5.html'
// Si el pathname no matchea `-{N}.html` al final (URL fuera del patrón
// conocido), devuelve null y el caller omite ese target.
function buildPageUrl(baseNextUrl, targetPage) {
    if (!baseNextUrl || !targetPage) return null;
    const m = baseNextUrl.match(/^(.*-)(\d+)(\.html(?:[?#].*)?)$/);
    if (!m) return null;
    return `${m[1]}${targetPage}${m[3]}`;
}

navigate(input.url);

const listing_selector = '.prod-item, .list-node, .products-item';
wait(listing_selector);

if (!el_exists(listing_selector))
    dead_page('no listing cards found');

const {product_urls, supplier_urls, next_page_url, total_pages} = parse();

// Normalizar max_pages: undefined/null → -1; 0 → -1 (spec §9).
const max_pages_raw = (input.max_pages === undefined || input.max_pages === null)
    ? -1
    : Number(input.max_pages);
const max_pages = (max_pages_raw === 0) ? -1 : max_pages_raw;

const is_rerun = input.is_rerun === true;

console.log(`Page ${is_rerun ? 'N (rerun)' : '1 (root)'} — ${product_urls.length} products, ${supplier_urls.length} suppliers, total_pages=${total_pages}, max_pages=${max_pages === -1 ? 'all' : max_pages}`);

// Fan-out paralelo: solo desde página 1 (raíz), nunca desde reruns.
if (!is_rerun) {
    const cap = max_pages === -1 ? total_pages : Math.min(max_pages, total_pages);

    // Si total_pages===1 o no hay next_page_url, no hay nada que paginar.
    if (cap >= 2 && next_page_url) {
        for (let page = 2; page <= cap; page++) {
            const page_url = buildPageUrl(next_page_url, page);
            if (!page_url) continue;
            rerun_stage({
                url: page_url,
                is_rerun: true,
                max_pages,
            });
        }
    }
}

// En ambas ramas (página 1 y rerun), emitir los detail/supplier de esta página.
for (let url of product_urls)
    next_stage({url});

for (let url of supplier_urls)
    next_stage({url});
