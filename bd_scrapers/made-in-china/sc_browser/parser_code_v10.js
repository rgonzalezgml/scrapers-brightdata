// v10 — replaces .toArray() with .each() (more compatible across BrightData
// runtime versions) and extracts next_page_url so the Code Worker interaction
// code does not need document access.

function absolutize(href) {
    if (!href) return null;
    if (href.startsWith('http')) return href;
    if (href.startsWith('//')) return `https:${href}`;
    if (href.startsWith('/')) return `https://www.made-in-china.com${href}`;
    return href;
}

const seen = new Set();
const product_urls = [];
$('.prod-item a, .list-node a, .products-item a').each(function() {
    const href = $(this).attr('href') || '';
    if (href.includes('en.made-in-china.com/product/') && !seen.has(href)) {
        seen.add(href);
        product_urls.push(absolutize(href));
    }
});

// .attr('href') on a collection returns the first matched element's attribute,
// equivalent to .first().attr('href') but without requiring .first().
// Via-1 next: a.main.nextpage  |  Via-2 next: .page-num a.next
const raw_next = $('a.main.nextpage, .page-num a.next').attr('href') || null;
const next_page_url = raw_next ? absolutize(raw_next) : null;

console.log(`Found ${product_urls.length} unique product URLs, next: ${next_page_url}`);

return { product_urls, next_page_url };
