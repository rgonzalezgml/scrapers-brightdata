// parser_code_v2 — IndiaMART Stage 2 product detail (Code worker).
//
// Cambios vs vendor (`vendor/sc_code/parser_code.js`):
//   1. Fix del selector de supplier_url/supplier_id. El vendor usa
//      `$('a[href*="lighthouse-india"]')`, string que ya NO aparece en el
//      HTML actual de IndiaMART (verificado 2026-04-23 con curl a
//      /proddetail/caustic-soda-flakes-22408594448.html). Con el selector
//      vendor, supplier_url y supplier_id se emiten siempre null y rompen
//      el join a la entidad `supplier` (spec §6).
//
//      El nuevo selector busca el `<a>` que envuelve a `h2.fs15` (nombre
//      del supplier en el header de la ficha), que según el DOM real
//      apunta a `https://www.indiamart.com/{slug}/?pid=...`. Se absolutiza
//      y normaliza a la forma canónica `https://www.indiamart.com/{slug}/`
//      (sin querystring) según spec §3 ("Supplier home"). supplier_id se
//      deriva del slug del path por regex `/^\/([a-z0-9-]+)\/?$/i` según
//      spec §6 ("supplier_id derivado del slug del href del seller").
//
//      Nota fixture 22408594448: el slug real del DOM es `vatsinternational`
//      (un token, sin guión). La spec §11 ejemplifica `vats-international`,
//      inconsistente con §6. §6 es la regla autoritaria: se usa el slug
//      tal como lo da el href. Reportado para refinamiento de spec.
//
//   El refactor a extracción-por-JSON-LD que recomienda la spec §4
//   ("Fuente autoritaria: JSON-LD") queda para la Fase 2 del scraper. Este
//   v2 se enfoca en los guards (en interaction_code_v2.js) y este fix
//   puntual de selector.
//
// Output schema (mismo que vendor, 20 fields, compatible con dashboard):
//   product_id, url, name_clean, type, category_path,
//   price_min_usd, price_unit, price_currency,
//   supplier_id, supplier_name, supplier_city, supplier_url,
//   supplier_state, supplier_country, business_type, member_since_year,
//   verified, trustseal, supplier_rating, supplier_gst.

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

// Extract supplier information.
// supplier_url: href del <a> que envuelve al <h2 class="fs15"> con el
// nombre del supplier. En el DOM actual el href trae querystring
// (?pid=...&cui=1); normalizamos al canónico `https://www.indiamart.com/{slug}/`
// según spec §3. Fallback: href del logo del supplier (a > img.c_logo).
const supplier_name = $('h2.fs15').text_sane();
const supplier_href_raw = $('h2.fs15').closest('a').attr('href')
  || $('a:has(img.c_logo)').attr('href')
  || null;
const supplier_slug = supplier_href_raw
  ?.match(/^https?:\/\/www\.indiamart\.com\/([a-z0-9-]+)\/?(?:\?|$)/i)?.[1]
  || null;
const supplier_url = supplier_slug
  ? `https://www.indiamart.com/${supplier_slug}/`
  : null;
const supplier_id = supplier_slug;
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
