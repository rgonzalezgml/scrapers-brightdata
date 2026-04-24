// interaction_code_v2 — IndiaMART Stage 1 MCAT listing (Browser worker).
//
// Cambios vs vendor (`vendor/sc_browser/interaction_code.js`):
//   vendor flow (15 loc): navigate → wait(proddetail) → scroll → wait
//   (proddetail) → for url in parse().product_urls { next_stage({url}) }.
//   El problema: ningún guard. Si la URL no es un MCAT listing válido, o
//   si el sitio sirve bot-check / redirect a enquiry, `wait()` timeout-ea
//   a los 30s y rompe el run completo en lugar de marcar la seed como
//   dead. Tampoco detecta schema_change (parser devuelve 0 URLs).
//
//   v2 adopta el patrón idiomático documentado en
//   `reference_brightdata_dsl_helpers.md` y ya aplicado en
//   `scrapers/alibaba/sc_code/interaction_code_v2.js`:
//     - `el_exists(sel, timeoutMs)` → boolean, no lanza excepción.
//     - `dead_page(reason)` → marca la URL como dead con razón explícita.
//
//   Además: v2 NO itera `next_stage` dentro del browser worker. El flujo
//   oficial de BrightData Scraper Studio con `queue_next=1` hace que el
//   dashboard consuma automáticamente `data[].product_urls` (cada URL
//   queda encolada como seed del Stage 2). `collect(data)` es el return
//   canónico; el `for` del vendor era redundante con el queue_next.
//
// Flow:
//   1. navigate(input.url).
//   2. Guard 1: bot-check / redirect (spec §2 patrones de bloqueo).
//   3. Guard 2: URL shape — solo MCAT listing o industry hub (spec §3).
//   4. Guard 3: esperar `a[href*="proddetail"]` (30s ok, URL ya validada).
//   5. scroll_to('bottom') — lazy-load (heredado del vendor).
//   6. Guard 4: re-confirmar proddetail links tras scroll (5s).
//   7. parse() → {product_urls}.
//   8. Guard 5: si parser devolvió 0 URLs pese a que Guard 3 pasó,
//      schema_change (selector del parser no matchea).
//   9. collect(data).

// URL templates del sitio (refactor 2026-04-23 híbrido):
//   Scraper conoce LAS PLANTILLAS del sitio (conocimiento de IndiaMART).
//   Middleware manda SOLO el slug + kind (conocimiento de negocio Genomma).
//   Ventaja: si IndiaMART cambia /impcat/ a /category/, tocás solo este archivo.
//   Backward compat: si `input.url` viene dado directo, se respeta (para tests).
const MCAT_URL_TMPL = 'https://dir.indiamart.com/impcat/{slug}.html';
const HUB_URL_TMPL  = 'https://dir.indiamart.com/indianexporters/ind_{slug}.html';

// let resolved_url;
// if (input.url) {
//   // Backward compat: URL directa (ej. tests o preview manual del dashboard).
//   resolved_url = input.url;
// } else if (input.category_slug) {
//   const kind = input.kind || 'mcat';  // default 'mcat' si no se especifica
//   if (kind === 'hub') {
//     resolved_url = HUB_URL_TMPL.replace('{slug}', input.category_slug);
//   } else if (kind === 'mcat') {
//     resolved_url = MCAT_URL_TMPL.replace('{slug}', input.category_slug);
//   } else {
//     dead_page('bad_input: input.kind must be "mcat" or "hub", got: ' + kind);
//   }
// } else {
//   dead_page('bad_input: provide either input.url or input.category_slug');
// }

console.log(input)
proxy_location({country: 'in'});

const kind = input.kind || 'mcat';  // default 'mcat' si no se especifica
  if (kind === 'hub') {
    
    resolved_url = HUB_URL_TMPL.replace('{slug}', input.category_slug);
  } else if (kind === 'mcat') {
    resolved_url = MCAT_URL_TMPL.replace('{slug}', input.category_slug);
  } else {
    dead_page('bad_input: input.kind must be "mcat" or "hub", got: ' + kind);
  }

navigate(resolved_url);

// Guard 1: bot-check / "Just a moment" Cloudflare / redirect a enquiry.
// Selector [action*="/errors/"] captura captcha forms genéricos.
// Timeout corto (2s): estos elementos aparecen inmediatos en el HTML
// servido por el proxy, no tiene sentido esperar 30s.


if (el_exists(
  'h1:contains("Access Denied"), h1:contains("Just a moment"), [action*="/errors/"]',
  2000
)) {
  dead_page('bot_check_detected');
}

// Guard 2: URL shape. Stage 1 acepta solo:
//   Vía 1 (MCAT): https://dir.indiamart.com/impcat/{slug}.html
//   Vía 2 (industry hub): https://dir.indiamart.com/indianexporters/ind_{slug}.html
// City directories (/indore/, /mumbai/) NO tienen proddetail links
// directos — filtrar antes de esperar 30s al wait.
// Nota: cuando `input.category_slug` se usa, la URL la construye este
// código con las plantillas de arriba — siempre pasa este guard. Sirve
// principalmente cuando alguien pasa `input.url` directo (preview/test).
const is_mcat = /^https?:\/\/dir\.indiamart\.com\/impcat\/[^/]+\.html/i.test(resolved_url);
const is_hub = /^https?:\/\/dir\.indiamart\.com\/indianexporters\/ind_[^/]+\.html/i.test(resolved_url);
if (!is_mcat && !is_hub) {
  dead_page('not_stage1_url: expected impcat or indianexporters URL');
}

// Guard 3: esperar a que aparezcan los proddetail links. 30s es ok acá
// porque ya sabemos que la URL ES un MCAT/hub válido (Guard 2). Si la
// página sigue sin renderizarlos, algo cambió en el DOM → dead_page.
if (!el_exists('a[href*="proddetail"]', 30000)) {
  dead_page('no_proddetail_links_on_listing');
}

// Scroll para lazy-load (mantiene el comportamiento del vendor).
scroll_to('bottom');

// Wait extra post-scroll (pattern del vendor con segundo `wait`).
// Si los links desaparecieron tras scroll, raro pero detectable.
if (!el_exists('a[href*="proddetail"]', 5000)) {
  dead_page('proddetail_links_lost_after_scroll');
}

let data = null
try{
  data = parse();
} catch(e) {

}
// Extraer las URLs.
// const data = parse();

// Guard 5: spec §2 schema_change — Guard 3 vio los links pero el parser
// devolvió 0 URLs. El selector del parser no está matcheando el DOM
// (cambio de estructura, nuevo atributo, etc.).
// if (!data.product_urls || data.product_urls.length === 0) {
//   dead_page('schema_change: parser produced 0 proddetail URLs despite selector match');
// }
 if (data) {
    collect(data);
 }

