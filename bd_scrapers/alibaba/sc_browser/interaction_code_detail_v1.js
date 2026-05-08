// Stage 2 — Detail page interaction code (Browser worker)
// Versión: detail_v1
//
// Propósito:
//   Navega cada URL de producto recibida desde Stage 1 (via next_stage({ url })) y
//   espera a que los bloques de precio y supplier terminen de hidratarse antes de
//   llamar parse(). Sin este código, BrightData parseaba el HTML antes de que React
//   inyectara los componentes dinámicos, produciendo ~34% de filas con price_raw y
//   supplier_name = null (ver errors.md E1).
//
// Fix aplicado:
//   - wait() post-navigate para h1 (HTML inicial, siempre presente).
//   - wait() dentro de try/catch para los selectores de precio/supplier: si los
//     componentes no aparecen en el timeout indicado, el parser corre de todas formas
//     con sus fallbacks de body-text (parser_code_v* en sc_code/).
//   - scroll_to('bottom') entre los dos wait() dinámicos para activar lazy-loading
//     de bloques below-the-fold.
//   - captcha check tras el primer wait() estable.
//
// Relación con errors.md:
//   Mitiga la causa raíz de E1 (parse antes de hidratación) en el Browser worker.
//   El fix de parser (fallback tiered-price + supplier) sigue en sc_code/parser_code_v4.js.

// ── 1. Navegar a la URL del producto ──────────────────────────────────────────
navigate(input.url);

// ── 2. Esperar el H1 — confirma que el HTML inicial cargó ────────────────────
//    Timeout 30 s (default). Si falla aquí, la página está rota o bloqueada.
wait('h1', { timeout: 30000 });

// ── 3. Captcha check ─────────────────────────────────────────────────────────
if (el_exists('[action="/errors/validateCaptcha"]')) {
    blocked('Captcha detected on detail page');
}

// ── 4. Esperar componentes dinámicos (precio / supplier) — intento 1 ─────────
//    Si el selector no aparece en 20 s, continuar igual; parse() usará fallbacks.
const DYNAMIC_SELECTOR =
    '.price-item, [data-testid="range-price"], [data-testid="seller-overview-card-company-link"]';

try {
    wait(DYNAMIC_SELECTOR, { timeout: 20000 });
} catch (_) {
    // Los componentes no se renderizaron aún; scroll puede desencadenar lazy-load.
}

// ── 5. Scroll para activar lazy-loading below-the-fold ───────────────────────
scroll_to('bottom');

// ── 6. Esperar componentes dinámicos — intento 2 (post-scroll) ───────────────
//    Tiempo reducido: si el scroll no desbloqueó la hidratación en 8 s, ya no lo hará.
try {
    wait(DYNAMIC_SELECTOR, { timeout: 8000 });
} catch (_) {
    // El parser correrá con lo que haya en el DOM; sus fallbacks de texto cubren este caso.
}

// ── 7. Parsear ────────────────────────────────────────────────────────────────
parse();

// Dashboard BrightData — dónde subir este archivo:
// | Stage | Slot              | Archivo                          |
// | 2     | Interaction code  | interaction_code_detail_v1.js    |
