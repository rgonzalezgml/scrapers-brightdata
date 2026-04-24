// interaction_code_v2 — IndiaMART Stage 2 product detail (Code worker).
//
// Cambios vs vendor (`vendor/sc_code/interaction_code.js`):
//   vendor era trivial (6 loc): `navigate(input.url); collect(parse());`.
//   Sin guards: una URL fuera de `/proddetail/` patterns o una página de
//   bot-check gastaba un parse() completo y emitía row degenerado.
//
//   v2 adopta el mismo patrón idiomático que Stage 1 y que
//   `scrapers/alibaba/sc_code/interaction_code_v2.js`:
//     - `el_exists(sel, timeoutMs)` → boolean, no lanza.
//     - `dead_page(reason)` → marca URL como dead con razón explícita.
//
// Flow:
//   1. navigate(input.url).
//   2. Guard 1: bot-check (mismo patrón que Stage 1).
//   3. Guard 2: URL shape — /proddetail/{slug}-{PID}.html, PID 11-13 dígitos.
//      Catch también rutas Disallow (/pd/, /proddetail1/, /proddetail2/).
//   4. parse() → dict de 20 fields del vendor.
//   5. Guard 3: invariantes spec §4 — product_id, name_clean, supplier_name
//      son las 3 llaves que hacen útil una fila.
//   6. collect(data).
//
// NOTA: parser_code_v2 es idéntico al vendor (no refactor a JSON-LD todavía,
// eso queda para la Fase 2 del scraper según spec §4). Los guards viven acá.



navigate(input.url);

// Guard 1: bot-check / "Just a moment" Cloudflare / captcha redirect.
// Mismo selector que Stage 1 para consistencia.
if (el_exists(
  'h1:contains("Access Denied"), h1:contains("Just a moment"), [action*="/errors/"]',
  2000
)) {
  dead_page('bot_check_detected');
}

// Guard 2a: rutas Disallow del robots.txt (spec §3). Si una seed del
// Stage 1 se coló pese al filtro del parser, matar acá.
if (/\/(pd|proddetail[12])\//i.test(input.url)) {
  dead_page('route_disallowed: robots.txt Disallow');
}

// Guard 2b: URL shape canónica (spec §3):
//   https://www.indiamart.com/proddetail/{slug}-{PID}.html
//   con PID de 11 a 13 dígitos.
if (!/\/proddetail\/[^/]+-\d{11,13}\.html/i.test(input.url)) {
  dead_page('not_a_proddetail_url');
}

// Extracción — parser_code_v3 emite los 29 fields de §4+§5 (JSON-LD-primero).
const data = parse();

// Guard 3: invariantes spec §4/§8. Las 4 llaves mínimas para que la fila
// sea útil en el negocio (Precios B2B India): product_id, nombre, supplier,
// y **precio**. Si falta CUALQUIERA, no emitir fila — se marca dead_page
// con razón específica y queda registrado en el historial del run con
// el error code (searchable en el dashboard para triage).
//
// Regla de negocio (memoria `feedback_scraper_invariants.md`): invariantes
// del sitio van non-nullable en el Output Schema; null = fallo de parser,
// NO dato válido. Mejor perder 1 fila con `dead_page('missing_price')`
// visible, que emitir 1000 filas con price=null que contaminan el dataset.
//
// Spec §8 SKIP rules alineadas:
//   - product_id no extraible del path
//   - JSON-LD Product ausente / parser devuelve name_clean null
//   - Product.offers.price ausente o no numerico
//   - supplier (seller.name) ausente
// if (!data.product_id) {
//   dead_page('missing_product_id');
// }
// if (!data.product_name_clean) {
//   dead_page('missing_name');
// }
// if (!data.supplier_name) {
//   dead_page('missing_supplier');
// }


// // price_value_raw es string ("50") del JSON-LD offers.price o del title
// // parseado. Cadena vacía / "0" / null → sin precio → skip.
// const price_raw_str = data.price_value_raw;
// const has_price =
//   price_raw_str !== null &&
//   price_raw_str !== undefined &&
//   String(price_raw_str).trim() !== '' &&
//   parseFloat(String(price_raw_str)) > 0;
// if (!has_price) {
//   dead_page('missing_price');
// }

collect(data);
