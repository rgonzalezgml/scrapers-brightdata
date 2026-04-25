// v7 — elimina extracción de supplier_links / supplier_urls (E19).
// Diff vs v6:
//   - supplier_links y supplier_urls eliminados completamente.
//   - El return ya no incluye supplier_urls (no lo necesita interaction_code_v6).
//   - Todo lo demás es idéntico a v6: absolutize, product_urls con union selector,
//     next_page_url, current_page, total_pages, return shape.
//
// Fixes previos que se mantienen vigentes:
//   E10 .company-name sin typo.
//   E11 union pagination selector.
//   E12 absolutize para href protocol-relative / root-relative.
//   E17 product_links union .prod-item/.list-node/.products-item.

function absolutize(href) {
    if (!href) return null;
    if (href.startsWith('http')) return href;
    if (href.startsWith('//')) return `https:${href}`;
    if (href.startsWith('/')) return `https://www.made-in-china.com${href}`;
    return href;
}

// Extraer URLs de producto desde los cards de listing.
// Via-2 catalog: div.list-node > div.list-node-content > a.img-wrap (href absoluto https://)
// Via-1 search:  div.products-item > a.img-wrap (href absoluto https://)
// Carrusel ads:  a.prod-item.J-focus-faw (href protocol-relative //)
// El filtro href.includes('/product/') discrimina product links de supplier homes y otros anchors.
const product_links = $('.prod-item a, .list-node a, .products-item a').map((_, el) => {
    const href = $(el).attr('href') || '';
    return href.includes('en.made-in-china.com/product/') ? href : null;
}).get().filter(Boolean);

const product_urls = [...new Set(
    product_links
        .map(href => {
            if (!href.includes('/product/')) return null;
            return absolutize(href);
        })
        .filter(Boolean)
)];

console.log(`Found ${product_urls.length} unique product URLs`);

// Next page — union selector para ambos tipos de listing (E11 preservado).
// Via-1 search:  a.main.nextpage (clase compuesta "main nextpage")
// Via-2 catalog: .page-num a.next (clase simple "next" dentro de div.page-num)
const next_link = $('a.main.nextpage, .page-num a.next').attr('href');
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
    next_page_url,
    current_page,
    total_pages,
};
