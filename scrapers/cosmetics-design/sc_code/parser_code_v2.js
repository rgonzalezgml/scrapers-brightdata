// Helper function to parse dates
const parseDate = (dateStr) => {
    if (!dateStr) return null;
    try {
        return new Date(dateStr).toISOString();
    } catch {
        return null;
    }
};

// Extract article title
let article_title = $('.headline-block-header').text_sane();

// Extract publication date
let publication_date = parseDate($('.date-block time:first-of-type').text_sane());

// Extract last updated date
let last_updated_date = parseDate($('.date-block time:last-of-type').text_sane());

// Extract article summary
let article_summary = $('.subheadline-block').text_sane();

// Extract article content
let article_content = $('article#pn_rw').text_sane();

// Extract lead image URL
let lead_image_url = $('.lead-art-image-view-thumb img').attr('src')
    || $('.lead-art-image-view-thumb img').attr('data-src')
    || $('.lead-art-image-view-thumb source').first().attr('srcset')?.split('?')[0];

if (lead_image_url) {
    lead_image_url = new Image(lead_image_url);
}

// Extract image caption
let image_caption = $('.lead-art-image-view-caption').text_sane();

// Extract article URL from canonical link
let article_url = $('link[rel="canonical"]').attr('href');
if (article_url) {
    article_url = new URL(article_url);
} else {
    article_url = new URL(input.url);
}

// Extract related topics
let related_topics = $('.related-topics-item').toArray().map(item => $(item).text_sane());

// Determine if paywalled - check for paywall indicators
let paywalled = false;
if ($('.paywall-message').length > 0 ||
    $('.subscription-required').length > 0 ||
    $('[class*="paywall"]').length > 0 ||
    $('body').text().includes('Subscribe to continue reading')) {
    paywalled = true;
}

return {
    article_title,
    publication_date,
    last_updated_date,
    article_summary,
    article_content,
    lead_image_url,
    image_caption,
    article_url,
    related_topics,
    paywalled
};
