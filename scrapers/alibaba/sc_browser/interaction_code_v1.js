// Input
// url: https://www.alibaba.com/trade/search?SearchText=industrial+chemicals&has4Tab=true
// search_keyword: "industrial chemicals"  // optional search keyword to override default
// min_order_quantity: 100  // optional minimum order quantity filter (applies to product URLs)
// supplier_country: "China"  // optional supplier country filter (applies to product URLs)
// min_price: 0  // optional minimum price filter in USD (applies to product URLs)
// max_price: 5000  // optional maximum price filter in USD (applies to product URLs)
// max_pages: 500  // optional maximum number of pages to scrape (default is 5, max is 10)



// Navigate to the URL
const base_url = 'https://www.alibaba.com';
let url = new URL(input.url || `${base_url}/trade/search?SearchText=industrial+chemicals&has4Tab=true`);

// Apply filters from input if provided
if (input.search_keyword) {
    url.searchParams.set('SearchText', input.search_keyword);
}

// Navigate to the search page
navigate(url.href);

// Wait for product cards to load
const product_card_selector = 'div.fy23-search-card.J-search-card-wrapper';
wait(product_card_selector, { timeout: 60000 });

// Check for blocking or errors
if (el_exists('[action="/errors/validateCaptcha"]')) {
    blocked('Captcha detected on page');
}

// Scroll to load all products on the page
scroll_to('bottom');
wait(product_card_selector);

// Parse the current page to get product URLs
let page_data = parse();

// Handle pagination - check if we're on the first run
if (!input.is_rerun) {
    // Get the maximum number of pages to scrape (default to 5, max 10)
    const max_pages = Math.min(input.max_pages || 5, 10);

    // Get current page number from URL
    const current_page = parseInt(url.searchParams.get('page')) || 1;

    // Check if next page button exists and is enabled
    const has_next_page = el_exists('button.pagination-item.next:not([disabled])');

    // Trigger rerun for subsequent pages
    if (has_next_page && current_page < max_pages) {
        for (let page = 2; page <= max_pages; page++) {
            const next_url = new URL(url.href);
            next_url.searchParams.set('page', page.toString());

            rerun_stage({
                url: next_url.href,
                search_keyword: input.search_keyword,
                min_order_quantity: input.min_order_quantity,
                supplier_country: input.supplier_country,
                min_price: input.min_price,
                max_price: input.max_price,
                max_pages: input.max_pages,
                is_rerun: true
            });
        }
    }
}

// Collect product URLs using next_stage
for (let product_url of page_data.product_urls) {
    next_stage({ url: product_url });
}