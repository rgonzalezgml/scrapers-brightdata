// ============================================================
// STAGE 2 — PARSER CODE
// Extrae detalle del producto desde su página individual.
//
// Selectores clave:
//   brand_url/brand_no → a[data-testid="product-brand-name"]
//   categorías         → .loc_wrap li a span.loc_cat
//   is_best/is_new     → .prd-bedge span
//   rating             → .review-average-left
//   review_count       → .review-average-right-reviews strong
//   discount_rate      → .discount-rate
//   why_we_love_it     → [data-testid="product-whyweloveit-content"]
//   how_to_use         → [data-testid="product-howtouse-content"]
//   extra_images       → [data-testid="product-thumbnail-list"] img
// ============================================================

const BASE_URL = 'https://global.oliveyoung.com';

// ── Brand ────────────────────────────────────────────────────
const brandLink = $('a[data-testid="product-brand-name"]').first();
const brandHref = brandLink.attr('href') || '';
const brand_url = brandHref ? BASE_URL + brandHref : null;
const brandNoMatch = brandHref.match(/brandNo=([^&]+)/);
const brand_no = brandNoMatch ? brandNoMatch[1] : null;

// ── Categorías ────────────────────────────────────────────────
// breadcrumb: Makeup > Face > Powder & Pact
// category   → la más específica (última)
// categories → array completo como JSON string
const cats = [];
$('.loc_wrap li a span.loc_cat').each((i, el) => {
    const txt = $(el).text().trim();
    if (txt) cats.push(txt);
});
const category = cats.length > 0 ? cats[cats.length - 1] : null;
const categories = cats.length > 0 ? JSON.stringify(cats) : null;

// ── Badges ───────────────────────────────────────────────────
let is_best = false;
let is_new = false;
$('.prd-bedge span').each((i, el) => {
    const txt = $(el).text().trim().toUpperCase();
    if (txt === 'BEST') is_best = true;
    if (txt === 'NEW') is_new = true;
});

// ── Rating y reviews ─────────────────────────────────────────
const ratingText = $('.review-average-left').first().text().trim();
const rating = ratingText ? parseFloat(ratingText) : null;

const reviewText = $('.review-average-right-reviews strong').first().text().trim();
const review_count = reviewText ? parseInt(reviewText, 10) : null;

// ── Descuento ────────────────────────────────────────────────
const discountText = $('.discount-rate').first().text().trim();
const discount_rate = discountText ? discountText.replace('%', '').trim() : null;

// ── Textos de producto ────────────────────────────────────────
const why_we_love_it = $('[data-testid="product-whyweloveit-content"]').first().text().trim() || null;
const how_to_use = $('[data-testid="product-howtouse-content"]').first().text().trim() || null;

// ── Imágenes adicionales ──────────────────────────────────────
const extra_images = [];
$('[data-testid="product-thumbnail-list"] .swiper-slide img').each((i, img) => {
    const src = $(img).attr('src') || '';
    if (src && !src.includes('load.png')) extra_images.push(src);
});

return {
    brand_no,
    brand_url,
    category,
    categories,
    is_best,
    is_new,
    rating,
    review_count,
    discount_rate,
    why_we_love_it,
    how_to_use,
    extra_images: extra_images.join(' | '),
};