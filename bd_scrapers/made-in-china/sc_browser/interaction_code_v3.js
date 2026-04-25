// v3 — paginación con `max_pages` (spec §9, input schema del collector).
// Cambios vs v2:
//   - Default `max_pages=-1` = sin límite (comportamiento v2).
//   - `max_pages > 0` acota la cadena a N páginas de listing.
//   - `current_page` se propaga en cada rerun_stage (default 1, +1 por página).
//   - La decisión de encolar rerun ya no depende de `is_rerun`, sino de
//     (max_pages, current_page). `is_rerun` se conserva por compat (spec §9).
// Fixes previos que se mantienen vigentes:
//   E9  multi-selector listing (search + catalog).
//   E10 `.company-name` sin typo en parser_code_v2.
//   E11 union pagination selector en parser_code_v2.

navigate(input.url);

const listing_selector = '.prod-item, .list-node, .products-item';
wait(listing_selector);

if (!el_exists(listing_selector))
    dead_page('no listing cards found');

const {product_urls, supplier_urls, next_page_url} = parse();

// `max_pages=0` no es válido — tratar como -1 (sin límite) por spec §9.
const max_pages_raw = (input.max_pages === undefined || input.max_pages === null)
    ? -1
    : Number(input.max_pages);
const max_pages = (max_pages_raw === 0) ? -1 : max_pages_raw;
const current_page = Number(input.current_page) || 1;

console.log(`Page ${current_page}/${max_pages === -1 ? 'all' : max_pages} — ${product_urls.length} products`);

// Paginación: solo encolar rerun si hay next Y (sin límite O aún no alcanzamos el cap).
// R3: un solo rerun_stage por página, desde la raíz de esta invocación.
const can_paginate = next_page_url && (max_pages === -1 || current_page < max_pages);

if (can_paginate)
    rerun_stage({
        url: next_page_url,
        max_pages,
        current_page: current_page + 1,
        is_rerun: true,
    });

for (let url of product_urls)
    next_stage({url});

for (let url of supplier_urls)
    next_stage({url});
