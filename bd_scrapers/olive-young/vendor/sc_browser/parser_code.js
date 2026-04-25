// Determine which tab is active based on the region
const region = input.region || 'usa';
const product_list_id = region.toLowerCase() === 'korea' ? '#koreaBestProduct' : '#orderBestProduct';

// Extract product URLs from the active tab
// HTML: <a href="/product/detail?prdtNo=GA240824996">
const product_links = $(`${product_list_id} li a[href*='/product/detail']`).toArray();

// Use a Set to ensure unique URLs
const unique_urls = new Set();
let len = 0;
product_links.forEach(link => {
    const href = $(link).attr('href');
    if (href && len <= 5) {
        // Convert relative URLs to absolute URLs
        const full_url = new URL(href, location.href).href;
        unique_urls.add(full_url);
        len++
    }
});

// Convert Set to Array
const product_urls = Array.from(unique_urls);

console.log(`Found ${product_urls.length} unique product URLs for region: ${region}`);

return { product_urls };
