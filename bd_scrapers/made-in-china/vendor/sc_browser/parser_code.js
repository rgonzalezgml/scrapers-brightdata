// Extract product URLs from the listing page
const product_links = $('.product-name a[href*="en.made-in-china.com/product/"]').toArray();

const product_urls = product_links
    .map(el => {
        const href = $(el).attr('href');
        if (href && href.includes('/product/')) {
            // Convert relative URLs to absolute URLs
            return href.startsWith('http') ? href : `https:${href}`;
        }
        return null;
    })
    .filter(Boolean);

// Remove duplicates
const unique_product_urls = [...new Set(product_urls)];

console.log(`Found ${unique_product_urls.length} unique product URLs`);

// Extract supplier URLs from the listing page
const supplier_links = $('.compnay-name[href*="en.made-in-china.com"]').toArray();

const supplier_urls = supplier_links
    .map(el => {
        const href = $(el).attr('href');
        if (href) {
            // Convert relative URLs to absolute URLs
            return href.startsWith('http') ? href : `https:${href}`;
        }
        return null;
    })
    .filter(Boolean);

// Remove duplicates
const unique_supplier_urls = [...new Set(supplier_urls)];

console.log(`Found ${unique_supplier_urls.length} unique supplier URLs`);

// Extract next page URL for pagination
let next_page_url = null;
const next_link = $('.page-num a.next').attr('href');
if (next_link) {
    next_page_url = next_link.startsWith('http') ? next_link : `https://www.made-in-china.com${next_link}`;
}

// Extract current page number
let current_page = 1;
const current_page_elem = $('.page-num strong').text();
if (current_page_elem) {
    current_page = parseInt(current_page_elem) || 1;
}

return {
    product_urls: unique_product_urls,
    supplier_urls: unique_supplier_urls,
    next_page_url: next_page_url,
    current_page: current_page
};