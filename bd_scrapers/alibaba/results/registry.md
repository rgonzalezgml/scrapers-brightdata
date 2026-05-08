# alibaba — registry de versiones

| Versión | Archivo | Estado | Fixes / Notas |
|---------|---------|--------|---------------|
| v1 | sc_code/parser_code_v1.js | producción | Baseline: cascada de selectores spec §4 (templates fixed-price + customizable-MOQ), extractPrice con EXCHANGE_RATES, 10 keys Fase 1 vendor-compatibles |
| v2 | sc_code/parser_code_v2.js | producción | Iteración sobre v1 (ver cabecera del archivo) |
| v3 | sc_code/parser_code_v3.js | producción (activo hasta deploy v4) | Iteración sobre v2 (ver cabecera del archivo) |
| v4 | sc_code/parser_code_v4.js | pendiente de run | Fix E1: tercer fallback tiered-price + fallback adicional supplier_name |
| detail_v1 | sc_browser/interaction_code_detail_v1.js | pendiente de run | Stage 2 interaction code: wait h1 + captcha check + wait dinámico (precio/supplier) con try/catch + scroll_to bottom + parse(); mitiga causa raíz de E1 en Browser worker |
| v5 | sc_code/parser_code_v5.js | producción | Fixes C1–C5: strip RTL, body fallback P6, CURRENCY_RE ampliada (SEK/DKK/RSD/円/TL), lakh indio en parseNumber, regresión cascada P2–P6 (ver cabecera) |
| v6 | sc_code/parser_code_v6.js | producción | Fix C7: ladder-price split-decimal spans (Tailwind id-text-[28px]); ver cabecera |
| v7 | sc_code/parser_code_v7.js | producción (activo hasta deploy v8) | Fix R-v6: refactor cascada P1–P6 independientes; ver cabecera |
| v8 | sc_code/parser_code_v8.js | producción (run 08-09) | Fix E2: P0 JSON-LD al inicio de cascada + FB4/FB5/FB6 fallbacks supplier + flags rfc_only_page/hydration_timeout. Run 08: 784 filas, null 27.4% (vs 41.0% en v7, −13.6pp). Run 09: 373 filas (26.9%) crashearon por bug JSON-LD array top-level → TypeError. |
| v9 | sc_code/parser_code_v9.js | pendiente de deploy | Fix JSON-LD array top-level (causa 373 crashes en run 09); price_raw siempre DOM o "[jsonld: ...]" como marcador; ladder no bloqueado por P0; scanJsonLd() como fallback P7. |
