# olive_young_new_arrivals — spec
https://global.oliveyoung.com/display/page/new-arrivals
Proveedor: CJ Group
Categoría: I+D
Función: Nuevos lanzamientos K-beauty, innovación de producto

## databrightdata

### 1.
Scraper Olive Young Global new-arrivals (I+D K-beauty). Entidad: `new_arrival`. Señales: lanzamientos recientes organizados por corner/colección, price, soldOut, flags newYn/bestYn/flashYn, brand. Fuente: `global.oliveyoung.com/display/page/new-arrivals` + API `new-arrivals-data`. NO rankings, reviews, ni precios históricos.

### 2.
```json
{"new_arrival":["prdt_no","product_url","product_name_en","product_name_kr","brand_no","brand_name_en","brand_name_kr","sale_amt","nrml_amt","image_url","is_soldout","is_new","is_best","is_flash","has_coupon","has_gift","promo_name","corner_name","scraped_date"]}
```

### 3.
- `global.oliveyoung.com/display/page/new-arrivals` (Vue SPA)
- API relativa `new-arrivals-data?acesCntryCode=00&langCode=en&dispPageTypeCode=40&mrgnCntry={code}`
- `global.oliveyoung.com/product/detail?prdtNo={GA...}`
- `global.oliveyoung.com/sitemapindex-product.xml`
- AVOID `/order`, `/cart`, `/myaccount`, `/delivery`, `oliveyoung.co.kr`

## genomma lab

### 1.
Propósito: capturar los productos de nueva llegada en Olive Young Global para detectar innovaciones K-beauty en el momento de su lanzamiento. Este scraper es complementario al scraper `olive-young` de rankings: donde aquel captura popularidad acumulada (bestsellers), este captura novedad reciente. Los productos aparecen en la página `/display/page/new-arrivals` organizados por corners (colecciones temáticas o de temporada) que rotan periódicamente. Señales relevantes para I+D: nombre de producto (EN + KR), marca, precio de venta vs. precio normal (descuento de lanzamiento), flags `newYn`/`bestYn`/`flashYn`, disponibilidad (soldOut), y el nombre del corner que agrupa el producto. La fuente canónica es el API interno `new-arrivals-data` que responde un JSON con `cornerList` conteniendo `setContsMap` con arreglos `PRODUCT[]`.

### 2.
Infraestructura. La URL `/display/page/new-arrivals` es una Vue 2 SPA servida por `global.oliveyoung.com`. El HTML del shell carga en menos de 300 KB, pero los productos solo se inyectan tras `axios.get('new-arrivals-data', {...})` — el endpoint es relativo y se resuelve como `https://global.oliveyoung.com/display/page/new-arrivals/new-arrivals-data?...`. Requiere Scraping Browser con JS habilitado para ejecutar el Vue component. Cloudflare bot-challenge silente vía iframe cdn-cgi (igual que el scraper de rankings). Proxy: residencial US o UK, delay 3–5 s. robots.txt de `global.oliveyoung.com`: permite `/display` y `/product`; Crawl-delay 5 para `*`; Disallow `/order`, `/claim`, `/myaccount`, `/aws`, `/cart`, `/product/review-report`, `/delivery`, `/capi/send-event`. ClaudeBot no listado. NUNCA scrapear `oliveyoung.co.kr` (retorna 403). Señal de bloqueo: body < 50 KB o `title` contiene "Just a moment".

### 3.
URLs canónicas.

Página principal new arrivals (SPA shell):
```
https://global.oliveyoung.com/display/page/new-arrivals
```

API de datos (GET, relativa — resolver contra la URL del SPA):
```
new-arrivals-data?acesCntryCode=00&langCode=en&dispPageTypeCode=40&mrgnCntry={mrgnCntryCode}
```
`mrgnCntryCode` es una variable JS inicializada en el shell — valor observado: `10` (Korea). El endpoint resuelto es:
```
https://global.oliveyoung.com/display/page/new-arrivals/new-arrivals-data?acesCntryCode=00&langCode=en&dispPageTypeCode=40&mrgnCntry=10
```

