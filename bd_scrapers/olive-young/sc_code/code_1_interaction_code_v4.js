// interaction_code_v4.js — sc_code (Code worker)
// v4: Rankings API bloqueada (E8). sc_code ya no colecta nada.
// Solo lanza sc_browser (Browser worker) sobre el listing HTML.
// Toda la extracción y el enrichment ocurren en sc_browser/interaction_code_v4.js.

next_stage({ url: 'https://global.oliveyoung.com/display/page/best-seller' });
