# alibaba.com — spec
https://www.alibaba.com/trade/search?SearchText=industrial+chemicals&has4Tab=true
Proveedor: Alibaba Group
Categoría: Precios
Función: Precios globales de químicos industriales y empaque

## databrightdata

### 1.
Scraper alibaba.com (Precios B2B). Químicos + empaque. Fuente principal Precios. Entidad: `product` (fila por SKU). Señales: rango USD, MOQ, supplier country/verified, categoría (Alkali/Acid/Solvent/Surfactant/Preservative/Fragrance/Packaging_*). Shape alineado con MIC/IndiaMART. Render SPA. NO reviews/chat/RFQ.

### 2.
```json
{"product":["product_name_clean","product_name_original","type","category","price_raw","price_min_usd","price_max_usd","price_unit","price_normalized_per_kg","moq_quantity","moq_unit","supplier_name","supplier_country","supplier_verified","product_url","scraped_date"]}
```

### 3.
- `alibaba.com/trade/search?SearchText={term}&has4Tab=true` listing (pag. `?page=N`)
- `alibaba.com/product-detail/{slug}_{PID}.html` detail
- BrightData DCA: `POST api.brightdata.com/dca/trigger?collector={ID}&queue_next=1`, `GET api.brightdata.com/dca/dataset?id={snap}&format=json`
- País proxy default `CN`

## genomma lab

### 1.
Scraper de alibaba.com para area de Precios B2B global. Proposito: extraer precios de quimicos industriales y materiales de empaque publicados por proveedores B2B como fuente principal del area de Precios (competitive benchmarking). Cada registro representa un producto listado (SKU comercial de un proveedor) con precio normalizado a USD, MOQ, metadatos del proveedor y trazabilidad al URL original. NO es un scraper de I+D: ignoramos reviews en texto libre, chat con supplier, formularios RFQ, galeria completa de imagenes, catalogos de video, disponibilidad en tiempo real, variantes. Buscamos senales comparables producto-a-producto: nombre limpio del SKU quimico, rango de precio con moneda y unidad, MOQ con unidad, supplier con pais ISO-2 y nivel de verificacion (Gold Supplier / Verified), categoria (taxonomia de 10 enums: Alkali, Acid, Solvent, Surfactant, Preservative, Fragrance, Packaging_Drum, Packaging_Bag, Packaging_Container, Other), reputacion opcional (rating, reviews_count, response_rate). Output plano JSON: una fila por producto, sin nested objects; alineado con made-in-china e indiamart para comparacion cross-source sin mapeos. Campo site fijo alibaba. Los detalles por area vienen en los puntos siguientes.

### 2.
Infraestructura y motor. Alibaba.com es SPA: las tarjetas .fy23-search-card y los campos de detail se pintan tras ejecutar JavaScript; proxy HTTP plano sin render NO devuelve el DOM util. Motor principal: BrightData Data Collector (DCA), un scraper pre-construido disparado por HTTP API que usa Scraping Browser internamente y encapsula rotacion de IP, CAPTCHA solve y render JS. Endpoint trigger POST https://api.brightdata.com/dca/trigger?collector={COLLECTOR_ID}&queue_next=1 con header Authorization: Bearer {API_KEY}. Endpoint dataset GET https://api.brightdata.com/dca/dataset?id={snapshot_id}&format={json|csv|ndjson}. Polling del connector: intervalos poll_seconds=10 default, timeout total timeout_minutes=15; HTTP 202 = procesando, 200 con payload JSON = listo. Pais proxy configurable via country() (collector) y supplier_country (payload), default CN. Variables de entorno: BRIGHTDATA_API_KEY, BRIGHTDATA_COLLECTOR_ID, BRIGHTDATA_APIcore, BRIGHTDATA_TRIGGER_URL, BRIGHTDATA_DATASET_URL, ALIBABA_DEFAULT_MAX_PAGES, ALIBABA_DEFAULT_COUNTRY, ALIBABA_DEFAULT_MIN_PRICE, ALIBABA_DEFAULT_MAX_PRICE. Retry policy: pendiente de implementar (backoff exponencial 2s/4s/8s para trigger ante 429/5xx). CAPTCHA / bot-check: un h1 puede existir en pantalla de bot-check y pasar wait() silenciosamente; validar h1 no trivial + al menos un selector de precio antes de collect(). Alerta SCHEMA_CHANGE si product_urls.length=0 en busqueda que historicamente devuelve resultados.

