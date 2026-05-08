# alibaba — DOM map

Última actualización: 2026-05-05. Fuente: análisis de URLs reales + diagnóstico E1.

---

## Templates de detail page identificados

Alibaba.com muestra tres variantes de la página `/product-detail/` según el tipo de producto y la configuración del proveedor. Los tres comparten la misma URL canónica y el mismo h1; lo que difiere es el bloque de precio y MOQ.

---

### Template 1 — fixed-price

Productos con precio escalonado por cantidad (tiers predefinidos). Es el template más común y el que cubre el vendor baseline.

**Señal de detección**: presencia de `.price-item` en el DOM.

| Campo | Selector / estrategia |
|-------|-----------------------|
| Precio por tier (texto) | `.price-item .id-text-2xl span` |
| Rango construido | Primer `.price-item` (precio alto) → último (precio bajo); se construye `"last-first"` si difieren |
| MOQ (texto) | `.price-item:first .id-text-sm` |
| Nombre producto | `.product-title-container h1` → `h1.title-first-column` → `.product-title h1` → `h1[class*="title"]` → `h1` |
| Supplier name | `[data-testid="seller-overview-card-company-link"]` → `.company-name a` → `.supplier-name a` → `[class*="company-name"] a` → `[class*="company-name"]` |
| Supplier país | `.supplier-country` → `[class*="country"]` → `.country-flag + span` |
| CAS number | `[data-testid="module-attribute-row"]` con label `/cas\s*no\.?/i` → tabla `<tr><td>` genérica → `<dt>/<dd>` |
| Purity | Igual que CAS con label `/\bpurity\b/i` o `/assay/i` |

---

### Template 2 — customizable-MOQ

Productos con precio RFQ o con un único precio publicado junto a una línea "Minimum order quantity". Aparece en productos etiquetados como "Customizable".

**Señal de detección**: `.price-item` ausente + texto "Minimum order quantity" presente en el bloque de descripción del supplier.

| Campo | Selector / estrategia |
|-------|-----------------------|
| Precio | Regex en texto libre del bloque `section, div[class*="description"], div[class*="detail"], [class*="supplier-desc"]`: patrón `minimum\s+order\s+quantity[:\s]+([^\n]+?)\s*...(moneda+numero)` |
| MOQ (texto) | Captura `m[1]` del mismo regex (el segmento antes del precio) |
| Fallback laxo | Si bloque tiene "Customizable" + "Minimum order quantity": regex independientes para MOQ y precio en el bloque completo |
| Supplier name | Misma cascada que Template 1; fallback extra: `a[href*=".en.alibaba.com"]` |

---

### Template 3 — tiered-price (nuevo ~2026-05-03)

Productos customizable donde el bloque del supplier muestra rangos de cantidad por separado (sin la etiqueta "Minimum order quantity"). Ejemplo real:

```
1,000 - 4,999 kilograms
US$1.70

>= 5,000 kilograms
US$1.63
```

**Señal de detección**: `.price-item` ausente + no hay "Minimum order quantity" en el bloque de descripción.

**URL de referencia que falla en v3**: `https://www.alibaba.com/product-detail/Professional-Water-Treatment-Chemicals-Ultra-high_1601457834481.html?s=p`

| Campo | Selector / estrategia |
|-------|-----------------------|
| Precio | Regex global `/(NZ\$|CA\$|A\$|US\$|R\$|B\/\.|RM|Rp|[€£¥₹₩฿$])\s*[\d.,]+/g` sobre el texto del bloque descripción; se recopilan todos los valores, se construye `"min-max"` (menor primero) |
| MOQ (texto) | Regex `/([\d,]+)\s*(?:-\s*[\d,]+)?\s*(kilogram|kg|ton|piece|unit|liter|litre)/i` sobre el texto del bloque anterior al primer precio |
| Supplier name | Cascada Template 1 + `a[href*=".en.alibaba.com"]` + `a[href*="alibaba.com"][href*="/index"]` (nuevo fallback E1) |
| Flag emitido | `tiered_price_fallback` en `flags[]` cuando este path se activa |

---

## Notas de portabilidad

- `.toArray().map(fn)` es el patrón usado en `sc_code/` (Code worker / cheerio completo). No usar en `sc_browser/` (ver SKILL R12).
- `text_sane()` en lugar de `.text().trim()` en todos los accesos de texto (SKILL R11).
- `CURRENCY_RE` usa `lastIndex = 0` antes de cada llamada a `exec()` en el loop porque el flag `g` mantiene estado en el objeto RegExp.
