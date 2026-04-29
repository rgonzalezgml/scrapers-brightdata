// // ============================================================================
// // STAGE 2 — INTERACTION CODE (Browser): Extraer detalle de cada producto
// // ============================================================================

// console.log(input);
// if (!input.url) bad_input('Missing prod_url');

// navigate(input.url, { timeout: 30000, allow_status: [404] });

// if (el_exists('.error-404, img[src*="error_pages"]')) {
//   dead_page('Product not found: ' + input.product_id);
// }

// try {
//   wait('dd.summary, .product-header, h2', { timeout: 15000 });
// } catch (e) {
//   blocked('Product page did not load: ' + input.product_id);
// }

// collect(parse());



// ============================================================================
// STAGE 2 — INTERACTION CODE (Browser): Detalle de producto
// ============================================================================

if (!input.url) bad_input('Missing prod_url');

navigate(input.url, { timeout: 30000, allow_status: [404] });

if (el_exists('.error-404, img[src*="error_pages"]')) {
  dead_page('Product not found: ' + input.product_id);
}

try {
  wait('#product-spec', { timeout: 15000 });
} catch (e) {
  blocked('Product page did not load: ' + input.product_id);
}

collect(parse());