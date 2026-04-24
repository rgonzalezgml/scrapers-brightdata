// Extract all product links from the page
// The selector a[href*="proddetail"] works on IndiaMART pages
const product_links = $('a[href*="proddetail"]').toArray()
    .map(el => {
        const href = $(el).attr('href');
        if (href && href.includes('proddetail')) {
            // Parse the URL to clean it
            try {
                const url = new URL(href, location.href);
                // Keep the full URL with query parameters as they may be important for tracking
                return url.href;
            } catch (e) {
                console.log('Invalid URL:', href);
                return null;
            }
        }
        return null;
    })
    .filter(Boolean);

// Remove duplicates
const unique_urls = [...new Set(product_links)];

console.log(`Found ${unique_urls.length} unique product URLs`);

return {
    product_urls: unique_urls
};
