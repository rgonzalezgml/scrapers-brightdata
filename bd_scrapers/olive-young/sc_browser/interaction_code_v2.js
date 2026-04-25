// interaction_code_v2.js — sc_browser (Browser worker)
// Cambio vs v1: es Stage 2. v1 navegaba el best-seller listing HTML para
// extraer URLs (Stage 1 incorrecto). v2 recibe input.url de un product detail
// desde next_stage({url}) disparado por sc_code Stage 1, navega con JS render
// completo (Vue+CSRF, E6), guarda con collect(parse()).
// Guards: .co.kr → skip (E1), Cloudflare challenge iframe (E2), Vue timeout
// (flag product_enrich_failed), 404 (dead_page).

// Guard: .co.kr out-of-scope (E1)
if (!input.url) {
  dead_page('no_url');
}

if (/oliveyoung\.co\.kr/i.test(input.url)) {
  collect({
    entity: 'product',
    product_url: input.url,
    scraper_flags: ['source_gone'],
  });
} else {
  navigate(input.url, { allow_status: [200, 400, 404, 410] });

  // Guard: Cloudflare challenge (E2) — check before waiting for real content
  if (el_exists('iframe[src*="cdn-cgi/challenge-platform"]', 3000)) {
    collect({
      entity: 'product',
      product_url: input.url,
      scraper_flags: ['cloudflare_challenge'],
    });
  } else if (el_exists('.main.type-error.error-not-found', 2000)) {
    // Guard: 404 product not found
    dead_page('product_not_found');
  } else {
    // Wait for Vue to render the product name (up to 15s — spec requires full Vue exec)
    if (!el_exists('[data-testid=product-name]', 15000)) {
      collect({
        entity: 'product',
        product_url: input.url,
        scraper_flags: ['product_enrich_failed'],
      });
    } else {
      collect(parse());
    }
  }
}
