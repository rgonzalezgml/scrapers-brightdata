// Helper function to extract text safely
const getText = (selector) => $(selector).text_sane() || null;

// Helper function to calculate word count
const getWordCount = (text) => {
  if (!text) return null;
  return text.trim().split(/\s+/).filter(Boolean).length;
};

// Extract article ID from URL slug
const currentUrl = input.url;
const urlMatch = currentUrl.match(/\/Article\/\d{4}\/\d{2}\/\d{2}\/(.*?)(\/|$)/);
const articleId = urlMatch ? urlMatch[1] : null;

// Extract headline
const headline = getText('.headline-block-header');

// Extract subheadline - try both selectors
const subheadline = getText('.subheadline-block') || getText('.subheadline-block-skinny');

// Extract display date
const displayDateEl = $('.date-block time').first();
const displayDateText = displayDateEl.text_sane();
let displayDate = null;
if (displayDateText) {
  // Parse date like "15-Apr-2026"
  displayDate = new Date(displayDateText).toISOString();
}

// Extract topic tags from related topics
const topicTags = $('.related-topics-item').toArray().map(el => $(el).text_sane()).filter(Boolean);

// Extract body text from article paragraphs
let bodyText = null;
const articleParagraphs = $('article p.c-paragraph.b-article-body-skinny').toArray()
  .map(el => $(el).text_sane())
  .filter(Boolean);

if (articleParagraphs.length > 0) {
  bodyText = articleParagraphs.join('\n\n');
}

// Determine if body text fell back to HTML extraction or is truncated
const bodyFallbackHtml = !bodyText || bodyText.includes('...(trunc)');

// Calculate word count
const wordCount = getWordCount(bodyText);

// Check if date is in future
let dateFuture = false;
if (displayDate) {
  const articleDate = new Date(displayDate);
  const now = new Date();
  dateFuture = articleDate > now;
}

// Extract URL
const url = new URL(input.url);

// Check for paywall indicators
const paywalled = $('.paywall, [class*="paywall"], [class*="subscription-required"]').length > 0;

// Extract sections from related topics links
const sectionLinks = $('.related-topics-item').toArray().map(el => {
  const href = $(el).attr('href');
  return href;
}).filter(Boolean);

// Parse sections from URLs
const sections = sectionLinks.map(href => {
  const match = href.match(/\/(News|Health-conditions|Ingredients)\/(.*?)\//);
  if (match) {
    return match[2].replace(/-/g, ' ');
  }
  return null;
}).filter(Boolean);

// Primary section is the first one
const primarySection = sections.length > 0 ? sections[0] : null;

// Look for region tags in links
const regionLinks = $('a[href*="/Region"]').toArray().map(el => {
  const href = $(el).attr('href');
  const match = href.match(/\/Regions?\/(.*?)(\/|$)/);
  if (match) {
    return match[1].replace(/-/g, ' ');
  }
  return null;
}).filter(Boolean);

const regionTags = [...new Set(regionLinks)]; // Remove duplicates

// Check if region tags are missing
const regionMissing = regionTags.length === 0;

// Check if Fusion parsing failed - no script tags means no Fusion data
const fusionParseFallback = $('script').length === 0;

// Consent wall retry flag - check if interstitial was present
const consentWallRetried = $('.interstitial-container-popup').length > 0;

// Try to extract author from page text
const bodyTextAll = $('body').text();
const authorMatch = bodyTextAll.match(/By ([A-Z][a-z]+(?: [A-Z][a-z]+)+)/);
const authors = authorMatch ? [authorMatch[1]] : [];

return {
  article_id: articleId,
  url: url,
  headline: headline,
  subheadline: subheadline,
  description_basic: subheadline,
  authors: authors,
  body_text: bodyText,
  word_count: wordCount,
  display_date: displayDate,
  primary_section: primarySection,
  sections: sections,
  region_tags: regionTags,
  topic_tags: topicTags,
  paywalled: paywalled,
  date_future: dateFuture,
  region_missing: regionMissing,
  body_fallback_html: bodyFallbackHtml,
  fusion_parse_fallback: fusionParseFallback,
  consent_wall_retried: consentWallRetried
};