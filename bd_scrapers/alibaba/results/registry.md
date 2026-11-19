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
| v9 | sc_code/parser_code_v9.js | producción (activo) | Fix JSON-LD array top-level (causa 373 crashes en run 09); price_raw siempre DOM o "[jsonld: ...]" como marcador; ladder no bloqueado por P0; scanJsonLd() como fallback P7. |
| v10 | sc_code/parser_code_v10.js | pendiente de deploy | Tasas de cambio dinámicas: usa input.exchange_rates (fetched por interaction_code_v7 desde Frankfurter/BCE). Flag exchange_rates_live. Fallback al snapshot hardcodeado si fetch falló. |
| interaction_v7 | sc_browser/interaction_code_v7.js | producción (activo) | Fetch live FX rates desde Frankfurter al inicio del run (página 1). Propaga exchange_rates a rerun_stage() y next_stage(). Fallback silencioso si la API no responde. Fix bug: sin search_keyword, URL sin SearchText → página sin cards; ahora siempre usa fallback 'citric acid'. |
| interaction_code_v3 | sc_code/interaction_code_v3.js | producción (activo) | Fix DOMContentLoaded timeout (run 10: 341/509 registros solo cleaned_product_name+product_url). Usa navigate({wait_until:'navigate'}) + el_exists(h1,30s) + el_exists(DYNAMIC_SELECTOR,20s) antes de parse(). |
| interaction_code_v4 | sc_code/interaction_code_v4.js | pendiente de deploy | Fix tabla de precios escalonados (run 12: 14 sparse sin precio). Agrega scroll_to('bottom') + segunda el_exists(8s) post-scroll para dar tiempo al componente React de precios de hidratarse. |
| v11 | sc_code/parser_code_v11.js | pendiente de deploy | Fix P6 ventana: extiende 2000 chars antes del header de sección (precios antes de "Product descriptions") y usa full-body cuando no hay anchor (locale chino, páginas sin sección). |
