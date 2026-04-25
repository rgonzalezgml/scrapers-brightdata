# olive-young — registry de versiones

| Versión | Worker | Archivo interaction | Archivo parser | Estado | Notas |
|---------|--------|---------------------|----------------|--------|-------|
| v1 | sc_browser | interaction_code_v1.js | parser_code_v1.js | arquitectura incorrecta | Stage 1 Browser listing → Stage 2 Code detail. Detail es Vue+CSRF, sc_code no puede renderizarlo. E7. |
| v1 | sc_code | interaction_code_v1.js | parser_code_v1.js | arquitectura incorrecta | sc_code intentaba navegar product detail Vue (E6, E7). |
| v2 | sc_code | interaction_code_v2.js | parser_code_v2.js | pendiente de run | Stage 1 correcto: Rankings API JSON → collect ranking rows → next_stage para enrichment (2+ rankings, máx 10). |
| v2 | sc_browser | interaction_code_v2.js | parser_code_v2.js | pendiente de run | Stage 2 correcto: product detail Vue+CSRF con JS render. Guards: .co.kr skip, Cloudflare iframe, Vue timeout 15s. |
| v3 | sc_code | interaction_code_v3.js | parser_code_v3.js | bloqueado (E8) | Stage 1 Rankings API → bloqueada por microservicio. Región corregida USA→US vs v2. |
| v4 | sc_browser | interaction_code_v4.js | parser_code_v4.js | pendiente de run | Stage 1 migrado a HTML listing best-seller (Browser worker, Cloudflare bypass nativo). Stage 2 igual a v2. Arregla E8. |