### 3.
Fuentes y URLs canonicas. URL base canonica de busqueda: https://www.alibaba.com/trade/search?SearchText=industrial+chemicals&has4Tab=true. URL template parametrizada: https://www.alibaba.com/trade/search?SearchText={term}&has4Tab=true. Paginacion: query param ?page=N con default max_pages=5 (Stage 1 JS) y max_pages=3 (connector Python). Ficha detail: https://www.alibaba.com/product-detail/{slug}_{PID}.html donde PID es el id numerico del producto. Busquedas por defecto del Stage 1 listing (5 search terms especializadas para ampliar cobertura): industrial chemicals (tipo=quimico, hint=Quimicos Industriales); industrial packaging drums barrels (tipo=empaque, hint=Tambores y Barriles); sodium hydroxide industrial (tipo=quimico, hint=Alcalis/Soda Caustica); hydrochloric acid industrial (tipo=quimico, hint=Acidos Inorganicos); chemical packaging containers (tipo=empaque, hint=Contenedores Quimicos). Payload del trigger a DCA: array con un objeto {url, search_keyword, max_pages, supplier_country (default CN), min_price (default 1), max_price (default 10000)}. Login NO requerido. Frecuencia esperada: on-demand / semanal (no cron declarado; lo dispara el connector Python manualmente).

