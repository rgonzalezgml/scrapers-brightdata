// interaction_code_v3 — Alibaba detail page (Code worker).
//
// Cambios vs v2:
//   v2 usaba `navigate(input.url)` que espera DOMContentLoaded. En run 10 se
//   detectaron 341 registros con solo cleaned_product_name + product_url y 0
//   supplier/precio: DOMContentLoaded timeout en páginas Alibaba pesadas. El
//   error literal de BrightData: "Timed out waiting for window.DomContentLoaded
//   event — specify wait_until option in navigate command."
//
//   v3 aplica el fix sugerido:
//     - `navigate(url, {wait_until: 'navigate'})` → no espera DOMContentLoaded.
//     - `el_exists('h1', 30000)` → confirma que el HTML inicial (pre-React) cargó.
//     - `el_exists(DYNAMIC_SELECTOR, 20000)` → espera hidratación React (precio /
//       supplier). Si no aparece en 20 s, parse() corre con sus fallbacks de texto.
//   Mismo patrón que sc_browser/interaction_code_detail_v1.js, adaptado a Code Worker.
//
// Flow:
//   1. navigate(input.url, {wait_until: 'navigate'})
//   2. Guard bot-check (timeout corto 2s).
//   3. Guard URL shape (regex product-detail).
//   4. el_exists('h1', 30000) — HTML inicial presente.
//   5. el_exists(DYNAMIC_SELECTOR, 20000) — componentes React hidratados.
//   6. parse() → data Fase 1 (10 keys vendor-literales).
//   7. Guard invariantes: product_url + cleaned_product_name no pueden ser null.
//   8. collect(data).

navigate(input.url, { wait_until: 'navigate' });

// Guard 1: bot-check / error page (timeout corto: si van a aparecer ya están).
if (el_exists(
  'h1:contains("Access Denied"), h1:contains("Just a moment"), [action="/errors/validateCaptcha"]',
  2000
)) {
  dead_page('bot_check_detected');
}

// Guard 2: URL shape.
if (!input.url.match(/\/product-detail\/.+_\d+\.html/)) {
  dead_page('not_a_product_url');
}

// Esperar HTML inicial (h1 aparece antes de hidratación React).
if (!el_exists('h1', 30000)) {
  dead_page('page_did_not_load');
}

// Esperar componentes dinámicos (precio / supplier). Si no aparecen en 20 s,
// parse() continuará con sus fallbacks de body-text.
const DYNAMIC_SELECTOR =
  '.price-item, [data-testid="range-price"], [data-testid="seller-overview-card-company-link"]';
el_exists(DYNAMIC_SELECTOR, 20000);

const data = parse();

// Guard 3: invariantes.
if (!data.product_url || !data.cleaned_product_name) {
  dead_page('missing_invariants: product_url or cleaned_product_name');
}

collect(data);
