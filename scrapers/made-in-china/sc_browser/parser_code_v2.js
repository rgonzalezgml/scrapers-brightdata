// v2 — fixes:
//   E9: contenedor listing multi-site (.prod-item funciona en search y catalog)
//   E10: supplier anchor .company-name (sin typo; el `.compnay-name` de v1 era un placeholder Mustache)
//   E11: next-page varía por tipo de URL — search usa `a.main.nextpage`, catalog usa `a.next`

// Extraer URLs de producto desde los cards de listing
const product_links = $('.prod-item a[href*="en.made-in-china.com/product/"]').toArray();

const product_urls = [...new Set(
    product_links
        .map(el => {
            const href = $(el).attr('href');
            if (!href || !href.includes('/product/')) return null;
            return href.startsWith('http') ? href : `https:${href}`;
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
            return href.startsWith('http') ? href : `https:${href}`;
        })
        .filter(Boolean)
)];

console.log(`Found ${supplier_urls.length} unique supplier URLs`);

// Next page — union selector para ambos tipos de listing
const next_link = $('a.main.nextpage, .pagination a.next, .page-num a.next').attr('href');
const next_page_url = next_link
    ? (next_link.startsWith('http') ? next_link : `https://www.made-in-china.com${next_link.replace(/^\/\//, 'https://')}`)
    : null;

// Current page — el span `.page-current` tiene el número activo
const current_page_text = $('.page-current.J-page-current, .page-num strong').text_sane();
const current_page = parseInt(current_page_text, 10) || 1;

return {
    product_urls,
    supplier_urls,
    next_page_url,
    current_page,
};
