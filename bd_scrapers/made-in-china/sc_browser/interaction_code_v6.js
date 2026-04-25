// v6 — dos fixes sobre v5:
//   E18  listing_selector actualizado con selectores reales del DOM (dom_map.md 2026-04-24):
//        - Via-2 catalog (/Chemicals-Catalog/{SubCat}.html): lista principal en div.list-node
//          dentro de div.search-list.search-list-wrapper; NO usa .products-item.
//        - Via-1 search (/products-search/...): lista principal en div.products-item; NO usa .list-node.
//        - Ambas: tienen a.prod-item.J-focus-faw (carrusel ads top), pero esos elementos
//          pueden estar ocultos o cargarse tarde en el browser. El selector más fiable para
//          indicar que el listing SSR cargó es .search-list (presente en ambos tipos).
//        Fix: wait amplía a union de 4 selectores incluyendo .search-list como fallback rápido;
//        listing_selector para el guard el_exists mantiene los 3 selectores de card.
//   E19  bloque supplier fan-out eliminado completamente (solo productos, sin suppliers).
//        Parser v7 ya no calcula supplier_urls. El interaction no emite next_stage para ellos.
//
// Fixes previos que se mantienen vigentes:
//   E9  multi-selector listing (search + catalog).
//   E10 .company-name sin typo (parser v5).
//   E11 union pagination selector (parser v5).
//   E12 absolutize para href protocol-relative / root-relative (parser v5).
//   E17 product_links union .prod-item/.list-node/.products-item (parser v6).
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

// E18: listing_selector ampliado.
//   .search-list       — wrapper del listing SSR presente en AMBAS variantes (via-1 y via-2).
//   .list-node         — card individual de via-2 catalog.
//   .products-item     — card individual de via-1 search.
//   .prod-item         — carrusel ads, presente en ambas; menos fiable en browser (carga JS).
// El wait resuelve en cuanto cualquiera de los cuatro aparece en el DOM.
const wait_selector = '.search-list, .list-node, .products-item, .prod-item';
wait(wait_selector);

// Guard: verificar que al menos un tipo de card existe (no solo el wrapper .search-list vacío).
const listing_selector = '.list-node, .products-item, .prod-item';
if (!el_exists(listing_selector))
    dead_page('no listing cards found');

const {product_urls, next_page_url, total_pages} = parse();

// Normalizar max_pages: undefined/null → -1; 0 → -1 (spec §9).
const max_pages_raw = (input.max_pages === undefined || input.max_pages === null)
    ? -1
    : Number(input.max_pages);
const max_pages = (max_pages_raw === 0) ? -1 : max_pages_raw;

const is_rerun = input.is_rerun === true;

console.log(`Page ${is_rerun ? 'N (rerun)' : '1 (root)'} — ${product_urls.length} products, total_pages=${total_pages}, max_pages=${max_pages === -1 ? 'all' : max_pages}`);

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

// En ambas ramas (página 1 y rerun), emitir los detail de esta página.
// E19: bloque supplier fan-out eliminado completamente.
for (let url of product_urls)
    next_stage({url});
