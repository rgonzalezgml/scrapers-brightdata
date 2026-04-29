// // ============================================================================
// // STAGE 2 — PARSER CODE: Extraer detalle completo del producto
// // ============================================================================
// // Combina la metadata del ranking (Stage 1 via input) con datos
// // extraídos de la página de detalle del producto.
// //
// // NOTA: Los selectores de detalle necesitan verificación.
// // Inspeccioná el HTML de https://www.cosme.net/products/10147158/
// // en el IDE y ajustá si algo sale vacío.
// // ============================================================================

// const base = 'https://www.cosme.net';
// const now  = new Date().toISOString();

// // ---- Datos de la página de detalle ----

// // Descripción
// const description = $('[class*="description"], .product-detail-text, .product-info')
//   .first().text_sane();

// // Todas las imágenes
// const all_images = [];
// $('img[src*="media/product"], img[src*="skuimg"]').each(function () {
//   const src = $(this).attr('src') || '';
//   if (src && all_images.indexOf(src) === -1) all_images.push(src);
// });

// // Ingredientes
// const ingredients = $('[class*="ingredient"], .product-ingredient')
//   .first().text_sane();

// // ---- Registro final: Stage 1 + detalle ----

// return {
//   // Producto
//   product_id:       input.product_id,
//   product_name:     input.product_name,
//   product_url:      input.prod_url,
//   product_img:      input.prod_img_url,

//   // Marca
//   brand_name:       input.brand_name,
//   brand_id:         input.brand_id,
//   brand_url:        input.brand_href,

//   // Categoría
//   category:         input.category,
//   category_url:     input.category_href,

//   // Precio
//   price_text:       input.price_text,
//   price_yen:        input.price_yen,
//   size:             input.size,
//   is_open_price:    input.is_open_price,
//   tax_included:     input.tax_included,

//   // Ranking
//   rank:             input.rank,
//   rank_change:      input.rank_change,
//   rating:           input.rating,
//   review_count:     input.review_count,
//   release_date:     input.release_date,
//   is_best_cosme:    input.is_best_cosme,
//   is_new:           input.is_new,

//   // Detalle (Stage 2)
//   description,
//   all_images,
//   ingredients,
//   shop_url:         input.shop_url,

//   // Metadata
//   period_start:     input.meta_period_start,
//   period_end:       input.meta_period_end,
//   total_products:   input.meta_total,

//   scraped_at:       now,
// };





// ============================================================================
// STAGE 2 — PARSER CODE: Detalle completo del producto
// ============================================================================
// Selectores basados en el HTML real de /products/10290194/
// Secciones clave:
//   #product-header  → nombre, tabs (reviews, fotos, Q&A)
//   #product-spec    → tabla de especificaciones (dl con clases)
//   .info-rating     → rating, puntos, ranking en categoría
//   .act-counter     → likes, haves
//   #product-line-up → productos relacionados
// ============================================================================

const base = 'https://www.cosme.net';
const now = new Date().toISOString();

// ===== HEADER =====

// Nombre del producto (japonés original)
const product_name_jp = $('h2.item-name strong.pdct-name a').text_sane();
const brand_name_jp = $('h2.item-name span.brd-name a.brand').text_sane();

// Tabs: reviews, fotos, Q&A counts
const review_count_text = $('.navi-tab .review .num').text_sane();
const review_count = parseInt((review_count_text || '').replace(/[^\d]/g, ''), 10) || 0;

const photo_count_text = $('.navi-tab .post-photo .num').text_sane();
const photo_count = parseInt((photo_count_text || '').replace(/[^\d]/g, ''), 10) || 0;

const qa_count_text = $('.navi-tab .qa .num').text_sane();
const qa_count = parseInt((qa_count_text || '').replace(/[^\d]/g, ''), 10) || 0;

// ===== RATING & STATS =====

// Rating (ej: "5.2")
const rating_detail = parseFloat($('p.average').text_sane()) || null;

// Points (ej: "59.1pt")
const points_text = $('p.point').text_sane();
const points = parseFloat((points_text || '').replace(/[^\d.]/g, '')) || null;

// Category ranking (ej: "5位" → 5)
const cat_rank_text = $('.info-ranking .info-ranking span').first().text_sane();
const cat_rank = parseInt((cat_rank_text || '').replace(/[^\d]/g, ''), 10) || null;
const cat_rank_name = $('.info-ranking .info-ctg a').text_sane();

// Likes & Haves
const likes_text = $('.act-counter[data-object\\.class="product_like"]').first().text();
const likes = parseInt((likes_text || '').replace(/[^\d]/g, ''), 10) || 0;

