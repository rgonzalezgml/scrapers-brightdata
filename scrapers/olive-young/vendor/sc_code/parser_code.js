// Extract product number from URL
let prdt_no = null;
try {
  const match = input.url.match(/prdtNo=([^&]*)/);
  prdt_no = match ? match[1] : null;
} catch(e) {
  prdt_no = null;
}

// Extract product name
const name_en = $('[data-testid=product-name]').text_sane();

// Extract brand name
const brand_no = $('[data-testid=product-brand-name]').text_sane();

// Extract rating
const rate = +$('.prd-rating-info dt span').text_sane() || null;

// Extract review count - use the data-testid selector from schema
const review_count = +$('[data-testid=product-review-link] span.notranslate').text_sane().replace(/,/g, '') || 0;

// Check if sold out - look for state-stock class on add to cart button
const is_soldout = !!$('[data-testid=product-addtocart-button].state-stock').length;

// Check for badges
const badge_text = $('.prd-bedge span').text_sane();
const best_flag = badge_text === 'BEST';
const new_flag = badge_text === 'NEW';
const early_access_flag = badge_text === 'EARLY ACCESS' || badge_text.includes('Early Access');
const hot_deal_flag = badge_text === 'HOT DEAL' || badge_text.includes('Hot Deal');

// Extract claim tags - look for emblem list if it exists
// Note: This selector may not exist on all products
const claim_tags_elements = $('.list-emblem li').toArray().map(el => $(el).text_sane()).filter(v => v);
const claim_tags = claim_tags_elements.length > 0 ? claim_tags_elements : null;

// Extract category from breadcrumb
const category_ids = $('.location-bar .loc_cat').toArray().map(el => $(el).text_sane()).filter(v => v);

return {
  prdt_no,
  name_en,
  brand_no,
  rate,
  review_count,
  is_soldout,
  best_flag,
  new_flag,
  early_access_flag,
  hot_deal_flag,
  claim_tags,
  category_ids: category_ids.length > 0 ? category_ids : null
};