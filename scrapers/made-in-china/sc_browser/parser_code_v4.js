// v4 — fix E12: next_page_url malformada por doble prefijo de host.
// Diff vs v2:
//   - Nuevo helper `absolutize(href)` que ramifica por prefijo
//     ('http' → as-is | '//' → `https:` | '/' → host + href | otro → as-is).
//   - `next_page_url` usa absolutize (cierra E12: el href del anchor `a.main.nextpage`
//     viene protocol-relative `//www.made-in-china.com/...` y v2 lo componía a
//     `https://www.made-in-china.comhttps://www.made-in-china.com/...`).
//   - `product_urls` y `supplier_urls` también pasan por absolutize para
//     consistencia y para cubrir un hipotético href root-relative (`/product/...`).
// Fixes previos que se mantienen vigentes:
//   E9  multi-selector listing (el selector vive en interaction_code_v3).
//   E10 `.company-name` sin typo (se preserva literal).
//   E11 union pagination selector `a.main.nextpage, .pagination a.next, .page-num a.next`.
// Interaction vigente: `sc_browser/interaction_code_v3.js` (lógica `max_pages` sin cambios).

function absolutize(href) {
    if (!href) return null;
    if (href.startsWith('http')) return href;
    if (href.startsWith('//')) return `https:${href}`;
    if (href.startsWith('/')) return `https://www.made-in-china.com${href}`;
    return href;
}

// Extraer URLs de producto desde los cards de listing
const product_links = $('.prod-item a[href*="en.made-in-china.com/product/"]').toArray();

const product_urls = [...new Set(
    product_links
        .map(el => {
            const href = $(el).attr('href');
            if (!href || !href.includes('/product/')) return null;
            return absolutize(href);
        })
        .filter(Boolean)
)];

console.log(`Found ${product_urls.length} unique product URLs`);

// Extraer URLs de supplier (home del supplier, sin `/product/`)
const supplier_links = $('.company-name[href*="en.made-in-china.com"]').toArray();

const supplier_urls = [...new Set(
    supplier_links
        .map(el => {
            const href = $(el).attr('href');
            if (!href) return null;
            return absolutize(href);
        })
        .filter(Boolean)
)];

console.log(`Found ${supplier_urls.length} unique supplier URLs`);

// Next page — union selector para ambos tipos de listing (E11 preservado).
const next_link = $('a.main.nextpage, .pagination a.next, .page-num a.next').attr('href');
const next_page_url = absolutize(next_link);

// Current page — el span `.page-current` tiene el número activo
const current_page_text = $('.page-current.J-page-current, .page-num strong').text_sane();
const current_page = parseInt(current_page_text, 10) || 1;

return {
    product_urls,
    supplier_urls,
    next_page_url,
    current_page,
};
