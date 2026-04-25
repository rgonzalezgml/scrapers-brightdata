// v6 — fix multi-selector product_links + supplier_links para tarjetas via-2 catalog (E17).
// Diff vs v5: product_links y supplier_links amplian su selector base de solo .prod-item
// a union .prod-item/.list-node/.products-item, cubriendo las 12 seeds del modo primario v6
// (ej. /Chemicals-Catalog/Alkali.html, /Packaging-Printing-Catalog/Stretch-Film.html).
// Todo lo demás es idéntico a v5: absolutize, current_page, next_page_url, total_pages, return shape.

function absolutize(href) {
    if (!href) return null;
    if (href.startsWith('http')) return href;
    if (href.startsWith('//')) return `https:${href}`;
    if (href.startsWith('/')) return `https://www.made-in-china.com${href}`;
    return href;
}

// Extraer URLs de producto desde los cards de listing (via-1 .prod-item, via-2 .list-node / .products-item)
const product_links = $('.prod-item a, .list-node a, .products-item a').toArray()
    .filter(el => {
        const href = $(el).attr('href') || '';
        return href.includes('en.made-in-china.com/product/');
    });

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

// Extraer URLs de supplier (home del supplier, sin `/product/`) — cubre los tres tipos de card
const supplier_links = $('.company-name[href*="en.made-in-china.com"], .prod-item .company-name, .list-node .company-name, .products-item .company-name').toArray()
    .map(el => $(el).attr('href'))
    .filter(href => href && href.includes('en.made-in-china.com') && !href.includes('/product/'));

const supplier_urls = [...new Set(
    supplier_links
        .map(href => absolutize(href))
        .filter(Boolean)
)];

console.log(`Found ${supplier_urls.length} unique supplier URLs`);

// Next page — union selector para ambos tipos de listing (E11 preservado).
const next_link = $('a.main.nextpage, .pagination a.next, .page-num a.next').attr('href');
const next_page_url = absolutize(next_link);

// Current page — el span `.page-current` tiene el número activo
const current_page_text = $('.page-current.J-page-current, .page-num strong').text_sane();
const current_page = parseInt(current_page_text, 10) || 1;

// Total pages — span `.page-total` del widget de paginación MIC.
// Si no existe (listing single-page), fallback a 1.
const total_pages_text = $('.page-total').first().text_sane();
const total_pages = parseInt(total_pages_text, 10) || 1;

console.log(`Pagination: page ${current_page}/${total_pages}`);

return {
    product_urls,
    supplier_urls,
    next_page_url,
    current_page,
    total_pages,
};
