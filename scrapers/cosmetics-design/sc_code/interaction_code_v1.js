// cosmetics-design — sc_code/interaction_code_v1.js
// Bootstrap desde vendor + cierre de gaps:
// - SKIP por HTTP 404/410 (spec §8 skip rules) via dead_page.
// - Parser (parser_code_v1.js) lee input.supplier con default "William Reed"
//   y emite el contrato §2/§4 completo.
//
// Nota: sc_code es HTTP puro — no hay close_popup ni wait; el consent wall,
// si aparece, se deja pasar y el parser flaggea consent_wall_retried.

navigate(input.url);

// SKIP rule §8: HTTP 404 / 410 → no emitir fila.
const status = status_code();
if (status === 404 || status === 410) {
    dead_page('article_removed_' + status);
}

collect(parse());
