// Input (modo single):
//   search_keyword: "citric acid anhydrous"
//   url: "https://www.made-in-china.com/..."  (opcional, backward compat)
//   max_pages: -1  (sin limite) | N (default 5)

const BASE = 'https://www.made-in-china.com';

function search_url(keyword, page) {
    const slug = keyword.trim().toLowerCase().replace(/\s+/g, '-');
    return `${BASE}/multi-search/${encodeURIComponent(slug)}/F0/pg-${page}.html`;
}

const page = input.current_page || 1;
let url = input.url || (input.search_keyword
    ? search_url(input.search_keyword, page)
    : search_url('pharmaceutical ingredients', page));

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
