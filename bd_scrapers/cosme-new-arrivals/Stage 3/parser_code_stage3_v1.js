// ============================================================
// STAGE 3 — PARSER CODE v1
// Combina los campos base recibidos por input (product_id,
// product_name, brand_id, brand_name, brand_url, release_date,
// shop_url, scraped_at) con los campos enriquecidos extraídos
// de /products/{id}/ (spec §5 tabla Stage 3).
// Selectores validados en producción desde
// cosme-ranking-products/sc_code/parser_code_v1.js.
// Si #product-spec no existe (página vacía / body < 5 KB)
// devuelve solo los campos base con flag detail_unavailable.
// ============================================================

const base = 'https://www.cosme.net';

// ── Guard: página sin contenido ──────────────────────────────

if (!$('#product-spec').length) {
  return {
    product_id: input.product_id,
    product_url: input.url,
    product_name: input.product_name,
    brand_id: input.brand_id,
    brand_name: input.brand_name,
    brand_url: input.brand_url,
    release_date: input.release_date,
    shop_url: input.shop_url,
    scraped_at: input.scraped_at ?? new Date().toISOString(),
    scraper_flags: ['detail_unavailable'],
  };
}

// ── Tabs: review / photo / Q&A counts ────────────────────────

const review_count_text = $('.navi-tab .review .num').text_sane();
const review_count = parseInt((review_count_text || '').replace(/[^\d]/g, ''), 10) || 0;

const photo_count_text = $('.navi-tab .post-photo .num').text_sane();
const photo_count = parseInt((photo_count_text || '').replace(/[^\d]/g, ''), 10) || 0;

const qa_count_text = $('.navi-tab .qa .num').text_sane();
const qa_count = parseInt((qa_count_text || '').replace(/[^\d]/g, ''), 10) || 0;

// ── Rating & stats ────────────────────────────────────────────

const rating_detail = parseFloat($('p.average').text_sane()) || null;

const points_text = $('p.point').text_sane();
const points = parseFloat((points_text || '').replace(/[^\d.]/g, '')) || null;

const cat_rank_text = $('.info-ranking .info-ranking span').first().text_sane();
const cat_rank = parseInt((cat_rank_text || '').replace(/[^\d]/g, ''), 10) || null;
const cat_rank_name = $('.info-ranking .info-ctg a').text_sane() || null;

// ── Likes & haves ─────────────────────────────────────────────

const likes_text = $('.act-counter[data-object\\.class="product_like"]').first().text();
const likes = parseInt((likes_text || '').replace(/[^\d]/g, ''), 10) || 0;

const haves_text = $('.act-counter[data-object\\.class="product_have"]').first().text();
const haves = parseInt((haves_text || '').replace(/[^\d]/g, ''), 10) || 0;

// ── Product spec table (#product-spec) ───────────────────────

// Manufacturer
const manufacturer = $('#product-spec dl.maker dd a').text_sane() || null;
const manufacturer_href = $('#product-spec dl.maker dd a').attr('href') || '';
const manufacturer_url = manufacturer_href
  ? new URL(manufacturer_href, base).href
  : null;

// Category path (array of {name, url}) + breadcrumb string
const category_path = [];
$('#product-spec dl.item-category dd a').each(function () {
  const href = $(this).attr('href') || '';
  category_path.push({
    name: $(this).text_sane(),
    url: href ? new URL(href, base).href : null,
  });
});
const category_full = category_path.map(function (c) { return c.name; }).join(' > ') || null;

// Description (HTML → plain text, <br> → \n)
const description_html = $('#product-spec dl.item-description dd').html();
const description = description_html
  ? description_html.replace(/<br\s*\/?>/gi, '\n').replace(/<[^>]*>/g, '').trim()
  : null;

// How to use
const how_to_use_html = $('#product-spec dl.use dd').html();
const how_to_use = how_to_use_html
  ? how_to_use_html.replace(/<br\s*\/?>/gi, '\n').replace(/<[^>]*>/g, '').trim()
  : null;

// Ingredients
const ingredients_html = $('#product-spec dl.all-components dd').html();
const ingredients = ingredients_html
  ? ingredients_html.replace(/<br\s*\/?>/gi, '\n').replace(/<[^>]*>/g, '').trim()
  : null;

// Official URL
const official_url = $('#product-spec dl.official-site dd a').attr('href') || null;

// Classification (quasi-drug)
const classification = $('#product-spec dl.quasi-drug dd').text_sane() || null;

// JAN code
const jan_code = $('#product-spec dl.jan-code dd').text_sane() || null;

// ── Images ────────────────────────────────────────────────────

const all_images = [];
$('.pict-list img, .vri-item-list img').each(function () {
  const src = $(this).attr('src') || '';
  if (src && all_images.indexOf(src) === -1) all_images.push(src);
});

// ── Stores ────────────────────────────────────────────────────

const stores = [];
$('#product-shopping-site .cosmestore .toggle ul li a').each(function () {
  stores.push($(this).text_sane());
});

// ── Related products ─────────────────────────────────────────

const related_products = [];
$('#product-line-up .item-list a').each(function () {
  const href = $(this).attr('href') || '';
  const name = $(this).find('.item-list-txt').text_sane();
  if (name && href) {
    related_products.push({
      name: name,
      url: new URL(href, base).href,
    });
  }
});

// ── Final record: base + enriched ────────────────────────────

return {
  // Base fields (from Stage 2 via input)
  product_id: input.product_id,
  product_url: input.url,
  product_name: input.product_name,
  // brand_id:         input.brand_id,
  brand_name: input.brand_name,
  brand_url: input.brand_url,
  release_date: input.release_date,
  shop_url: input.shop_url,
  scraped_at: new Date().toISOString(),

  // Enriched fields (from product detail page)
  description: description,
  how_to_use: how_to_use,
  ingredients: ingredients,
  classification: classification,
  jan_code: jan_code,
  official_url: official_url,
  manufacturer: manufacturer,
  manufacturer_url: manufacturer_url,
  category_full: category_full,
  category_path: category_path,
  rating_detail: rating_detail,
  points: points,
  review_count: review_count,
  photo_count: photo_count,
  qa_count: qa_count,
  cat_rank: cat_rank,
  cat_rank_name: cat_rank_name,
  likes: likes,
  haves: haves,
  all_images: all_images,
  stores: stores,
  related_products: related_products,
};
