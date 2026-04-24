// Extract product cards
const product_cards = $('div.fy23-search-card.J-search-card-wrapper').toArray();

const product_urls = [];

for (let card of product_cards) {
    const $card = $(card);
    
    // Extract product URL from the main product link
    const product_link = $card.find('a[href*="/product-detail/"]').first().attr('href');
    
    if (product_link) {
        // Convert relative URL to absolute URL
        const absolute_url = new URL(product_link, 'https://www.alibaba.com').href;
        
        // Apply filters if specified in input
        let should_include = true;
        
        // Filter by minimum order quantity if specified
        if (input.min_order_quantity) {
            const moq_text = $card.find('.search-card-m-sale-features__item').text();
            const moq_match = moq_text.match(/Min\.\s*order:\s*([\d,]+)/i);
            if (moq_match) {
                const moq = parseFloat(moq_match[1].replace(/,/g, ''));
                if (moq < input.min_order_quantity) {
                    should_include = false;
                }
            }
        }
        
        // Filter by price range if specified
        if (input.min_price || input.max_price) {
            const price_text = $card.find('[class*="search-card-e-price"]').text();
            const price_match = price_text.match(/([\d,]+(?:\.\d+)?)/);
            if (price_match) {
                const price = parseFloat(price_match[1].replace(/,/g, ''));
                if (input.min_price && price < input.min_price) {
                    should_include = false;
                }
                if (input.max_price && price > input.max_price) {
                    should_include = false;
                }
            }
        }
        
        // Filter by supplier country if specified
        if (input.supplier_country) {
            const country_code = $card.find('.search-card-e-country-flag__wrapper img').attr('src');
            if (country_code) {
                const country_match = country_code.match(/\/([a-z]{2})\.png$/i);
                if (country_match) {
                    const card_country = country_match[1].toUpperCase();
                    if (card_country !== input.supplier_country.toUpperCase()) {
                        should_include = false;
                    }
                }
            }
        }
        
        if (should_include) {
            product_urls.push(absolute_url);
        }
    }
}

console.log(`Found ${product_urls.length} product URLs on this page`);

return {
    product_urls: product_urls
};