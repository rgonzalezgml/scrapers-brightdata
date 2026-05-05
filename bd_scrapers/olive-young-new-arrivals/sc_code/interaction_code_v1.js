// ============================================================
// STAGE 2 — INTERACTION CODE
// Input: producto completo desde Stage 1
// Navega a la URL del producto y extrae detalle.
// ============================================================

navigate(input.url, { wait_until: 'networkidle2' });

wait_visible('.prd-detail-content', { timeout: 30000 });

const detail = parse();

collect({
  // Campos heredados de Stage 1
  prdt_no: input.prdt_no,
  url: input.url,
  product_name_en: input.product_name_en,
  product_name_kr: input.product_name_kr,
  brand_name_en: input.brand_name_en,
  brand_image_url: input.brand_image_url,
  sale_amt: input.sale_amt,
  nrml_amt: input.nrml_amt,
  image_url: input.image_url,
  has_gift: input.has_gift,
  corner_name: input.corner_name,
  scraped_date: input.scraped_date,

  // Campos enriquecidos desde Stage 2
  brand_no: detail.brand_no,
  brand_url: detail.brand_url,
  category: detail.category,
  categories: detail.categories,
  is_best: detail.is_best,
  is_new: detail.is_new,
  rating: detail.rating,
  review_count: detail.review_count,
  discount_rate: detail.discount_rate,
  why_we_love_it: detail.why_we_love_it,
  how_to_use: detail.how_to_use,
  extra_images: detail.extra_images,
});