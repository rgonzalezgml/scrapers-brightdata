// Helper function to extract price range
const extractPriceRange = (priceText) => {
  if (!priceText) return { min: null, max: null };
  const match = priceText.match(/US\$\s*([\d.,]+)(?:-([\d.,]+))?/);
  if (!match) return { min: null, max: null };
  const min = parseFloat(match[1].replace(/,/g, ''));
  const max = match[2] ? parseFloat(match[2].replace(/,/g, '')) : min;
  return { min, max };
};

// Helper function to extract MOQ
const extractMOQ = (moqText) => {
  if (!moqText) return { quantity: null, unit: null };
  const match = moqText.match(/([\d,]+)\s*([a-zA-Z]+)/);
  if (!match) return { quantity: null, unit: null };
  return {
    quantity: parseInt(match[1].replace(/,/g, '')),
    unit: match[2]
  };
};

// Extract product ID from URL or hidden field
const product_id = input.url.match(/product\/([^\/]+)\//)?.[1] || $('.J-data-pid').val() || null;

// Extract URL
const url = new URL(input.url);

// Extract product name
const name_clean = $('.sr-proMainInfo-baseInfoH1.J-baseInfo-name span').text_sane();

// Extract type/classification
const type = $('.bsc-item:has(.bac-item-label:contains("Classification")) .bac-item-value').text_sane();

// Extract category from breadcrumb
const category_mic = $('.sr-QPWords-cont a[href*="Oxide"]').last().text_sane() || 
                     $('a[href*="/Chemicals-Catalog/Oxide.html"]').text_sane();

// Extract price information
const priceText = $('.only-one-priceNum-td-left').text_sane();
const priceRange = extractPriceRange(priceText);

// Extract MOQ information
const moqText = $('.sa-only-property-price.only-one-priceNum-price span').first().text_sane();
const moqData = extractMOQ(moqText);

// Extract CAS number
const cas_no = $('tr:has(th:contains("CAS No.")) td').text_sane() || 
               $('th.th-label:contains("CAS No.") + td').text_sane();

// Extract grade
const grade = $('.bsc-item:has(.bac-item-label:contains("Grade Standard")) .bac-item-value').text_sane();

// Extract appearance from specification table
const appearance = $('.rich-text-table tr:has(td:contains("Appearance")) td').last().text_sane();

// Extract supplier information
const supplier_url_text = $('.sr-linkTo-comInfo .sr-comInfo-title a').attr('href');
const supplier_id = supplier_url_text ? supplier_url_text.match(/\/\/([^.]+)\./)?.[1] : null;
const supplier_url = supplier_url_text ? new URL(supplier_url_text) : null;
const supplier_name = $('.sr-linkTo-comInfo .sr-comInfo-title .text-ellipsis').text_sane();

// Extract supplier country from address
const addressText = $('.info-item:has(.info-label:contains("Address")) .info-fields').text_sane();
const supplier_country = addressText ? addressText.split(',').pop().trim() : null;

// Extract supplier business type
const supplier_business_type = $('.sr-comInfo-sign .sign-item').first().text_sane();

// Extract member level
const supplier_member_level = $('.sign-item:contains("Diamond Member")').text_sane().split('Since')[0].trim() || null;

// Check if supplier is audited
const supplier_audited = $('.sign-item:has(img[src*="as-short.png"])').length > 0;

return {
  product_id,
  url,
  name_clean,
  type,
  category_mic,
  price_min_usd: priceRange.min ? new Money(priceRange.min, 'USD') : null,
  price_max_usd: priceRange.max ? new Money(priceRange.max, 'USD') : null,
  price_unit: moqData.unit,
  price_currency: 'USD',
  moq_quantity: moqData.quantity,
  moq_unit: moqData.unit,
  cas_no,
  grade,
  appearance,
  supplier_id,
  supplier_url,
  supplier_name,
  supplier_country,
  supplier_business_type,
  supplier_member_level,
  supplier_audited
};
