// v5 — parser acompaña el switch a paginación PARALELA (spec §9).
// Diff vs v4:
//   - Nuevo campo de salida `total_pages` extraído del widget de paginación
//     MIC real: `<span class="page-current J-page-current">1</span>/<span class="page-total">10</span>`.
//     Selector `.page-total` → parseInt; fallback a 1 si el span no existe
//     (listing de una sola página o listing sin widget).
//   - Sin cambios en product_urls, supplier_urls, next_page_url, current_page.
//     El interaction v5 consume `total_pages` + `next_page_url` para construir
//     las URLs de páginas 2..cap en paralelo (fan-out desde página 1).
// Fixes previos que se mantienen vigentes:
//   E9  multi-selector listing (el selector vive en interaction_code_v5).
//   E10 `.company-name` sin typo (se preserva literal).
//   E11 union pagination selector `a.main.nextpage, .pagination a.next, .page-num a.next`.
//   E12 helper `absolutize` para href protocol-relative / root-relative.

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
