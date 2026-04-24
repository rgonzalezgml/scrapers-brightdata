// Navigate to the input URL
navigate(input.url);

// Wait for product listings to load - the correct selector is .search-list .list-node
const product_list_selector = '.search-list .list-node';
wait(product_list_selector);

// Extract product URLs and supplier URLs from the current page
const {product_urls, supplier_urls, next_page_url, current_page} = parse();

console.log(`Found ${product_urls.length} products on page ${current_page}`);

// Handle pagination - check if there's a next page
if (!input.is_rerun && next_page_url) {
    // Rerun this stage with the next page URL
    rerun_stage({url: next_page_url, is_rerun: true});
}

// Collect each product URL using next_stage
for (let url of product_urls) {
    next_stage({url});
}

// Collect each supplier URL using next_stage
for (let url of supplier_urls) {
    next_stage({url});
}