Detalle de producto (Vue + CSRF):
```
https://global.oliveyoung.com/product/detail?prdtNo={GA...}
```

Sitemap:
```
https://global.oliveyoung.com/sitemapindex-product.xml
```

Fixture de producto real observado 2026-05-03:
```
https://global.oliveyoung.com/product/detail?prdtNo=GA260338924
```

### 4.
Entidad `new_arrival`. Una fila por producto distinto dentro de los corners retornados por el API. El JSON de respuesta tiene la estructura:

```
response.data.cornerList[N].setContsMap.PRODUCT[M]
```

Campos disponibles en cada producto del API:
- `prdtNo` (string) — ID único del producto, formato `GA\d{9,12}`
- `korPrdtName` (string) — nombre en coreano
- `prdtName` (string) — nombre en inglés (puede estar vacío si no hay traducción)
- `brandNo` (string) — ID de la marca
- `brandName` (string) — nombre de la marca en inglés
- `korBrandName` (string) — nombre de la marca en coreano
- `saleAmt` (string numérico) — precio de venta en KRW
- `nrmlAmt` (string numérico) — precio normal en KRW
- `imagePath` (string) — ruta relativa de imagen; URL completa = `https://cdn-image.oliveyoung.com/{imagePath}`
- `soldOutYn` (string "Y"/"N") — disponibilidad
- `newYn` (string "Y"/"N") — badge "New"
- `bestYn` (string "Y"/"N") — badge "Best"
- `flashYn` (string "Y"/"N") — badge "Flash"
- `cpnYn` (string "Y"/"N") — tiene cupón
- `giftYn` (string "Y"/"N") — tiene regalo
- `offrSpNm` (string) — nombre de promoción especial (puede ser vacío)
- `prmtnNm` (string) — nombre de promoción/cupón

El corner que contiene el producto proviene de:
```
response.data.cornerList[N].setContsMap.SET_NAME[0].contsCont
```

Mapeo de campos del API a los campos del schema §2:

| Campo schema | Fuente API |
|---|---|
| `prdt_no` | `prdtNo` |
| `product_url` | `"https://global.oliveyoung.com/product/detail?prdtNo=" + prdtNo` |
| `product_name_en` | `prdtName` (fallback: vacío) |
| `product_name_kr` | `korPrdtName` |
| `brand_no` | `brandNo` |
| `brand_name_en` | `brandName` |
| `brand_name_kr` | `korBrandName` |
| `sale_amt` | `Number(saleAmt)` |
| `nrml_amt` | `Number(nrmlAmt)` |
| `image_url` | `"https://cdn-image.oliveyoung.com/" + imagePath` |
| `is_soldout` | `soldOutYn === "Y"` |
| `is_new` | `newYn === "Y"` |
| `is_best` | `bestYn === "Y"` |
| `is_flash` | `flashYn === "Y"` |
| `has_coupon` | `cpnYn === "Y"` |
| `has_gift` | `giftYn === "Y"` |
| `promo_name` | `offrSpNm || prmtnNm || null` |
| `corner_name` | `cornerList[N].setContsMap.SET_NAME[0].contsCont` |
| `scraped_date` | fecha ISO YYYY-MM-DD del run |

### 5.
Estructura de corners. El API devuelve `cornerList` como un array de corners (colecciones temáticas). Cada corner tiene:
- `setContsMap.SET_NAME[0].contsCont` — título del corner (ej. "New K-Beauty Essentials", "Trending Now")
- `setContsMap.TEXT[0].contsCont` — descripción del corner (opcional)
- `setContsMap.PRODUCT[]` — lista de productos del corner

Un producto puede aparecer en múltiples corners. Deduplicar por `prdt_no` para la entidad final, pero registrar `corner_name` del primer corner donde aparece (o el de mayor prioridad si se puede determinar). El total de productos únicos observado oscila entre 50 y 200 según la rotación semanal.

