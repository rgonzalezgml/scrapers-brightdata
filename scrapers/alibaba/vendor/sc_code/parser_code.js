// Helper function to extract numeric value from price string
const extractPrice = (priceStr) => {
  if (!priceStr) return null;
  // Remove currency symbols and extract numeric value
  const match = priceStr.replace(/[^\d.,]/g, '').replace(/,/g, '');
  return match ? parseFloat(match) : null;
};

// Extract cleaned product name from title
const cleaned_product_name = $('.product-title-container h1').text_sane();

// Extract product URL from canonical link
const product_url = new URL($('link[rel="canonical"]').attr('href') || input.url);

// Extract supplier name
const supplier_name = $('[data-testid="seller-overview-card-company-link"]').text_sane() 
  || $('a[href*="en.alibaba.com"]').first().text_sane();

// Extract price information from the price tiers
const priceItems = $('.price-item').toArray();
let price_raw = null;
let price_min_usd = null;
let price_max_usd = null;
let price_unit = null;
let minimum_order_quantity = null;

if (priceItems.length > 0) {
  // First price tier (highest price, lowest quantity)
  const firstPriceText = $(priceItems[0]).find('.id-text-2xl span').text_sane();
  price_raw = firstPriceText;
  price_max_usd = extractPrice(firstPriceText);
  
  // Last price tier (lowest price, highest quantity)
  const lastPriceText = $(priceItems[priceItems.length - 1]).find('.id-text-2xl span').text_sane();
  price_min_usd = extractPrice(lastPriceText);
  
  // Extract unit from first price tier quantity range
  const quantityText = $(priceItems[0]).find('.id-text-sm').text_sane();
  minimum_order_quantity = quantityText;
  
  // Extract unit (e.g., "kilograms" from "1 - 24 kilograms")
  const unitMatch = quantityText.match(/\d+\s*-?\s*\d*\s*(\w+)/);
  price_unit = unitMatch ? unitMatch[1] : null;
}

// Extract CAS number from attributes
const cas_number = $('[data-testid="module-attribute-row"]:has([data-testid="module-attribute-name-text"]:contains("CAS No.")) [data-testid="module-attribute-value-text"]').text_sane()
  || $('[data-testid="module-attribute-row"]:has([data-testid="module-attribute-name-text"]:contains("CAS number")) [data-testid="module-attribute-value-text"]').text_sane();

// Extract purity from attributes
const purity = $('[data-testid="module-attribute-row"]:has([data-testid="module-attribute-name-text"]:contains("Purity")) [data-testid="module-attribute-value-text"]').text_sane();

return {
  cleaned_product_name,
  product_url,
  supplier_name,
  price_raw,
  price_min_usd,
  price_max_usd,
  price_unit,
  minimum_order_quantity,
  cas_number,
  purity
};
