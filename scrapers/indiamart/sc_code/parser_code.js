// Extract product ID from URL
const product_id = input.url.match(/(\d+)\.html$/)?.[1] || null;

// Extract product name
const name_clean = $('h1.center-heading').text_sane();

// Extract product type (Bulb Type)
const type = $('table tbody tr:has(td:contains("Bulb Type")) td.tdwdt1').text_sane();

// Extract price information
const price_text = $('.price-unit').text_sane();
const price_inr = +price_text.replace(/[^\d.]/g, '') || null;
const price_unit = $('.units').text_sane();
const price_currency = price_text.match(/[₹$€£¥]/)?.[0] || null;

// Create price in original currency (INR)
const price_min_usd = price_inr && price_currency ? new Money(price_inr, price_currency) : null;

// Extract supplier information
const supplier_name = $('h2.fs15').text_sane();
const supplier_url = $('a[href*="lighthouse-india"]').attr('href');
const supplier_id = supplier_url?.match(/\/([^\/]+)\//)?.[1] || null;
const supplier_city = $('.addrs.plhn').text_sane();

// Extract state and country from the location text
const location_text = $('.verT.fs13').text_sane();
const location_parts = location_text?.split(',').map(s => s.trim()) || [];
const supplier_state = location_parts[1] || null;
const supplier_country = location_parts[2] || null;

// Extract GST number
const supplier_gst = $('.company-details-grid div:has(dt:contains("GST")) dd').text_sane() 
  || $('span.color1').filter(function() { return $(this).text().match(/\d{2}\*+\d+[A-Z]+/); }).text_sane();

// Extract business type
const business_type = $('.company-details-grid div:has(dt:contains("Nature of Business")) dd').text_sane();

// Extract member since year
const member_since_year = $('.company-details-grid div:has(dt:contains("IndiaMART Member Since")) dd').text_sane();

// Extract verification status
const verified = $('.slic').length > 0;
const trustseal = $('.slic .color1 span').toArray().map(el => $(el).text_sane()).join(' ').trim() || null;

// Extract supplier rating
const supplier_rating = +$('#slr_rtng .bo.color').text_sane() || null;

// Extract category path from breadcrumb or product context
let category_path = null;
try {
  const scriptContent = $('script[type="application/ld+json"]').html();
  if (scriptContent) {
    const jsonData = JSON.parse(scriptContent);
    if (jsonData['@type'] === 'BreadcrumbList' && jsonData.itemListElement) {
      category_path = jsonData.itemListElement[jsonData.itemListElement.length - 1]?.item?.name || null;
    }
  }
} catch (e) {
  // If parsing fails, leave as null
}

// Try to extract category from related categories section
if (!category_path) {
  const relatedCategory = $('#fndrltd h3').first().text_sane();
  if (relatedCategory) {
    category_path = relatedCategory;
  }
}

// Try to extract from page title or meta tags
if (!category_path) {
  const pageTitle = $('title').text_sane();
  const categoryMatch = pageTitle.match(/(.+?)\s*-\s*/);
  if (categoryMatch) {
    category_path = categoryMatch[1];
  }
}

return {
  product_id,
  url: new URL(input.url),
  name_clean,
  type,
  category_path,
  price_min_usd,
  price_unit,
  price_currency,
  supplier_id,
  supplier_name,
  supplier_city,
  supplier_url: supplier_url ? new URL(supplier_url) : null,
  supplier_state,
  supplier_country,
  business_type,
  member_since_year,
  verified,
  trustseal,
  supplier_rating,
  supplier_gst
};
