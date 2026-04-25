# impi — vendor (v0)

**Vacío intencional.** IMPI fue bootstrapeado directamente a v1 sin pasar por
DB AI, a partir de un blueprint funcional provisto por un compañero (script
XHR que corre en la consola del browser).

Si a futuro DB AI genera un andamiaje v0 para este scraper, ubicar los
archivos acá (`vendor/sc_browser/interaction_code.js`,
`vendor/sc_browser/parser_code.js`, `vendor/sc_code/*`) y mantener
`sc_browser/` y `sc_code/` en root como la versión autoritativa. El vendor es
READ-ONLY una vez colocado.
