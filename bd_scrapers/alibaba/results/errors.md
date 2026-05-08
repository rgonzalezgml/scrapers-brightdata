# alibaba — error catalog

## E1 — Template tiered-price: price_raw y supplier_name null (~34% de filas)

**Versión afectada**: sc_code/parser_code_v3.js  
**Detectado**: ~2026-05-03  
**Síntoma**: 132/387 filas en PRD_STG.GNM.SRC_ALIBABA_PROV_HIST con `price_raw IS NULL` y `supplier_name IS NULL` simultáneamente.  
**Causa**: Alibaba desplegó un tercer template de detail page ("tiered-price") para productos customizable. En este template:
- No existe `.price-item` (descarta la rama fixed-price).
- No aparece la cadena "Minimum order quantity" (descarta ambos fallbacks customizable-MOQ del v3).
- En cambio el bloque del supplier muestra rangos de cantidad → precio en texto libre, ej.:
  ```
  1,000 - 4,999 kilograms
  US$1.70

  >= 5,000 kilograms
  US$1.63
  ```
- El link del supplier puede no tener el formato `*.en.alibaba.com` esperado por el fallback existente (correlación perfecta supplier-null ↔ price-null confirma que ambos fallan juntos).

**Fix**: Implementado en sc_code/parser_code_v4.js:
1. Tercer fallback de precio: escanear bloque descripción con regex `/(NZ\$|CA\$|A\$|US\$|R\$|B\/\.|RM|Rp|[€£¥₹₩฿$])\s*[\d.,]+/g`, capturar todos los precios, construir rango `"<min>-<max>"`. MOQ extraído del primer threshold de cantidad con unidad antes del primer precio.
2. Fallback adicional de supplier: `a[href*="alibaba.com"][href*="/index"]` como último recurso tras `a[href*=".en.alibaba.com"]`.

---

## E2 — price_raw y supplier_name null en 41% de filas post-v7 (JSON-LD no cubierto)

**Versión afectada**: sc_code/parser_code_v7.js  
**Detectado**: 2026-05-07 (run 07-alibaba_20260507_195655.json)  
**Síntoma**: 180/439 filas (41%) con `price_raw IS NULL` y `supplier_name IS NULL` simultáneamente. Las filas null solo tienen `cleaned_product_name`, `product_url`, `input`, `status_code`. Correlación perfecta: si price es null, supplier también es null.  
**Causa**: Las 6 estrategias P1–P6 del parser v7 fallan en estas páginas porque el componente de precio React no hidrata dentro del timeout del Code worker. Sin embargo, Alibaba inyecta `<script type="application/ld+json">` en el HTML inicial (pre-hidratación) con el nodo `Product/offers` que contiene `lowPrice`/`highPrice`/`price` + `priceCurrency`. Este JSON-LD tampoco expone el nombre del supplier directamente, pero los campos `brand.name`, `seller.name` y `manufacturer.name` pueden estar presentes. Los 3 fallbacks de supplier de v7 también fallan porque apuntan a nodos del DOM dinámico (data-testid, hrefs de empresa).  
**Fix**: Implementado en sc_code/parser_code_v8.js:
1. **P0 JSON-LD** (nueva estrategia al inicio de la cascada): parsear todos los `<script type="application/ld+json">`, soportar `@graph` array y objeto directo, extraer `offers.lowPrice`/`offers.highPrice`/`offers.price` + `priceCurrency`. Construye `"CUR{low}-CUR{high}"`. Flag `price_source_P0_jsonld`.
2. **FB4** (supplier JSON-LD): escanear mismos scripts buscando `brand.name`, `seller.name`, `manufacturer.name`. Flag `supplier_source_jsonld`.
3. **FB5** (supplier og:site_name): leer `meta[property="og:site_name"]` filtrando valores que contengan "alibaba". Flag `supplier_source_og`.
4. **FB6** (supplier data-testid broad net): selectores `[data-testid*="seller"]`, `[data-testid*="company-name"]`, `[data-testid*="supplier-name"]` excluyendo el ya cubierto en la cascada primaria.
5. **Nuevo flag diagnóstico**: si `price_raw` sigue null tras todas las estrategias, emitir `rfc_only_page` (si `supplier_name` se encontró, precio es RFQ/oculto) o `hydration_timeout` (ambos null, React no hidró).
