// interaction_code_v2 — Alibaba detail page (Code worker).
//
// Cambios vs v1:
//   v1 era trivial: `navigate(input.url); collect(parse());`. El skip de
//   rows inválidos (missing_name, missing_price, machinery, non_ascii_title)
//   se hacía dentro del parser emitiendo `scraper_flags: skipped_*` en el
//   return, porque Scraper Studio rechaza `parse()` que devuelva null
//   ("Output can't be empty"). Eso contaminaba `data[]` con rows null-heavy.
//
//   v2 adopta el patrón idiomático observado 2026-04-23:
//     - `el_exists(sel, timeoutMs)` → boolean, NO tira excepción si no aparece
//       (contrast con `wait(sel)` que rompe el run).
//     - `dead_page(reason)` → marca la URL como dead con razón; el row no
//       entra a `data[]` y downstream solo consume rows reales.
//   Ref: memoria del proyecto `reference_brightdata_dsl_helpers.md`.
//
// Flow:
//   1. navigate(input.url)
//   2. Guard bot-check (timeout corto 2s).
//   3. Guard URL shape (regex product-detail).
//   4. parse() → data Fase 1 (10 keys vendor-literales, ver parser_code_v2).
//   5. Guard invariantes: product_url + cleaned_product_name no pueden ser null.
//   6. collect(data).
//
// NOTA: parser_code_v2 depende de este interaction. NO usar parser_code_v2
//   con el interaction_code_v1 trivial, ni parser_code_v1 con este
//   interaction (las skip rules viven en v1, los guards viven acá).

navigate(input.url);

// Guard 1: bot-check / error page. Selectores observados:
//   - "Access Denied" (Alibaba error page genérica).
//   - "Just a moment" (Cloudflare interstitial).
//   - action="/errors/validateCaptcha" (captcha form; selector heredado del
//     vendor sc_browser/interaction_code.js, útil como fallback robusto).
// Timeout corto (2s): si estos elementos van a aparecer, ya están en el HTML
// inicial servido por el proxy; no tiene sentido esperar 30s.
if (el_exists(
  'h1:contains("Access Denied"), h1:contains("Just a moment"), [action="/errors/validateCaptcha"]',
  2000
)) {
  dead_page('bot_check_detected');
}

// Guard 2: URL shape. Alibaba product URLs válidas son
// `/product-detail/{slug}_{PID}.html`. Catch URLs no-producto (listings,
// supplier homes, landing) sin gastar un parse() completo.
if (!input.url.match(/\/product-detail\/.+_\d+\.html/)) {
  dead_page('not_a_product_url');
}

// Extracción — parser_code_v2 emite 10 keys vendor-literales (Fase 1).
const data = parse();

// Guard 3: invariantes spec §4 (cardinalidad). Si el parser no pudo
// extraer product_url o cleaned_product_name, la página cargó pero el HTML
// no es el esperado (template rota, A/B variant nueva, o skip legítimo como
// missing_name). Mejor marcar dead que emitir row degenerado.
if (!data.product_url || !data.cleaned_product_name) {
  dead_page('missing_invariants: product_url or cleaned_product_name');
}

collect(data);
