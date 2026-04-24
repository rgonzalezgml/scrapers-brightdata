// impi — sc_code/parser_code_v1.js
//
// El flujo de IMPI usa solamente requests JSON (endpoints internal/record y
// internal/result). interaction_code_v1.js emite todos los collect() con los
// datos normalizados del schema §2; NO llama a parse(). Este parser_code
// queda presente por convención del módulo (BrightData Scraper Studio espera
// el archivo, aunque no se ejecute).
//
// Si una iteración futura decide ejercer parse() sobre la página HTML
// (p.ej. para scraping del grid legacy en /marcas/search/quick cuando los
// endpoints JSON estén bloqueados), este archivo es el punto de extensión.

return {};
