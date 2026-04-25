// Input
// url: https://www.nutraingredients.com/Health-conditions/Beauty-wellness/



// Navigate to the URL
navigate(input.url);

// Wait for articles to load
const article_selector = 'article.story-item';
const load_more_button = 'button.stories-see-more';

wait(article_selector);

// Handle pagination by clicking "Load more" button until it's no longer available
// Using a for loop with a reasonable max_clicks limit to prevent infinite loops
const max_clicks = 50; // Adjust based on expected number of pages

for (let i = 0; i < max_clicks; i++) {
    // Check if the "Load more" button exists and is not disabled
    if (el_exists(load_more_button, 1000)) {
        // Scroll to the button to ensure it's visible
        scroll_to(load_more_button);

        // Click the button
        click(load_more_button);

        // Wait for new articles to load
        wait(article_selector, { timeout: 10000 });
    } else {
        // No more "Load more" button, we've reached the end
        console.log(`Clicked "Load more" ${i} times. No more content to load.`);
        break;
    }
}

// Parse the page to extract article URLs
const { article_urls } = parse();

console.log(`Found ${article_urls.length} article URLs`);

// Collect each article URL using next_stage
for (let url of article_urls) {
    next_stage({ url });
}
