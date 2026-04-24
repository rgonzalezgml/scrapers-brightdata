// parser_code_v4.js — sc_browser (Browser worker)
// Cambio vs v3 (sc_code parser): este parser solo maneja Stage 2 (product
// detail enrichment). Stage 1 (listing HTML) emite rows directamente desde
// interaction_code_v4.js via collect() inline — no hay parse() en Stage 1
// porque la extracción ocurre en dos momentos DOM separados (tab USA y tab KR)
// y parse() no puede pasar contexto entre navigate() calls (R9, R8).
//
// Stage 2 logic es idéntico a parser_code_v2.js.
// Arregla: E8 (Rankings API bloqueada — ahora Stage 1 no usa esa API).

// ── Stage 2 guard: solo se llama parse() desde Stage 2 ───────────────────────
// interaction_code_v4 llama collect(parse()) únicamente cuando input.url tiene
// /product/detail, así que aquí siempre estamos en el detail page.

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
// Multiple badges may exist; gather all texts — R12: .map((_,el)=>).get()
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
