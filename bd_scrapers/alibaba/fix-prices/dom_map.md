# Alibaba — DOM map de URLs con precio NULL (análisis completo)

> **Fecha análisis:** 2026-05-05  
> **Referencia:** [alibaba_nulls_2026-05-05.md](../../../docs/specs/scrapers/alibaba_nulls_2026-05-05.md)  
> **Parser en producción:** `parser_code_v4.js`  
> **URLs analizadas:** 105 (93 Grupo 1 + 12 Grupo 2) — TODAS visitadas via BrightData

---

## Resumen ejecutivo

Análisis sistemático de las 105 URLs con precio NULL. Se visitó cada URL via `mcp__brightdata__scrape_batch` y se extrajo el texto de precio visible + el patrón del enlace de proveedor.

| Causa | Descripción | URLs afectadas |
|-------|-------------|----------------|
| **C1** | Container selector gap — v4 no alcanza el bloque "Product descriptions from the supplier" | **~105/105** (causa universal) |
| **C2** | Monedas faltantes en CURRENCY_RE | Subconjunto: SEK, TL/TRY, DKK, RSD, 円-kanji |
| **C3** | Formato `número SÍMBOLO/CÓDIGO` no soportado — CURRENCY_RE asume `SÍMBOLO número` | Subconjunto: €-europeo, 円, SEK, TL, DKK, RSD |
| **C4** | Caracteres de control RTL (UI hebrea) — precio `‏1,262.14 ‏€` con `‏` invisibles | ≥1 URL |
| **C5** | Formato lakh indio — `₹87,439.50-1,55,448` (coma en posición no estándar) | ≥1 URL |

**Causa dominante:** C1. Todas las URLs muestran el precio en la sección "Product descriptions from the supplier" / "供应商的产品说明", cuyo contenedor no es alcanzado por el selector actual de v4.

**Causa secundaria más frecuente:** C2+C3 combinados para monedas no-estándar (SEK, TL, DKK, RSD, 円). Estas URLs fallarían incluso si C1 se resuelve, porque el regex no matchea esas monedas.

---

## Causa raíz C1 — Container selector gap (afecta ~105/105 URLs)

### El problema

El selector de contenedores en el fallback tiered-price y customizable-MOQ:
```js
$('section, div[class*="description"], div[class*="detail"], [class*="supplier-desc"]')
```
**no matchea** el contenedor real del bloque "Product descriptions from the supplier" / "供应商的产品说明" en ninguno de los 105 casos analizados.

El precio existe en el DOM (se ve con `scrape_as_markdown`) pero vive dentro de un `div` cuya clase no contiene ninguna de las palabras clave del selector actual.

### Evidencia

Todos los URLs analizados muestran el precio en el texto del body bajo el encabezado:
- `## Product descriptions from the supplier` (UI inglesa/europea)
- `## 供应商的产品说明` (UI china)
- `## Tedarikçinin ürün açıklamaları` (UI turca)
- `## תיאורי המוצרים מהספק` (UI hebrea)

El bloque es consistente cross-UI. El selector v4 no lo alcanza en ningún mercado/idioma.

### Fix propuesto (v5) — F1

Añadir `$('body').text_sane()` como último recurso en el fallback de extracción de precio:

```js
// Último recurso: escanear el body completo
if (!price_raw) {
    const bodyText = $('body').text_sane() || '';
    const bodyMatches = bodyText.match(CURRENCY_RE);
    if (bodyMatches && bodyMatches.length > 0) {
        price_raw = bodyMatches[0];
    }
}
```

---

## Causa raíz C2 — Monedas faltantes en CURRENCY_RE

### CURRENCY_RE actual
```js
/(NZ\$|CA\$|A\$|US\$|R\$|B\/\.|RM|Rp|[€£¥₹₩฿$])\s*[\d.,]+/g
```

### Monedas no-estándar encontradas en las 105 URLs

| Moneda | Código ISO | Ejemplos encontrados | Formato | ¿En CURRENCY_RE? |
|--------|-----------|---------------------|---------|-----------------|
| Corona sueca | SEK | `SEK 106.30`, `1,423.55 SEK`, `28,470.86 SEK`, `SEK 759,222.72` | Prefijo Y sufijo | ❌ NO |
| Lira turca | TL/TRY | `117.78 TL`, `1,177.72 TL`, `141.325,72 TL/Ton` | Sufijo (coma decimal europea) | ❌ NO |
| Corona danesa | DKK | `DKK 5.08-5.54`, `DKK 3,905.52` | Prefijo | ❌ NO |
| Dinar serbio | RSD | `RSD 276.44` | Prefijo | ❌ NO |
| Yen kanji | 円 | `794-1,112円`, `88-97円`, `63,513円` | Sufijo | ❌ NO (¥ sí está, 円 no) |
| Rupia india | INR | `₹87,439.50`, `₹87,439.50-1,55,448` | Prefijo | ✅ SÍ (₹ en charset) |
| Euro (formato EU) | EUR | `228,60 €`, `‏1,262.14 ‏€` | Sufijo (+ RTL chars) | Símbolo sí, posición no |
| GBP | £ | `£0.0075`, `£51.91`, `£238.98-283.79` | Prefijo | ✅ SÍ |
| USD | $ / US$ | `$80.00`, `US$8,500`, `US$5-10` | Prefijo | ✅ SÍ |
| EUR | € | `€86.43`, `€259.28` | Prefijo | ✅ SÍ |

