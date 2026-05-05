// ============================================================
// STAGE 3 — INTERACTION CODE v1 (sc_code)
// Input: { url, product_id, product_name, brand_id, brand_name,
//          brand_url, release_date, shop_url, scraped_at }
// Carga la página de detalle del producto y emite collect(parse()).
// Si la página retorna 404 o body < 5 KB → collect(campos_base)
// con flag detail_unavailable (spec §6, §8).
// ============================================================

if (!input.url) bad_input('Missing url');

// navigate(input.url, { timeout: 30000, allow_status: [404] });

// const sc = status_code();

// if (sc === 404) {
//   collect({
//     product_id:       input.product_id,
//     product_url:      input.url,
//     product_name:     input.product_name,
//     brand_id:         input.brand_id,
//     brand_name:       input.brand_name,
//     brand_url:        input.brand_url,
//     release_date:     input.release_date,
//     shop_url:         input.shop_url,
//     scraped_at:       input.scraped_at,
//     scraper_flags:    ['detail_unavailable'],
//   });
// } else {
//   collect(parse());
// }


navigate(input.url, { wait_until: 'domcontentloaded' });
// collect({
//     product_id:       input.product_id,
//     product_url:      input.url,
//     product_name:     input.product_name,
//     brand_id:         input.brand_id,
//     brand_name:       input.brand_name,
//     brand_url:        input.brand_url,
//     release_date:     input.release_date,
//     shop_url:         input.shop_url,
//     scraped_at:       input.scraped_at,
//     scraper_flags:    ['detail_unavailable'],
//   });


collect(parse())