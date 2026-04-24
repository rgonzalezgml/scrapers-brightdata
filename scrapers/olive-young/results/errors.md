# olive-young — errors y gotchas del sitio

Log vivo de problemas **específicos de olive-young** encontrados durante runs. Errores del runtime de BrightData van en `/workspace/docs/specs/brightdata-errors.md`.

---

## E1 — `oliveyoung.co.kr` devuelve 403 anti-bot

**Síntoma**: request a `oliveyoung.co.kr` retorna 403 con página estática `잠시만 기다려 주세요`.

**Causa**: el dominio `.co.kr` tiene anti-bot agresivo, fuera del alcance del scraper. El dominio productivo del scraper es `global.oliveyoung.com` + microservicio `product-ranking-service.oliveyoung.com`.

**Fix**: si un seed apunta a `.co.kr`, emitir flag `source_gone` y descartar sin request.

---

## E2 — Cloudflare challenge silente via iframe

**Síntoma**: body contiene "Just a moment" antes del primer `<script>` legítimo, o iframe `cdn-cgi/challenge-platform`.

**Causa**: `global.oliveyoung.com` usa Cloudflare con bot-challenge silente.

**Fix**: flag `cloudflare_challenge` y rotar session. Usar Scraping Browser con sesión residencial US/UK y JS render activo.

---

## E3 — `region=Global` o `language-code=ko` devuelven 400/array vacío

**Síntoma**: API `/v1/pages/ranking/sales/products?region=Global` retorna error 400 o `data: []`.

**Causa**: solo `region=KR` y `region=USA` son válidos. `language-code` debe ser `en` (no `ko`).

**Fix**: hardcodear `language-code=en`, `margin-country-code=10`, `delivery-country-code=10`. Iterar solo sobre `[KR, USA]`.

---

## E4 — `/brands/{brand_no}/` sin `?nt=1` — NO aplica (eso es cosme)

**Nota**: la regla `nt=1` es de cosme.net, no de olive-young. Eliminar si se copia-pegó por error del patrón. Olive Young usa `/display/page/brand-page?brandNo={no}` directo.

---

## E5 — `prdt_no` no matchea `^GA\d{8,12}$` → skip

**Síntoma**: algunos productos en el listing tienen IDs que no respetan el patrón `GA` + 8-12 dígitos.

**Causa**: productos legacy o tests con formato distinto.

**Fix**: skip sin emitir, dejar el registro fuera del output.

---

## E6 — Enriquecimiento detail requiere Vue + CSRF

**Síntoma**: POST directo a `/detail-data` del detail sin headers CSRF rebota 403.

**Causa**: la página usa Vue y dispara POST a `detail-data` con CSRF token matching tras render.

**Fix**: usar Scraping Browser (no sc_code HTTP puro) para product detail; navegar completo para que Vue ejecute el POST con CSRF.

---

## E7 — Arquitectura de stages invertida en v1

**Versión afectada**: sc_browser/interaction_code_v1.js + sc_browser/parser_code_v1.js + sc_code/interaction_code_v1.js + sc_code/parser_code_v1.js

**Síntoma**: sc_browser Stage 1 navegaba el listing best-seller HTML y disparaba `next_stage({url})`; sc_code Stage 2 intentaba `navigate(product_url)` para parsear detail. La página de detalle es Vue + Cloudflare: sin JS render la respuesta no contiene datos del producto (solo el shell HTML vacío), resultando en campos null masivos o errores 403 CSRF.

**Causa**: el worker equivocado ejecuta cada tarea. El Rankings API (`product-ranking-service.oliveyoung.com`) devuelve JSON puro sin JS — ideal para Code worker. Los product detail pages (`global.oliveyoung.com/product/detail?prdtNo=…`) requieren Vue render + CSRF — solo Browser worker puede resolverlos (E6).

**Fix**: invertir la arquitectura. Stage 1 = sc_code consume la Rankings API JSON. Stage 2 = sc_browser navega product detail con JS render. Implementado en v2.

---

## E8 — Rankings API (`product-ranking-service.oliveyoung.com`) bloquea requests

**Versión afectada**: sc_code/interaction_code_v3.js + sc_code/parser_code_v3.js

**Síntoma**: requests a `product-ranking-service.oliveyoung.com` retornan 403 o son silenciosamente descartados, incluso con headers correctos. Los campos `ranking_id`, `prdt_no`, etc. quedan vacíos o la corrida no produce rows.

**Causa**: el microservicio comenzó a bloquear requests directos sin sesión Cloudflare válida, posiblemente requiriendo cookies de sesión del dominio principal o headers de fingerprint que el Code worker no puede replicar sin browser.

**Fix**: migrar Stage 1 al Browser worker navegando el HTML listing de best-seller (`https://global.oliveyoung.com/display/page/best-seller`), que el Browser worker resuelve con Cloudflare bypass nativo. Extraer rankings desde el DOM inline (sin API). Implementado en sc_browser/interaction_code_v4.js.

---

## Patrón de contribución

Cada run fallido → `E{N+1}` con: síntoma, causa, fix. Si el error es del runtime (no del sitio), va en `docs/specs/brightdata-errors.md`.
