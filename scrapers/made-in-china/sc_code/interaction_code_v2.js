// interaction_code_v2.js — Code worker made-in-china
// Iteración v2. Diff vs v1:
// - v1 era `navigate(input.url); collect(parse());` — sin guards, sin branching,
//   sin dead_page para casos que el parser decide skipear.
// - v2 mantiene la navegación simple (R8: navigate top-level) pero agrega:
//   * Status check 404/410 → dead_page (spec §8 skip rule).
//   * `parse()` sin args (R9). El parser infiere entidad product o supplier vía
//     URL y retorna un objeto con __entity marker.
//   * Si el parser retorna null (skip condicionado) → dead_page.
//   * `collect(data)` se llama sin filtrar por entidad — downstream separa por
//     `__entity` del record (single-record collect por URL, spec §2 contrato).
//
// NO toca sc_browser. Preserva toda la cadena E9-E12 del Browser worker.

navigate(input.url);

if (status_code() === 404 || status_code() === 410) {
  dead_page('http_' + status_code());
}

const data = parse();

if (!data || data.__skip === true) {
  dead_page('parser_skip');
}

collect(data);
