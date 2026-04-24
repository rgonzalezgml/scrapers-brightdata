// Extract all category links from the directory page
// The page contains category links like /indore/t-shirts.html, /indore/mens-jeans.html, etc.
const category_links = $('a[href*="/indore/"]').toArray()
    .map(el => {
        const href = $(el).attr('href');
        if (href && href.includes('/indore/') && href.endsWith('.html')) {
            try {
                const url = new URL(href, location.href);
                return url.href;
            } catch (e) {
                return null;
            }
        }
        return null;
    })
    .filter(Boolean);

// Remove duplicates
const unique_urls = [...new Set(category_links)];

console.log(`Found ${unique_urls.length} unique category URLs`);

return {
    product_urls: unique_urls
};