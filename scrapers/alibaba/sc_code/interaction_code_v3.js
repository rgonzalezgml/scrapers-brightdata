// interaction_code_v1 — Alibaba detail page (Code worker).
//
// Mínimo: cargar la URL y pasar el HTML al parser. Es idéntico al vendor.
// Scraper Studio requiere ambos archivos (interaction + parser), así que
// mantenemos el interaction trivial y toda la lógica vive en parser_code_v1.
navigate(input.url);
collect(parse());
