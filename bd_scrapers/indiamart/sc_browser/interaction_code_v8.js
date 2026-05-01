// Input (modo array):
//   search_keywords: ["Citric Acid Anhydrous", "Glycerin USP", ...]  — fan-out: rerun por keyword
//
// Input (modo single con keyword):
//   search_keyword: "citric acid anhydrous"
//   max_pages: -1  (sin limite) | N (default 5)
//
// Input (modo URL original):
//   url: "https://dir.indiamart.com/impcat/citric-acid.html"
//   kind: "mcat" | "hub"  +  category_slug: "citric-acid"
//
// Input vacio -> fan-out por keywords por defecto

const BASE_SEARCH  = 'https://dir.indiamart.com/search.mp';
const MCAT_URL_TMPL = 'https://dir.indiamart.com/impcat/{slug}.html';
const HUB_URL_TMPL  = 'https://dir.indiamart.com/indianexporters/ind_{slug}.html';

const DEFAULT_KEYWORDS = [
    'pharmaceutical ingredients',
    'pharmaceutical packaging',
];

function search_url(keyword, page) {
    const ss = encodeURIComponent(keyword.trim());
    const url = `${BASE_SEARCH}?ss=${ss}&prdsrc=1`;
    return page > 1 ? `${url}&page=${page}` : url;
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
} else if (!input.url && !input.search_keyword && !input.category_slug) {
    for (const kw of DEFAULT_KEYWORDS) {
        rerun_stage({
            url:            search_url(kw, 1),
            search_keyword: kw,
            max_pages:      -1,
        });
    }

// --- Modo single: search_keyword, URL directa o category_slug ---
} else {
    let url = input.url;
    if (!url && input.search_keyword) {
        url = search_url(input.search_keyword, input.current_page || 1);
    } else if (!url) {
        const kind = input.kind || 'mcat';
        url = kind === 'hub'
            ? HUB_URL_TMPL.replace('{slug}', input.category_slug)
            : MCAT_URL_TMPL.replace('{slug}', input.category_slug);
    }

    country('in');
    navigate(url);

    const wait_selector = '.list-container, .prd-unit, .lst-unit, [class*="product-list"]';
    wait(wait_selector, { timeout: 60000 });

    if (!el_exists('.prd-unit, .lst-unit, [class*="product-list"] li'))
        dead_page('no product listings found');

    const data = parse();
    console.log(`Emitting ${data.product_urls.length} products`);

    for (const prod_url of data.product_urls)
        next_stage({ url: prod_url });

    // --- Paginacion ---
    const unlimited    = input.max_pages === -1;
    const max_pages    = unlimited ? Infinity : (input.max_pages || 5);
    const current_page = input.current_page || 1;
    const has_next     = el_exists('.next-btn:not(.disabled), a[rel="next"], .pagination .next:not(.disabled)');

    if (input.search_keyword && has_next && (unlimited || current_page < max_pages)) {
        rerun_stage({
            search_keyword: input.search_keyword,
            url:            search_url(input.search_keyword, current_page + 1),
            max_pages:      input.max_pages,
            current_page:   current_page + 1,
        });
    }
}
