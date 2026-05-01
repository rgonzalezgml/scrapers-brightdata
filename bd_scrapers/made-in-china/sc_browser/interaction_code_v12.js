// Input (modo single):
//   search_keyword: "citric acid anhydrous"
//   url: (optional - for Via-2 catalog URLs passed directly)
//   max_pages: -1 (no limit) | N (default 5)
//   current_page: 1 (incremented on each rerun)
//
// Via-1 keyword search URL structure (deterministic, no DOM access needed):
//   Page 1:  /products-search/hot-china-products/{Slug}.html
//   Page N:  /products-search/find-china-products/0b0nolimit/{Slug}-{N}.html
//
// multi-search /multi-search/{slug}/F0/pg-{N}.html (v11): HTTP 200 but
// zero listing cards - abandoned. Via-1 is the correct keyword search path.

const BASE = 'https://www.made-in-china.com';

function kw_to_slug(keyword) {
    // "citric acid anhydrous" -> "Citric_Acid_Anhydrous"
    return keyword.trim().split(/\s+/)
        .map(w => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
        .join('_');
}

const current_page = input.current_page || 1;
const kw   = input.search_keyword;
const slug = kw ? kw_to_slug(kw) : null;

// URL selection:
//   - keyword + page 1: Via-1 hot-china-products
//   - keyword + page N: Via-1 find-china-products/0b0nolimit (passed via input.url from rerun)
//   - no keyword: use input.url directly (Via-2 catalog or explicit seed)
let url;
if (input.url) {
    url = input.url;
} else if (slug) {
    url = `${BASE}/products-search/hot-china-products/${slug}.html`;
} else {
    url = `${BASE}/products-search/hot-china-products/Pharmaceutical_Ingredients.html`;
}

navigate(url);

// Via-1 always loads .prod-item (ads carousel) plus .products-item (main list).
wait('.products-item, .prod-item, .list-node', { timeout: 60000 });

if (!el_exists('.list-node, .products-item, .prod-item'))
    dead_page('no listing cards found');

const { product_urls } = parse();
console.log(`Page ${current_page}: ${product_urls.length} products`);

for (const prod_url of product_urls)
    next_stage({ url: prod_url });

// --- Pagination (keyword / Via-1 only) ---
// For Via-1 keyword search the page N URL is predictable — no DOM href needed.
// Via-2 catalog URL pagination requires the cat_id from the DOM (not supported here).
const unlimited = input.max_pages === -1;
const max_pages  = unlimited ? Infinity : (input.max_pages || 5);
const has_next   = el_exists('a.main.nextpage, .page-num a.next');

if (slug && has_next && (unlimited || current_page < max_pages)) {
    const next_num = current_page + 1;
    const next_url = `${BASE}/products-search/find-china-products/0b0nolimit/${slug}-${next_num}.html`;
    rerun_stage({
        search_keyword: kw,
        url:            next_url,
        max_pages:      input.max_pages,
        current_page:   next_num,
    });
}
