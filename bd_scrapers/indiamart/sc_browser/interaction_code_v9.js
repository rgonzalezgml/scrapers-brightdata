// Input (modo single):
//   search_keyword: "citric acid anhydrous"
//   url: "https://dir.indiamart.com/..."  (opcional, backward compat)
//   max_pages: -1  (sin limite) | N (default 5)

const BASE_SEARCH = 'https://dir.indiamart.com/search.mp';

function search_url(keyword, page) {
    const ss = encodeURIComponent(keyword.trim());
    const url = `${BASE_SEARCH}?ss=${ss}&prdsrc=1`;
    return page > 1 ? `${url}&page=${page}` : url;
}

const page = input.current_page || 1;
let url = input.url || (input.search_keyword
    ? search_url(input.search_keyword, page)
    : search_url('pharmaceutical ingredients', page));

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