### 6.
Skip rules. No emitir fila cuando:
- `prdtNo` está vacío o no matchea `^GA\d{9,12}$`.
- La URL apunta a `oliveyoung.co.kr` — emitir flag `source_gone` y descartar sin request.
- Body < 50 KB o título contiene "Just a moment" — emitir flag `cloudflare_challenge` y rotar sesión.
- El API devuelve array `cornerList` vacío — registrar como error `api_empty_response`.
- `korPrdtName` está vacío (producto sin nombre mínimo).

### 7.
Reglas de parsing y normalización.
- `product_name_en`: si `prdtName` está vacío, usar `null` y flag `product_name_en_missing`.
- `product_name_kr`: colapsar whitespace, max 200 chars.
- `sale_amt` y `nrml_amt`: parsear como `Number()`, null si no numérico.
- `image_url`: solo construir si `imagePath` no está vacío. Si empieza con `http`, usar tal cual.
- `corner_name`: limpiar whitespace y tags HTML remanentes con DOMParser. Max 100 chars.
- `promo_name`: preferir `offrSpNm` sobre `prmtnNm`; si ambos vacíos → `null`.
- `scraped_date`: `new Date().toISOString().slice(0, 10)` (YYYY-MM-DD).

### 8.
Límites y flags.
- Hard cap: 500 productos por corrida (el new-arrivals típicamente tiene < 200).
- Wall time máximo: 30 minutos.
- No hay paginación — el API devuelve todos los productos en una llamada.
- No es necesario crawl de páginas de detalle para el scope mínimo v1.

Flags permitidos:
- `cloudflare_challenge` — Cloudflare challenge detectado.
- `source_gone` — URL apunta a `oliveyoung.co.kr`.
- `api_empty_response` — `cornerList` vacío.
- `product_name_en_missing` — `prdtName` vacío.
- `image_url_missing` — `imagePath` vacío.
- `sold_out` — `soldOutYn === "Y"`.
- `api_parse_error` — error al parsear la respuesta JSON del API.

### 9.
Output y naming.
- Archivo de salida: `oliveyoung_newarrivals_{YYYYMMDD}.json` — array de `new_arrival`.
- Tabla destino: `SRC_OLIVEYOUNG_NEWARRIVALS`.
- Encoding: UTF-8.
- `scraped_date` como string YYYY-MM-DD.
- `sale_amt` y `nrml_amt` como números enteros (KRW, sin decimales).
- `prdt_no` como string, `brand_no` como string.

### 10.
Fixtures reales observados 2026-05-03.

Producto ejemplo visible en el shell HTML (antes de hidratación Vue):
- `prdtNo`: `GA260338924`
- `product_url`: `https://global.oliveyoung.com/product/detail?prdtNo=GA260338924`
- `image_url` raw: `https://cdn-image.oliveyoung.com/display/1056/ff868a66-94fa-4846-94a2-8de2af5dd5d0.jpg?RS=315x420&SF=webp&QT=80`

Categorías de navegación disponibles en el GNB (referencia para contexto de productos):
- Skincare (`ctgrNo=1000000008`), Makeup (`ctgrNo=1000000031`), Bath & Body (`ctgrNo=1000000052`), Hair (`ctgrNo=1000000070`), Face Masks (`ctgrNo=1000000003`), Suncare (`ctgrNo=1000000011`), K-Pop (`ctgrNo=1000000162`)

Nota: los corners del new-arrivals son distintos a las categorías del navegador — son editoriales y rotan semanalmente.

### 11.
Relación con scraper `olive-young`. El scraper existente captura rankings de popularidad (bestsellers por categoría, señal de demanda acumulada). Este scraper captura novedad de oferta (productos recién agregados al catálogo global, señal de innovación). Complementarios: el mismo `prdtNo` puede aparecer en rankings semanas después de entrar a new-arrivals. La clave de join cross-scraper es `prdt_no` = `prdt_no` del spec `olive-young`.
