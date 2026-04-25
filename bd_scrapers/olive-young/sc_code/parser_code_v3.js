// parser_code_v3.js — sc_code (Code worker)
// v3 corrige v2 con campos reales verificados contra la API live (2026-04-24):
// - array en json.data["pages.ranking.products"] (key con puntos)
// - prdt_no desde p.id (no prdtNo/productNo)
// - product_name_kr desde p.original_name (no originalName/nameKr)
// - brand_name_kr desde p.kor_brand_name (no brandNameKr)
// - thumbnail desde p.thumbnail_img_url (no thumbnail/prdtImgUrl)
// - rank no viene en el response → usar posición i+1
// Agrega original_price y sale_price (disponibles en el response).

// ── Helpers ──────────────────────────────────────────────────────────────────

function isoToday() {
  return new Date().toISOString().slice(0, 10);
}

function safeFloat(val, min, max) {
  const n = parseFloat(val);
  if (isNaN(n)) return null;
  if (n < min || n > max) return null;
  return n;
}

function cleanNameEn(raw) {
  if (!raw) return null;
  let s = raw.replace(/\s+/g, ' ').trim();
  s = s.replace(/\[[^\]]*\]/g, '').trim();
  s = s.replace(/\((OY-Exclusive|Refill Set|\+\d+ea|\+Pouch Keyring|\d{4})\)/gi, '').trim();
  s = s.split(/[|\/]/)[0].trim();
  if (s.length > 100) s = s.slice(0, 100).trim();
  return s || null;
}

function cleanNameKr(raw) {
  if (!raw) return null;
  let s = raw.replace(/\s+/g, ' ').trim();
  s = s.replace(/[(\s]*(기획|증정|한정|단독|리필|더블|트리플|파우치|키링|콜라보)[)\s]*/g, ' ').trim();
  s = s.replace(/\(\d{4}\)/g, '').trim();
  s = s.replace(/^[ㅣ|｜]\s*/, '').trim();
  if (s.length > 100) s = s.slice(0, 100).trim();
  return s || null;
}

