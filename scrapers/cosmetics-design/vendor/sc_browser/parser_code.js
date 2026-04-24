// Extract all article URLs from the story items on the page
const base_url = 'https://www.nutraingredients.com';

// Get all article links from story items
const article_urls = $('.story-item-text-headline-link')
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

// Remove duplicates
const unique_urls = [...new Set(article_urls)];

console.log(`Found ${unique_urls.length} unique article URLs`);

return {
    article_urls: unique_urls
};
