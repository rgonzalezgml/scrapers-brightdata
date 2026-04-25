// cosmetics-design — sc_browser/parser_code_v1.js
// Bootstrap desde vendor + cierre de gaps:
// - Filtro cross-promo: descartar URLs cuyo pathname comienza con
//   /Product-innovations/ o /Events/ (spec §3 databrightdata + §3 genomma lab).
// - Dedupe con Set preservado.
// - Log de conteo descartado para diagnostico.

// Extract all article URLs from the story items on the page
const base_url = 'https://www.nutraingredients.com';

// Get all article links from story items
const raw_urls = $('.story-item-text-headline-link')
    .toArray()
    .map(el => {
        const href = $(el).attr('href');
        if (href) {
            // Convert relative URLs to absolute URLs
            return new URL(href, base_url).href;
        }
        return null;
    })
    .filter(Boolean); // Remove null values

// Filter out cross-promo paths (spec §3: "Ignorar /Product-innovations/, /Events/")
const is_cross_promo = (u) => {
    const path = (new URL(u, base_url)).pathname;
    return path.indexOf('/Product-innovations/') === 0 || path.indexOf('/Events/') === 0;
};

const filtered_urls = raw_urls.filter(u => !is_cross_promo(u));
const dropped_count = raw_urls.length - filtered_urls.length;

// Remove duplicates
const unique_urls = [...new Set(filtered_urls)];

console.log(`Found ${unique_urls.length} unique article URLs (dropped ${dropped_count} cross-promo: /Product-innovations/ or /Events/)`);

return {
    article_urls: unique_urls
};
