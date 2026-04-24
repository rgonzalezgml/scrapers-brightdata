// v8 — igual que v7 pero usa .toArray() en lugar de .map().get() (más seguro en browser runtime).

function absolutize(href) {
    if (!href) return null;
    if (href.startsWith('http')) return href;
    if (href.startsWith('//')) return `https:${href}`;
    if (href.startsWith('/')) return `https://www.made-in-china.com${href}`;
    return href;
}

const product_urls = [...new Set(
    $('.prod-item a, .list-node a, .products-item a').toArray()
        .map(el => $(el).attr('href') || '')
        .filter(href => href.includes('en.made-in-china.com/product/'))
        .map(href => absolutize(href))
)];

console.log(`Found ${product_urls.length} unique product URLs`);

return { product_urls };
