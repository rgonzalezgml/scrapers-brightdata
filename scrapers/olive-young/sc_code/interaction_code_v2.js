// interaction_code_v2.js — sc_code (Code worker)
// Cambio vs v1: arquitectura correcta Stage 1.
// v1 navegaba un listing HTML con Browser. v2 consume el Rankings API JSON
// directamente con Code worker (sin browser), colecta entidades `ranking`, y
// llama next_stage({url}) para enrichment de productos que aparecen en 2+
// rankings (hasta 10 enrichments — spec §8).
// Arregla: E6 (detail necesita Vue+CSRF → lo hace Stage 2 Browser), E3 (solo
// region KR/USA, language-code=en, country codes=10).
// Compatibilidad backward: si input.url llega, delega al parser (vendor mode).

const RANKING_API = 'https://product-ranking-service.oliveyoung.com/v1/pages/ranking/sales/products';
const DEFAULT_REGIONS = ['KR', 'USA'];
const DEFAULT_CATEGORY_IDS = [
  '1000000001', // All
  '1000000008', // Skincare
  '1000000031', // Makeup
  '1000000052', // Bath & Body
  '1000000003', // Masks
  '1000000011', // Suncare
  '1000000012', // Hair Care
  '1000000013', // Body Care
  '1000000014', // Cleansing
  '1000000015', // Tools & Accessories
];
const MAX_ENRICHMENTS = 10;

// ── Backward compatibility: vendor/BrightData preview passes input.url ──────
if (input.url) {
  navigate(input.url, { allow_status: [200, 400, 404, 410] });
  const data = parse();
  if (data) collect(data);
  // stop — do not continue to API loop
} else {
  // ── Stage 1: Rankings API loop ──────────────────────────────────────────────
  const regions = (input.regions && input.regions.length)
    ? input.regions
    : DEFAULT_REGIONS;

  const category_ids = (input.category_ids && input.category_ids.length)
    ? input.category_ids
    : DEFAULT_CATEGORY_IDS;

  // cap max_pages to [1, 10]
  const raw_max = parseInt(input.max_pages, 10);
  const max_pages = (!isNaN(raw_max) && raw_max >= 1) ? Math.min(raw_max, 10) : 10;

  // Tracking for enrichment: prdt_no → { count, product_url }
  const seen = {};
  let enrichment_count = 0;
  let iterations = 0;

  for (let ri = 0; ri < regions.length; ri++) {
    const region = regions[ri];
    for (let ci = 0; ci < category_ids.length; ci++) {
      if (iterations >= max_pages) break;
      iterations++;

      const category_id = category_ids[ci];
      const api_url = RANKING_API
        + '?category-id=' + category_id
        + '&region=' + region
        + '&language-code=en'
        + '&margin-country-code=10'
        + '&delivery-country-code=10';

      navigate(api_url, { allow_status: [200, 400, 404, 410] });

      const rows = parse();

      if (!rows || !Array.isArray(rows)) continue;

      for (let k = 0; k < rows.length; k++) {
        const row = rows[k];
        if (!row) continue;

        collect(row);

        // Enrichment tracking — only for valid prdt_no
        const prdt_no = row.prdt_no;
        if (prdt_no && row.product_url) {
          seen[prdt_no] = (seen[prdt_no] || 0) + 1;
          if (seen[prdt_no] === 2 && enrichment_count < MAX_ENRICHMENTS) {
            next_stage({ url: row.product_url });
            enrichment_count++;
          }
        }
      }
    }
    if (iterations >= max_pages) break;
  }
}
