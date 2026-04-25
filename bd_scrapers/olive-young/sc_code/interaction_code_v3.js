// interaction_code_v3.js — sc_code (Code worker)
// v3 corrige v2: región USA → US (USA da 400 en la API live, verificado 2026-04-24).
// Todo lo demás igual: Stage 1 Rankings API loop, enrichment tracking,
// next_stage({url}) para productos que aparecen en 2+ rankings (≤10 enrichments).

const RANKING_API = 'https://product-ranking-service.oliveyoung.com/v1/pages/ranking/sales/products';
const DEFAULT_REGIONS = ['KR', 'US'];
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
  if (Array.isArray(data)) {
    for (let i = 0; i < data.length; i++) {
      if (data[i]) collect(data[i]);
    }
  } else if (data) {
    collect(data);
  }
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

  // Tracking for enrichment: prdt_no → count
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

        // Skip sentinel error rows (no prdt_no = api error flag row)
        if (!row.prdt_no) {
          collect(row);
          continue;
        }

        collect(row);

        // Enrichment: next_stage for products appearing in 2+ rankings
        if (row.product_url) {
          seen[row.prdt_no] = (seen[row.prdt_no] || 0) + 1;
          if (seen[row.prdt_no] === 2 && enrichment_count < MAX_ENRICHMENTS) {
            next_stage({ url: row.product_url });
            enrichment_count++;
          }
        }
      }
    }
    if (iterations >= max_pages) break;
  }
}
