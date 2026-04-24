// parser_code_v2.js — sc_code (Code worker)
// Cambio vs v1 (parser_code_v1 era un parser de product detail Vue, erróneo aquí).
// v2 parsea la respuesta JSON del Rankings API. Extrae region y category_id de
// la URL del request (input.url) para construir ranking_id determinístico.
// Arregla: spec §4 (entidad ranking completa), spec §7 (normalización), E5 (skip
// prdt_no que no matchea ^GA\d{8,12}$), E3 (flags api_400, api_parse_error).

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
  // strip marketing suffixes in brackets
  s = s.replace(/\[[^\]]*\]/g, '').trim();
  // strip suffixes in parens that match marketing patterns
  s = s.replace(/\((OY-Exclusive|Refill Set|\+\d+ea|\+Pouch Keyring|\d{4})\)/gi, '').trim();
  // cut at first pipe or slash
  s = s.split(/[|\/]/)[0].trim();
  // max 100 chars
  if (s.length > 100) s = s.slice(0, 100).trim();
  return s || null;
}

function cleanNameKr(raw) {
  if (!raw) return null;
  let s = raw.replace(/\s+/g, ' ').trim();
  // remove trailing marketing tokens in parens or standalone
  s = s.replace(/[(\s]*(기획|증정|한정|단독|리필|더블|트리플|파우치|키링|콜라보)[)\s]*/g, ' ').trim();
  // remove date codes like (2604) (2505)
  s = s.replace(/\(\d{4}\)/g, '').trim();
  // leading fullwidth separator
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
const raw_text = ($('body').text_sane() || $('pre').text_sane() || '').trim();

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

// Handle API-level 400 errors
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
// Try common shapes: json.data (array), json.data.products, json.products,
// or json itself as array.
let products = null;
if (Array.isArray(json)) {
  products = json;
} else if (Array.isArray(json.data)) {
  products = json.data;
} else if (json.data && Array.isArray(json.data.products)) {
  products = json.data.products;
} else if (Array.isArray(json.products)) {
  products = json.products;
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

  // prdt_no validation (spec §8 E5)
  const prdt_no = (p.prdtNo || p.prdt_no || p.productNo || '') + '';
  if (!PRDT_NO_RE.test(prdt_no)) continue; // skip without emitting

  const rank = typeof p.rank === 'number' ? p.rank : (i + 1);
  const ranking_id = 'oliveyoung-global_' + region_code + '_' + category_id + '_' + rank + '_' + scraped_date;
  const product_url = 'https://global.oliveyoung.com/product/detail?prdtNo=' + prdt_no;

  const name_raw_en = p.name || p.nameEn || p.productName || null;
  const name_raw_kr = p.originalName || p.nameKr || p.productNameKr || null;
  const brand_name_en = p.brandNameEn || p.brandName || null;
  const brand_name_kr = p.brandNameKr || null;
  const brand_no = (p.brandNo || '') + '' || null;

  const rate_raw = p.rate !== undefined ? p.rate : (p.rating !== undefined ? p.rating : null);
  const rate_flags = [];
  let rate = safeFloat(rate_raw, 0, 5);
  if (rate_raw !== null && rate_raw !== undefined && rate === null) {
    rate_flags.push('rating_invalid');
  }

  const thumbnail_raw = p.thumbnail || p.prdtImgUrl || p.thumbnailUrl || null;
  const thumbnail_full = thumbnailFull(thumbnail_raw);

  const name_clean_en = cleanNameEn(name_raw_en);
  if (name_raw_en && !name_clean_en) rate_flags.push('name_clean_fallback');

  rows.push({
    entity: 'ranking',
    ranking_id,
    site_code: 'oliveyoung-global',
    region_code,
    category_id,
    // category_name comes from the /categories endpoint; not available here
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
    is_soldout: !!(p.isSoldOut || p.soldOut || p.is_soldout),
    has_coupon: !!(p.hasCoupon || p.has_coupon),
    has_gift: !!(p.hasGift || p.has_gift),
    promotion_name: p.promotionName || p.promotion_name || null,
    thumbnail_img_url_raw: thumbnail_raw || null,
    thumbnail_img_url_full: thumbnail_full,
    scraped_date,
    scraper_flags: rate_flags,
  });
}

// Return array — interaction iterates and calls collect(row) per item
return rows;