function thumbnailFull(raw) {
  if (!raw) return null;
  if (/prdtImg\/\d+/.test(raw)) {
    return 'https://cdn-image.oliveyoung.com/' + raw.replace(/^\//, '');
  }
  return null;
}

// ── Parse URL params for region and category_id ───────────────────────────────
const url_str = (input && input.url) ? input.url : '';
const regionMatch = url_str.match(/[?&]region=([^&]+)/);
const catMatch = url_str.match(/[?&]category-id=([^&]+)/);
const region_code = regionMatch ? decodeURIComponent(regionMatch[1]) : 'UNKNOWN';
const category_id = catMatch ? decodeURIComponent(catMatch[1]) : 'UNKNOWN';
const scraped_date = isoToday();

// ── Extract JSON from body ────────────────────────────────────────────────────
// text_sane() puede lanzar en Code worker con respuestas JSON puras (no HTML)
// porque accede a .length sobre un elemento undefined internamente.
// Usar .text() estándar de jQuery con try-catch.
let raw_text = '';
try {
  raw_text = ($('body').text() || $('pre').text() || '').trim();
} catch (e) {
  raw_text = '';
}

if (!raw_text) {
  return [{
    entity: 'ranking',
    site_code: 'oliveyoung-global',
    region_code,
    category_id,
    scraped_date,
    scraper_flags: ['api_parse_error'],
  }];
}

let json;
try {
  json = JSON.parse(raw_text);
} catch (e) {
  return [{
    entity: 'ranking',
    site_code: 'oliveyoung-global',
    region_code,
    category_id,
    scraped_date,
    scraper_flags: ['api_parse_error'],
  }];
}

// Handle API-level 400 errors: {"timestamp":..,"status":400,"error":"Bad Request"}
if (json && json.status && json.status >= 400) {
  return [{
    entity: 'ranking',
    site_code: 'oliveyoung-global',
    region_code,
    category_id,
    scraped_date,
    scraper_flags: ['api_400'],
  }];
}

// ── Locate product array ──────────────────────────────────────────────────────
// Real shape: {"status":"success","data":{"pages.ranking.products":[...]}}
// Key contains literal dots — must use bracket notation.
let products = null;
if (json.data && Array.isArray(json.data['pages.ranking.products'])) {
  products = json.data['pages.ranking.products'];
} else if (Array.isArray(json.data)) {
  products = json.data;
} else if (Array.isArray(json)) {
  products = json;
}

if (!products || products.length === 0) {
  return [{
    entity: 'ranking',
    site_code: 'oliveyoung-global',
    region_code,
    category_id,
    scraped_date,
    scraper_flags: ['api_parse_error'],
  }];
}

// ── Build ranking rows ────────────────────────────────────────────────────────
const PRDT_NO_RE = /^GA\d{8,12}$/;

const rows = [];
for (let i = 0; i < products.length; i++) {
  const p = products[i];
  if (!p) continue;

  // prdt_no from p.id (live API) with fallback to legacy field names
  const prdt_no = (p.id || p.prdtNo || p.prdt_no || p.productNo || '') + '';
  if (!PRDT_NO_RE.test(prdt_no)) continue;

  // rank not in API response — use position
  const rank = typeof p.rank === 'number' ? p.rank : (i + 1);
  const ranking_id = 'oliveyoung-global_' + region_code + '_' + category_id + '_' + rank + '_' + scraped_date;
  const product_url = 'https://global.oliveyoung.com/product/detail?prdtNo=' + prdt_no;

  // Field names from live API (2026-04-24)
  const name_raw_en = p.name || p.nameEn || null;
  const name_raw_kr = p.original_name || p.originalName || p.nameKr || null;
  const brand_name_en = p.brand_name || p.brandName || p.brandNameEn || null;
  const brand_name_kr = p.kor_brand_name || p.brandNameKr || null;
  const brand_no = (p.brand_no || p.brandNo || '') + '' || null;

  const rate_raw = p.rate !== undefined ? p.rate : (p.rating !== undefined ? p.rating : null);
  const rate_flags = [];
  let rate = safeFloat(rate_raw, 0, 5);
  if (rate_raw !== null && rate_raw !== undefined && rate === null) {
    rate_flags.push('rating_invalid');
  }

  const thumbnail_raw = p.thumbnail_img_url || p.thumbnail || p.prdtImgUrl || null;
  const thumbnail_full = thumbnailFull(thumbnail_raw);

  const name_clean_en = cleanNameEn(name_raw_en);
  if (name_raw_en && !name_clean_en) rate_flags.push('name_clean_fallback');

  rows.push({
    entity: 'ranking',
    ranking_id,
    site_code: 'oliveyoung-global',
    region_code,
    category_id,
    category_name: null,
    rank,
    prdt_no,
    product_url,
    product_name_en: name_raw_en || null,
    product_name_kr: name_raw_kr || null,
    product_name_clean_en: name_clean_en,
    product_name_clean_kr: cleanNameKr(name_raw_kr),
    brand_name_en: brand_name_en || null,
    brand_name_kr: brand_name_kr || null,
    brand_no: brand_no || null,
    rate,
    original_price: typeof p.original_price === 'number' ? p.original_price : null,
    sale_price: typeof p.sale_price === 'number' ? p.sale_price : null,
    is_soldout: !!(p.is_soldout || p.isSoldOut || p.soldOut),
    has_coupon: !!(p.has_coupon || p.hasCoupon),
    has_gift: !!(p.has_gift || p.hasGift),
    promotion_name: (p.promotion_name || p.promotionName) || null,
    thumbnail_img_url_raw: thumbnail_raw || null,
    thumbnail_img_url_full: thumbnail_full,
    scraped_date,
    scraper_flags: rate_flags,
  });
}

// Return array — interaction iterates and calls collect(row) per item
return rows;
