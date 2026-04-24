# indiamart — errors y gotchas del sitio

Log vivo de problemas **específicos de indiamart.com** encontrados durante runs. Errores del runtime de BrightData van en `/workspace/docs/specs/brightdata-errors.md`.

---

## E1 — `ClaudeBot` y `Scrapy` Disallowed en robots.txt

**Síntoma**: si el scraper se anuncia con UA `ClaudeBot`, `Scrapy`, `AhrefsBot`, `Bytespider`, `Baiduspider`, `Yandex`, etc., el sitio puede devolver 403 o página mínima.

**Causa**: `www.indiamart.com/robots.txt` y `dir.indiamart.com/robots.txt` tienen `Disallow: /` para una lista larga de bots conocidos.

**Fix**: usar User-Agent Chrome genérico. OAI-SearchBot y GPTBot están explícitamente allowed, pero el safe default es Chrome.

---

## E2 — Content-Encoding gzip obligatorio

**Síntoma**: primer lectura de body devuelve binario ilegible.

**Causa**: el sitio sirve gzip por default. Sin decompression del cliente, el HTML es binario.

**Fix**: en cliente HTTP garantizar `Accept-Encoding: gzip, deflate` y decodificar. En curl: `--compressed`. En sc_code de BrightData esto debería ser transparente, confirmar en primer run.

---

## E3 — Paginación `?page=N` NO existe en impcat

**Síntoma**: vieja suposición de que `impcat/{slug}.html?page=2` funciona; en realidad retorna la página 1 o 404.

**Causa**: IndiaMART no usa pagination numérica en impcat. El listing muestra top N productos y resto se descubre por subcats + supplier drill-down + sitemaps XML.

**Fix**: usar sitemaps en `dir.indiamart.com/*-sitemap*.xml` para discovery masivo, subcats hijas (ej `caustic-soda-pearl.html`) para ampliar cobertura.

---

## E4 — `offers.price` viene sin rango

**Síntoma**: JSON-LD emite `offers.price = "50"` (string numerico único) en productos con precio rango.

**Causa**: IndiaMART mete solo el precio "from" en structured data; el rango completo (`"₹50-120/kg"`) solo vive en el `<title>` del detail.

**Fix**: leer `<title>` para rango + unidad. Parsear `\₹\s*[\d,.]+(?:-[\d,.]+)?\s*/\s*[A-Za-z]+` del title. Si hay rango, extraer min y max; si no, max=min.

---

## E5 — MOQ dual-sourced (spec table HTML + embedded JSON)

**Síntoma**: a veces la spec table del detail no tiene la fila `Minimum Order Quantity`, pero un objeto JSON inline sí trae `PC_ITEM_MOQ_UNIT_TYPE`.

**Causa**: IndiaMART renderiza algunos productos sin tabla de specs, dejando solo el objeto JSON embebido con campos `FK_IM_SPEC_MASTER_DESC` y `PC_ITEM_*`.

**Fix**: parser prueba en orden: (1) spec table HTML con selector `<tr><td>Minimum Order Quantity</td>...`, (2) fallback a regex sobre HTML crudo buscando `"PC_ITEM_MOQ_UNIT_TYPE":"([^"]+)"` y `"PC_ITEM_MIN_ORDER_QUANTITY":"([^"]+)"`. Implementado en parser v3.

---

## E6 — Selectores DOM obsoletos del vendor v1 (v2→v3 refactor)

**Versión afectada**: parser_code_v2 (= vendor v1 + hotfix supplier_slug). **Fix**: parser_code_v3 (2026-04-23).

**Síntoma**: 9 bugs simultáneos en el parser vendor → fila emitida con `type="Bulb Type"` artefacto, `category_path=null`, `supplier_city=""`, `supplier_state=undefined.split`, `supplier_country=undefined`, `business_type=""`, `member_since_year=""`, `verified=true` (laxo), `trustseal="Mobile E-Mail"`.

**Causa**: el vendor v1 fue sintetizado para una vertical de iluminación (bulbs) y selectores `.company-details-grid dt/dd` + `.addrs.plhn` + `.verT.fs13` split coma **ya no existen** en el DOM actual de IndiaMART. Adicional: `$('script[type="application/ld+json"]').html()` sin `.each()` devuelve solo el primer bloque (BreadcrumbList) y nunca lee el bloque Product.

**Fix** (aplicado en parser_code_v3): (a) iterar los 3 bloques JSON-LD con `.toArray().map(...)` y filtrar por `@type`; (b) derivar `type` del BreadcrumbList position=2 `.@id` regex `ind_chem`/`ind_packaging`; (c) `supplier_city` desde title con regex `\bin\s+(...)\s*\|`; (d) `supplier_state=null` + flag `supplier_state_from_home_needed` (NO extraible del detail SSR, se resuelve en Stage 3); (e) `supplier_country="IN"` fijo; (f) `business_type`/`member_since_year` desde `li.compdtsItems` con `p.fs12.color1` + `h4.cmpfvalh4`; (g) `verified`/`trustseal` como bool literal sobre HTML raw (`/Verified Exporter/i.test(raw_html)`, `/TrustSEAL Verified/i.test(raw_html)`). Handoff completo en `/workspace/docs/fase3/indiamart-parser-v3-handoff.md` §3.

---

## Patrón de contribución

Cada run fallido → `E{N+1}` con: síntoma, causa, fix. Si el error es del runtime (no del sitio), va en `docs/specs/brightdata-errors.md`.
