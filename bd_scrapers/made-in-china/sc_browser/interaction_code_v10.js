// Input (modo array):
//   search_keywords: ["Citric Acid Anhydrous", "Glycerin USP", ...]  — fan-out: rerun por keyword
//
// Input (modo single con keyword):
//   search_keyword: "citric acid anhydrous"
//   max_pages: -1  (sin limite) | N (default 5)
//
// Input (modo URL original):
//   url: "https://www.made-in-china.com/Chemicals-Catalog/Alkali.html"
//
// Input vacio -> fan-out por keywords por defecto

const BASE = 'https://www.made-in-china.com';

const DEFAULT_KEYWORDS = [
    'pharmaceutical ingredients',
    'pharmaceutical packaging',
];

function search_url(keyword, page) {
    const slug = keyword.trim().toLowerCase().replace(/\s+/g, '-');
    return `${BASE}/multi-search/${encodeURIComponent(slug)}/F0/pg-${page}.html`;
}

// --- Fan-out: array de keywords -> rerun por cada uno, sin navegar ---
if (Array.isArray(input.search_keywords) && input.search_keywords.length > 0) {
    for (const kw of input.search_keywords) {
        rerun_stage({
            url:            search_url(kw, 1),
            search_keyword: kw,
            max_pages:      -1,
        });
    }

// --- Sin input -> fan-out por keywords por defecto ---
} else if (!input.url && !input.search_keyword) {
    for (const kw of DEFAULT_KEYWORDS) {
        rerun_stage({
            url:            search_url(kw, 1),
            search_keyword: kw,
            max_pages:      -1,
        });
    }

// --- Modo single: search_keyword o URL directa ---
} else {
    let url = input.url;
    if (!url && input.search_keyword) {
        url = search_url(input.search_keyword, input.current_page || 1);
    }

    navigate(url);

    const wait_selector = '.search-list, .list-node, .products-item, .prod-item';
    wait(wait_selector, { timeout: 60000 });

    if (!el_exists('.list-node, .products-item, .prod-item'))
        dead_page('no listing cards found');

    const { product_urls } = parse();

    console.log(`Emitting ${product_urls.length} products`);

    for (const prod_url of product_urls)
        next_stage({ url: prod_url });

    // --- Paginacion ---
    const unlimited    = input.max_pages === -1;
    const max_pages    = unlimited ? Infinity : (input.max_pages || 5);
    const current_page = input.current_page || 1;
    const has_next     = el_exists('.paginator-next:not(.disabled), .next-page:not(.disabled), a[rel="next"]');

    if (has_next && (unlimited || current_page < max_pages)) {
        rerun_stage({
            search_keyword: input.search_keyword,
            url:            input.search_keyword ? search_url(input.search_keyword, current_page + 1) : null,
            max_pages:      input.max_pages,
            current_page:   current_page + 1,
        });
    }
}