const haves_text = $('.act-counter[data-object\\.class="product_have"]').first().text();
const haves = parseInt((haves_text || '').replace(/[^\d]/g, ''), 10) || 0;

// ===== PRODUCT SPEC TABLE (#product-spec) =====

// Fabricante (メーカー)
const manufacturer = $('#product-spec dl.maker dd a').text_sane();
const manufacturer_url = new URL($('#product-spec dl.maker dd a').attr('href') || '', base).href;

// Categoría completa (アイテムカテゴリ)
const category_path = [];
$('#product-spec dl.item-category dd a').each(function () {
  category_path.push({
    name: $(this).text_sane(),
    url: new URL($(this).attr('href') || '', base).href,
  });
});
const category_full = category_path.map(function (c) { return c.name; }).join(' > ');

// Ranking en categoría (ランキングIN)
const ranking_in = [];
$('#product-spec dl.ranking-in dd li').each(function () {
  ranking_in.push($(this).find('a').text_sane());
});

// Descripción (商品説明)
const description = $('#product-spec dl.item-description dd').html();
const description_clean = description
  ? description.replace(/<br\s*\/?>/gi, '\n').replace(/<[^>]*>/g, '').trim()
  : '';

// Modo de uso (使い方)
const how_to_use_html = $('#product-spec dl.use dd').html();
const how_to_use = how_to_use_html
  ? how_to_use_html.replace(/<br\s*\/?>/gi, '\n').replace(/<[^>]*>/g, '').trim()
  : '';

// Ingredientes completos (全成分)
const ingredients_html = $('#product-spec dl.all-components dd').html();
const ingredients = ingredients_html
  ? ingredients_html.replace(/<br\s*\/?>/gi, '\n').replace(/<[^>]*>/g, '').trim()
  : '';

// Sitio oficial (公式サイト)
const official_url = $('#product-spec dl.official-site dd a').attr('href') || '';

// Clasificación / tipo de producto (分類)
const classification = $('#product-spec dl.quasi-drug dd').text_sane();

// JAN code
const jan_code = $('#product-spec dl.jan-code dd').text_sane();

// ===== IMAGES =====

const all_images = [];
$('.pict-list img, .vri-item-list img').each(function () {
  const src = $(this).attr('src') || '';
  if (src && all_images.indexOf(src) === -1) all_images.push(src);
});

// ===== RELATED PRODUCTS =====

const related = [];
$('#product-line-up .item-list a').each(function () {
  const href = $(this).attr('href') || '';
  const name = $(this).find('.item-list-txt').text_sane();
  if (name && href) {
    related.push({
      name: name,
      url: new URL(href, base).href,
    });
  }
});

// ===== STORES =====

const stores = [];
$('#product-shopping-site .cosmestore .toggle ul li a').each(function () {
  stores.push($(this).text_sane());
});

// ===== FINAL RECORD =====

return {
  // Producto (Stage 1 + detalle)
  product_id: input.product_id,
  product_name: input.product_name,
  product_name_jp: product_name_jp,
  product_url: input.prod_url,
  product_img: input.prod_img_url,

  // Marca
  brand_name: input.brand_name,
  brand_name_jp: brand_name_jp,
  brand_id: input.brand_id,
  brand_url: input.brand_href,
  manufacturer: manufacturer,
  manufacturer_url: manufacturer_url,

  // Categoría
  category: input.category,
  category_url: input.category_href,
  category_full: category_full,
  category_path: category_path,

  // Precio (Stage 1)
  price_text: input.price_text,
  price_yen: input.price_yen,
  size: input.size,
  is_open_price: input.is_open_price,
  tax_included: input.tax_included,

  // Ranking (Stage 1 + detalle)
  rank: input.rank,
  rank_change: input.rank_change,
  rating: input.rating,
  rating_detail: rating_detail,
  points: points,
  cat_rank: cat_rank,
  cat_rank_name: cat_rank_name,
  ranking_in: ranking_in,

  // Social
  review_count: review_count,
  photo_count: photo_count,
  qa_count: qa_count,
  likes: likes,
  haves: haves,

  // Release
  release_date: input.release_date,
  is_best_cosme: input.is_best_cosme,
  is_new: input.is_new,

  // Detalle (Stage 2)
  description: description_clean,
  how_to_use: how_to_use,
  ingredients: ingredients,
  classification: classification,
  jan_code: jan_code,
  official_url: official_url,
  all_images: all_images,
  shop_url: input.shop_url,
  stores: stores,
  related_products: related,

  // Metadata
  period_start: input.meta_period_start,
  period_end: input.meta_period_end,
  total_products: input.meta_total,

  scraped_at: now,
  source: input.source || 'cosme.net/ranking/products',
  country: input.country || 'JP',
  ranking_by: 'product',
};