### 4.
Entidad product campos base (16). Una fila por producto listado. Todos los campos siempre presentes con null explicito cuando falten; nunca omitir clave. product_name_clean string max 80 chars normalizado tras clean_name (ver punto 7); product_name_original string titulo crudo del h1.title-first-column con fallbacks .product-title h1, h1[class*="title"], h1; type enum {chemical, packaging} derivado de clean_name en classify(); category enum {Alkali, Acid, Solvent, Surfactant, Preservative, Fragrance, Packaging_Drum, Packaging_Bag, Packaging_Container, Other} derivado en classify() (ver punto 9); price_raw string crudo del DOM .price-range con fallbacks .do-price, .price-original, [class*="price"] (ej "$1.20-$2.50/kg"); price_min_usd y price_max_usd float convertidos a USD via EXCHANGE_RATES; price_unit enum {kg, ton, L, piece, mt, set, null}; price_normalized_per_kg float o null (ver punto 8 regla 13); moq_quantity int desde .min-order-amount con fallbacks [class*="moq"], [class*="min-order"], .order-num; moq_unit enum {kg, ton, piece, ...}; supplier_name string desde .company-name a con fallbacks .supplier-name a, [class*="company-name"]; supplier_country string ISO-2 desde .supplier-country con fallbacks [class*="country"], .country-flag + span; supplier_verified bool desde badge "Gold Supplier" / "Verified" (selector pendiente); product_url string URL completa del path /product-detail/{slug}_{id}.html; scraped_date string YYYY-MM-DD del runtime. Cardinalidad / invariantes: product_url y product_name_original son invariantes del sitio (cada pagina /product-detail/* tiene canonical link y h1); si faltan el parser fallo y debe emitir error, no null; en el Output Schema de Fase 2 van non-nullable. Los demas 14 campos son nullable — null indica ausencia legitima (ej. price_raw null = RFQ-gated / precio oculto tras login; supplier_verified null = badge no presente en el DOM; category null = keyword no matcheo ninguna familia y fallback Other no aplica).

### 5.
Entidad product campos de reputacion (3 adicionales, prompt v2). Opcionales con null si ausentes; nunca omitir clave. supplier_rating float 0-5 un decimal desde selector de estrellas en el DOM del supplier card (selector pendiente); supplier_reviews_count int conteo total de reviews del supplier (selector pendiente); supplier_response_rate string formato "98%" (selector pendiente). Nota estructural: output plano, sin nested objects (requisito prompt v2 §1). Ausencias siempre null explicito. Listas que no aplican van como [] nunca null.

### 6.
Filtros de skip. No emitir fila cuando: sin nombre (product_name_clean queda vacio tras clean_name y no hay fallback desde name_from_url por URL); sin precio (price_raw es null, vacio, "None", "[]", o "null"); maquinaria / equipo (normalize(name) contiene alguno de MACHINERY_KW = [machine, equipment, pump, motor, meter, sensor, device, tool, instrument, apparatus, system, maquina, equipo, bomba, herramienta, maschine, gerat, anlage]); titulo solo en chino (si el titulo no contiene caracteres ASCII/Latinos; regla del prompt v2 §6, pendiente de implementar). name_from_url fallback: si raw_name viene vacio, extraer de product_url con regex /product-detail/([^_]+)_ (fallback /product-detail/(.+?)[\?_]) y reemplazar - por espacio.

### 7.
Limpieza de nombre (clean_name sobre product_name_original). Remover case-insensitive los patrones REMOVE_PATTERNS: marketing EN/ES/DE (high quality, best price, hot sale, factory direct, free sample, top quality, oem, odm, customized, wholesale, bulk, best selling, professional, direktvertrieb, vom hersteller, meistverkaufter, fabrik, qualit, zertifiziert, reinheit, calidad, certificado, fabricante, proveedor, directo, mejor precio, venta directa); certificaciones (iso[0-9]+, ce, gmp, fda, reach, rohs, kosher, halal con sufijos certified/approved/standard opcionales); roles (manufacturer, factory, supplier, exporter, producer); ciudades CN (jiahua, shandong, hebei, guangzhou, shanghai, beijing). Eliminar parentesis largos \([^)]{20,}\) → vacio. Colapsar separadores | / \ & → espacio; \s{2,} → un espacio. Truncar a 80 chars cortando en el ultimo espacio anterior (no parte palabra). Si queda vacio fallback a raw y flag name_clean_fallback.

### 8.
Parsing de precio (parse_price sobre price_raw). Detectar moneda en orden: primero CURRENCY_SYMBOLS literales (NZ$, CA$, A$, US$, R$, B/., RM, Rp, €, £, ¥, ₹, ₩, ฿) por matching; si no encuentra, buscar codigo ISO (USD, CNY, ...) en uppercase. Convertir a USD usando EXCHANGE_RATES (tabla fija en codigo; refresh pendiente). Extraer unidad matcheando /kg, /ton, /mt, /l, /piece, /set en lowercase. Si no hay numeros en el string → (null, null, currency, unit). Regla 13 normalizacion per-kg: si price_unit es kg entonces price_normalized_per_kg = price_min_usd; si ton o mt dividir price_min_usd por 1000; L, piece, set → null. Regla para rangos "$1.20-$2.50/kg": extraer ambos numeros, min=price_min, max=price_max; si solo hay 1 numero max=min.

### 9.
Clasificacion (classify sobre clean_name). Tipo packaging si el nombre contiene drum, barrel, container, bag, bottle, tank, ibc, packaging, package, sack → type="packaging" + category entre Packaging_Drum (drum/barrel), Packaging_Bag (bag/sack), Packaging_Container (container/ibc/tank/bottle). Si no es packaging, iterar keywords y asignar type="chemical" + primera category que matchee: Alkali (sodium hydroxide, caustic soda, potassium hydroxide, naoh, koh); Acid (hydrochloric, sulfuric, nitric, acetic, acid, hcl, h2so4, citric); Surfactant (sles, sls, laureth, lauryl, surfactant, detergent); Solvent (ethanol, methanol, acetone, isopropanol, ipa, solvent); Preservative (sodium benzoate, potassium sorbate, preservative, benzoate); Fragrance (fragrance, perfume, aroma, essential oil); Glycol (glycerin, glycerol, propylene glycol, peg); Silicate (silicate, silica, silicon); Polymer (polycarboxylate, polypropylene, polymer, resin); Corrosion (corrosion inhibitor, rust inhibitor, anti-corrosion); Bleach (chlorine, hypochlorite, bleach); Fertilizer (npk, ammonium, urea, fertilizer, nitrate, phosphate). Si ninguna matchea → type="chemical", category="Other".

### 10.
Output, limites y flags. Formato final: JSON array plano, un objeto por producto, sin nested (requisito prompt v2 §1); representacion de ausencias null explicito (nunca omitir clave, requisito §OUTPUT FORMAT); listas vacias nunca null. Tipos: json default, csv, ndjson soportados por el connector. Destino local convencion proyecto: data/alibaba/alibaba_{YYYY-MM-DD}.json relativo a la raiz del repo; override opcional via env var ALIBABA_OUTPUT_DIR. Encoding UTF-8, ensure_ascii=false, indent=2. Limites: default max_pages=5 (Stage 1 JS) o 3 (connector Python); 5 busquedas por defecto. Dedupe por product_url + scraped_date (pendiente de implementar). Cache no declarada. Hard caps: pendientes de definir. Flags permitidos: name_clean_fallback (clean_name vacio), rating_invalid (rate fuera de [0,5]), price_fx_needed (moneda no USD sin rate en tabla), price_unit_unknown (unidad no mapeable), schema_change (product_urls.length=0 en busqueda historica), captcha_detected, rate_limit_blocked. Destino remoto (Snowflake/S3/DB) no declarado; pendiente de decidir para consumo por area de Precios.

### 11.
Shape canonico (ejemplo fixture). Un producto tipico emitido cumple:

```json
{
  "product_name_clean": "Glycerin Industrial Grade Liquid",
  "product_name_original": "High Quality Glycerin 99.5% Industrial Grade Liquid Factory Direct CAS 56-81-5 ...",
  "type": "chemical",
  "category": "Glycol",
  "price_raw": "$1.20-$2.50/kg",
  "price_min_usd": 1.20,
  "price_max_usd": 2.50,
  "price_unit": "kg",
  "price_normalized_per_kg": 1.20,
  "moq_quantity": 500,
  "moq_unit": "kg",
  "supplier_name": "Shandong Example Chem Co., Ltd.",
  "supplier_country": "CN",
  "supplier_verified": true,
  "product_url": "https://www.alibaba.com/product-detail/Glycerin-99-5_123456.html",
  "scraped_date": "2026-04-21",
  "supplier_rating": 4.8,
  "supplier_reviews_count": 132,
  "supplier_response_rate": "98%"
}
```

URL busqueda canonica con los 5 search terms default: https://www.alibaba.com/trade/search?SearchText=industrial+chemicals&has4Tab=true. URL detail ejemplo: https://www.alibaba.com/product-detail/Glycerin-99-5_123456.html. Trigger DCA: POST https://api.brightdata.com/dca/trigger?collector={ID}&queue_next=1 con Authorization Bearer. Dataset: GET https://api.brightdata.com/dca/dataset?id={snapshot_id}&format=json.

### 12.
Fases de implementacion y Output Schema versioning. El scraper convive con un Output Schema configurado en el dashboard de BrightData Scraper Studio que historicamente quedo anclado al vendor (10 keys con nombres vendor), no a la spec §2 (16 keys con nombres canonicos). Romper esa forma unilateralmente desde el parser dispara HTTP 422 output_schema_incompatible en el trigger DCA. Por eso el trabajo se parte en dos fases.

Fase 1 (actual, parser_code_v1.js). El parser emite exactamente las 10 keys vendor-compatibles con nombres vendor literales: cleaned_product_name, product_url, supplier_name, price_raw, price_min_usd, price_max_usd, price_unit, minimum_order_quantity, cas_number, purity. Incluye dos fixes reales sobre la baseline vendor: selectores para los dos templates de detail page (fixed-price vs customizable) y conversion de monedas EUR/JPY con formato EU. Cero migracion de schema en el dashboard. Los 6 campos diferidos para Fase 2 son: product_name_original, type, category, price_normalized_per_kg, moq_quantity/moq_unit (split del string minimum_order_quantity), supplier_country, supplier_verified, scraped_date; la spec §2 los declara como target canonico pero Fase 1 no los emite.

Fase 2 (diferida, tarea coordinada). Parser v2 emite las 16 keys spec §2 con nombres canonicos. Requiere mover los 4 frentes juntos en un mismo release: (a) spec §2 (ya esta OK, es el target), (b) Output Schema del dashboard BrightData — agregar los 6 campos nuevos, renombrar cleaned_product_name→product_name_clean y minimum_order_quantity→moq_quantity, partir el string MOQ en moq_quantity/moq_unit, marcar product_url y product_name_original non-nullable (ver punto 4 cardinalidad), (c) parser_code_v2.js, (d) retirar la tabla de aliases vendor→spec §2 del middleware. Se levanta como brief aparte cuando se decida invertir el tiempo; no es bloqueante para consumidores de Fase 1.

Compatibilidad downstream. middlewares/alibaba/models.py:208-221 tiene una tabla de aliases vendor→spec §2 que remapea las 10 keys Fase 1 a la shape spec §2 y rellena los 6 campos diferidos con null explicito. Consecuencia: consumidores del middleware reciben siempre la shape spec §2 (§4 sigue siendo el target canonico para downstream), independiente de si el backend esta en Fase 1 o Fase 2. El salto Fase 1→Fase 2 es transparente para el consumidor siempre que el paso (d) — retirar aliases — se haga en el mismo release que (b) y (c).
