// Navigate to the Beauty-wellness category page
navigate(input.url);

// Wait for the main content to load
const story_items_selector = '.story-item';
const load_more_button_selector = 'button.stories-see-more';

wait(story_items_selector);

// Handle pagination by clicking "Load more" button repeatedly
// The page uses a "Load more" button to dynamically load additional articles
let max_clicks = 10; // Limit to prevent infinite loops
for (let i = 0; i < max_clicks; i++) {
    // Check if the "Load more" button exists and is visible
    if (el_exists(load_more_button_selector, 1000)) {
        scroll_to(load_more_button_selector);
        click(load_more_button_selector);
        // Wait for new content to load
        wait(story_items_selector, {timeout: 10000});
    } else {
        // No more "Load more" button, we've reached the end
        break;
    }
}

// Parse the page to extract article URLs
const {article_urls} = parse();

// Collect each article URL using next_stage
for (let url of article_urls) {
    next_stage({url});
}
