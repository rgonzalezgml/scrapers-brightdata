// interaction_code_v3.js — Code worker made-in-china
// Iteración v3. Diff vs v2:
// - Eliminada la guard `data.__skip === true` → `dead_page('parser_skip')`: el parser v3
//   ya no emite ese marker (ni `__entity`). El branching product vs supplier del parser
//   devuelve directamente el shape §2 de la entidad correspondiente, sin marker.
// - Conservado: navigate top-level (R8), parse() sin args (R9), status check 404/410 →
//   dead_page (spec §8 skip rule), collect(data) single-record por URL.
// - Guard `!data` preservado como cortafuego: si el parser alguna vez devuelve null
//   (ej. cambio futuro de skip condicionado), dead_page en vez de collect(null).
//
// NO toca sc_browser. Preserva toda la cadena E9-E12 del Browser worker.

navigate(input.url);

if (status_code() === 404 || status_code() === 410) {
  dead_page('http_' + status_code());
}

const data = parse();

if (!data) {
  dead_page('parser_skip');
}

collect(data);
