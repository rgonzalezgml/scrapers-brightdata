// v2 — fix E9: selector robusto que funciona en search y catalog.
// v1 usaba `.search-list .list-node` — `.list-node` solo existe en catálogo, no en search.

navigate(input.url);

// Multi-selector: `.prod-item` existe en ambos; `.list-node` solo en catálogo;
// `.products-item` aparece en search. Fallback a `dead_page` si nada matchea (R1).
const listing_selector = '.prod-item, .list-node, .products-item';
wait(listing_selector);

if (!el_exists(listing_selector))
    dead_page('no listing cards found');

const {product_urls, supplier_urls, next_page_url, current_page} = parse();

console.log(`Found ${product_urls.length} products on page ${current_page}`);

// Paginación — rerun una vez por cada página desde la raíz (R3: paralelo, no secuencial).
// `is_rerun` marca que no vuelva a disparar reruns.
if (!input.is_rerun && next_page_url)
    rerun_stage({url: next_page_url, is_rerun: true});

for (let url of product_urls)
    next_stage({url});

for (let url of supplier_urls)
    next_stage({url});