### Fix propuesto (v5) — F2 + F3

```js
// CURRENCY_RE ampliado: soporta prefijo Y sufijo, añade SEK/TL/DKK/RSD/円
const CURRENCY_RE = new RegExp(
    // Formato SÍMBOLO/CÓDIGO + número (prefijo)
    '(NZ\\$|CA\\$|A\\$|US\\$|R\\$|B/\\.|RM|Rp|SEK|DKK|RSD|[€£¥₹₩฿$])\\s*[\\d.,]+' +
    '|' +
    // Formato número + SÍMBOLO/CÓDIGO (sufijo)
    '[\\d.,]+\\s*(TL|TRY|SEK|DKK|RSD|CHF|NOK|円)',
    'gi'
);
```

---

## Causa raíz C4 — Caracteres de control RTL (UI hebrea)

### El problema

La UI en hebreo de Alibaba inserta caracteres de control RTL (U+200F, `‏`) invisibles dentro del texto de precio:
```
‏1,262.14 ‏€
```
El regex `[\d.,]+` matchea el número, pero el carácter `‏` antes del `€` hace que el patrón `número\s*€` no matchee porque `‏` no es `\s`.

### Fix propuesto (v5) — F4

```js
// Limpiar caracteres de control Unicode antes de aplicar CURRENCY_RE
const cleanText = rawText.replace(/[‏‎‪-‮﻿]/g, '');
```

---

## Causa raíz C5 — Formato lakh indio

### El problema

El sistema de numeración indio usa comas en posiciones no estándar:
```
₹87,439.50-1,55,448
```
`1,55,448` = 155,448 (lakh format). El regex `[\d.,]+` matchea `87,439.50` correctamente, pero si se intenta parsear `1,55,448` como número puede fallar.

### Fix propuesto (v5) — F5

Al extraer el valor numérico, normalizar el formato lakh antes de `parseFloat`:
```js
// Normalizar lakh: remover comas en posición no-estándar
function parsePriceValue(str) {
    // Si tiene 2+ grupos de coma con distinto espaciado → lakh indio
    return parseFloat(str.replace(/,/g, ''));
}
```

---

## Patrones de supplier — todos cubiertos por v4

| Patrón DOM | Selector v4 que lo captura | Ejemplos |
|-----------|---------------------------|---------|
| `<alias>.en.alibaba.com/<locale>/index.html` | `a[href*=".en.alibaba.com"]` | `jslydjx.en.alibaba.com`, `swaychemical.en.alibaba.com` |
| `<alias>.en.alibaba.com/index.html` | `a[href*=".en.alibaba.com"]` | `solidpack.en.alibaba.com`, `enochem.en.alibaba.com` |
| `<id>.trustpass.alibaba.com/index.html` | `a[href*="alibaba.com"][href*="/index"]` | `de39190602229pkhc.trustpass.alibaba.com`, `th19018039541xnal.trustpass.alibaba.com` |

**Conclusión:** El proveedor NO es la causa de los NULLs en Grupo 1. Los 93 URLs de Grupo 1 tienen precio NULL + proveedor NULL. Si C1 se resuelve (body text fallback), el supplier también debería extraerse porque su `<a>` es alcanzado por los selectores existentes. Los NULLs de supplier en Grupo 1 son un síntoma de que el parser no llegó a la etapa de extracción por C1.

---

## UIs / idiomas encontrados

| Idioma UI | Ejemplos de precio | URLs encontradas |
|-----------|-------------------|-----------------|
| Inglés | `£7.47`, `US$8,500`, `$80.00` | Mayoría |
| Chino (简体中文) | `US$5`, `£51.91` | Frecuente |
| Turco (Türkçe) | `141.325,72 TL/Ton` (coma decimal) | ≥3 URLs |
| Hebreo (עברית) | `‏1,262.14 ‏€` (RTL chars) | ≥1 URL |
| Sueco/Escandinavo | `SEK 106.30` | ≥5 URLs |
| Danés | `DKK 5.08` | ≥2 URLs |
| Serbio | `RSD 276.44` | ≥1 URL |
| Japonés | `794-1,112円` | ≥3 URLs |

---

## Resumen de fixes para parser_code_v5.js

| Fix | Causa | Cambio | Prioridad | Impacto estimado |
|-----|-------|--------|-----------|-----------------|
| **F1** | C1 | Añadir `$('body').text_sane()` como último recurso en extracción de precio | **Crítica** | ~105/105 URLs |
| **F2** | C2 | Añadir `SEK`, `DKK`, `RSD`, `TL`/`TRY`, `円` a CURRENCY_RE | **Alta** | Subconjunto con monedas no-estándar |
| **F3** | C3 | Soportar formato `número CÓDIGO` (sufijo) en CURRENCY_RE | **Alta** | Monedas que Alibaba muestra como sufijo |
| **F4** | C4 | Strip de chars RTL Unicode antes de aplicar regex | **Media** | UI hebrea |
| **F5** | C5 | Normalizar formato lakh indio al parsear valores numéricos | **Baja** | ≥1 URL con INR en lakh |

---

## Archivos relacionados

- Parser actual: `bd_scrapers/alibaba/sc_code/parser_code_v4.js`
- Reporte nulos: `docs/specs/scrapers/alibaba_nulls_2026-05-05.md`
- Spec scraper: `docs/specs/scrapers/alibaba.md`
