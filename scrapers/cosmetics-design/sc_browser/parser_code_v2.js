// Extract all article URLs from the page
const base_url = 'https://www.nutraingredients.com';

// Find all article links
const article_links = $('.story-item-text-headline-link').toArray().map(el => {
    const href = $(el).attr('href');
    if (href) {
        // Convert relative URLs to absolute URLs
        return new URL(href, base_url).href;
    }
    return null;
}).filter(Boolean); // Remove null values

// Remove duplicates
const unique_urls = [...new Set(article_links)];

console.log(`Extracted ${unique_urls.length} unique article URLs`);

return {
    article_urls: unique_urls
};
