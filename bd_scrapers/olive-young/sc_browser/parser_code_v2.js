// parser_code_v2.js — sc_browser (Browser worker)
// Cambio vs v1: es Stage 2 (enriquecimiento product detail). v1 era el mismo
// parser de product detail pero sin entity, sin scraper_flags, y usaba
// .toArray() que rompe en Browser worker (R12). v2 usa .map((_, el) => ...).get()
// portable, añade entity='product', review_count con reemplazo de comas correcto,
// flags completos y scraped_date.
// Spec §5: campos de enriquecimiento (review_count, *_flag, claim_tags,
// category_ids) más campos core heredados.

// ── prdt_no desde query param ─────────────────────────────────────────────────
const prdt_no_match = (input.url || '').match(/[?&]prdtNo=([^&]+)/);
const prdt_no = prdt_no_match ? prdt_no_match[1] : null;

// ── Core fields ───────────────────────────────────────────────────────────────
const name_en = $('[data-testid=product-name]').text_sane() || null;
const brand_name = $('[data-testid=product-brand-name]').text_sane() || null;

// ── Rate ──────────────────────────────────────────────────────────────────────
const rate_raw_str = $('.prd-rating-info dt span').text_sane();
const rate_parsed = parseFloat(rate_raw_str);
const rate_flags = [];
let rate = null;
if (rate_raw_str) {
  if (!isNaN(rate_parsed) && rate_parsed >= 0 && rate_parsed <= 5) {
    rate = rate_parsed;
  } else {
    rate_flags.push('rating_invalid');
  }
}

// ── Review count ──────────────────────────────────────────────────────────────
const review_raw = $('[data-testid=product-review-link] span.notranslate').text_sane();
const review_count = review_raw
  ? (parseInt(review_raw.replace(/,/g, ''), 10) || 0)
  : 0;

// ── Soldout ───────────────────────────────────────────────────────────────────
// state-stock class on the add-to-cart button means out of stock
const is_soldout = !!$('[data-testid=product-addtocart-button].state-stock').length;

// ── Badge flags ───────────────────────────────────────────────────────────────
// Multiple badges may exist; gather all texts
const badge_texts = $('.prd-bedge span').map((_, el) => $(el).text_sane()).get().filter(Boolean);
const badge_joined = badge_texts.join(' ');
const best_flag = badge_texts.some(t => t === 'BEST');
const new_flag = badge_texts.some(t => t === 'NEW');
const early_access_flag = /early.?access/i.test(badge_joined);
const hot_deal_flag = /hot.?deal/i.test(badge_joined);

// ── Claim tags ────────────────────────────────────────────────────────────────
const claim_tags_arr = $('.list-emblem li').map((_, el) => $(el).text_sane()).get().filter(Boolean);
const claim_tags = claim_tags_arr.length ? claim_tags_arr : null;

// ── Category ids (breadcrumb) ─────────────────────────────────────────────────
const category_ids_arr = $('.location-bar .loc_cat').map((_, el) => $(el).text_sane()).get().filter(Boolean);
const category_ids = category_ids_arr.length ? category_ids_arr : null;

// ── Flags ─────────────────────────────────────────────────────────────────────
const flags = [...rate_flags];
if (!prdt_no) flags.push('missing_prdt_no');
if (!name_en) flags.push('product_enrich_failed');

// ── scraped_date ──────────────────────────────────────────────────────────────
const scraped_date = new Date().toISOString().slice(0, 10);

return {
  entity: 'product',
  prdt_no: prdt_no || null,
  product_url: input.url || null,
  name_en,
  brand_name,
  rate,
  review_count,
  is_soldout,
  best_flag,
  new_flag,
  early_access_flag,
  hot_deal_flag,
  claim_tags,
  category_ids,
  scraped_date,
  scraper_flags: flags,
};
