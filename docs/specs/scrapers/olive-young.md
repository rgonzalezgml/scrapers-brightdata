# olive-young — spec
https://global.oliveyoung.com/
Proveedor: CJ Group
Categoría: I+D
Función: Tendencias K-beauty Korea, bestsellers

> URL original del catálogo (xlsx) era un redirect de Google Ads (`google.com/aclk?...`) + params de influencer/feature-flags. No es entrada funcional: se sustituye por el dominio directo.

## databrightdata

### 1.
Scraper Olive Young global (I+D K-beauty). Rankings KR + USA. Entidades: `ranking`, `product`, `brand`. Señales: bestsellers por cat. (11 KR + 12 USA), rating 0-5, claim_tags (Vegan/Clean), `is_soldout`, flags `new/best/flashYn`. Fuente: `global.oliveyoung.com` + API `product-ranking-service.oliveyoung.com`. `.co.kr`=403 out-of-scope. NO precios/reviews.

### 2.
```json
{"ranking":["ranking_id","region","cat_id","rank","prdt_no","name_en","brand_no","rate","is_soldout","promo","scraped_date"],"product":["prdt_no","url","name_clean_en","name_clean_kr","brand_no","category_ids","ranks","best_regions","review_count","claim_tags"],"brand":["brand_no","name_en","url","total_in_rankings","avg_rank"]}
```

### 3.
- API `product-ranking-service.oliveyoung.com/v1/pages/ranking/sales/{categories,products}` (region=KR|USA)
- `global.oliveyoung.com/product/detail?prdtNo={GA...}` Vue+CSRF
- `.../display/page/brand-page?brandNo={B...}`
- `.../sitemapindex-product.xml`
- AVOID `oliveyoung.co.kr` (403)

## genomma lab

### 1.
Scraper de olive-young para investigacion y desarrollo (I+D) cosmetico. Objetivo unico: detectar tendencias K-beauty Korea y bestsellers autoritativos. NO es un scraper de precios: ignoramos original_price, sale_price, max_discount_price, stockQty, reviews individuales, variantes, imagenes secundarias e ingredientes en texto libre. Buscamos senales de tendencia agregadas: productos que rankean en bestsellers por categoria en Korea y en mercado global (USA/internacional), popularidad (rating 0-5, reviewCnt), marca (KR y EN), categoria, flags newYn/bestYn/flashYn/is_soldout, tags estructurados como Vegan o Clean Beauty, y promociones nominativas cuando existan. Fuente canonica de ejecucion: global.oliveyoung.com y el microservicio interno product-ranking-service.oliveyoung.com. El dominio oliveyoung.co.kr devuelve HTTP 403 anti-bot y queda fuera. Output: JSON estructurado por entidades. Los detalles de cada area vienen en los puntos siguientes.

### 2.
Infraestructura y bloqueos. Dominio principal global.oliveyoung.com sirve HTML UTF-8 en ingles con Cloudflare bot-challenge silente via iframe cdn-cgi/challenge-platform. Usar BrightData Scraping Browser con JS render y sesiones residenciales rotadas (US o UK), delay 3-5 segundos entre requests por host. robots.txt dicta Crawl-delay 5 para User-agent asterisco; permitidos /display, /product, /event, /board, /member; prohibidos /order, /cart, /myaccount, /aws, /claim, /delivery, /capi/send-event, /product/review-report. El microservicio product-ranking-service.oliveyoung.com no requiere CSRF ni cookies pero aplica el mismo Crawl-delay 5 por politica. NUNCA scrapear oliveyoung.co.kr: devuelve 403 con pagina estatica 잠시만 기다려 주세요. Si algun seed apunta a ese host emitir flag source_gone y descartar sin hacer request. Cloudflare challenge: si body contiene Just a moment antes del primer tag script legitimo, flag cloudflare_challenge y rotar sesion.

### 3.
Fuentes y URLs canonicas. API rankings sin CSRF, 2 endpoints bajo product-ranking-service.oliveyoung.com. 1) GET /v1/pages/ranking/sales/categories?region=KR&language-code=en devuelve JSON data pages.ranking.categories lista id name (11 cats KR, 12 cats region USA). 2) GET /v1/pages/ranking/sales/products con params category-id, region, language-code, margin-country-code=10, delivery-country-code=10 devuelve 100 items ordenados por rank. region validos: KR y USA. NO usar region=Global ni language-code=ko: devuelven 400 o array vacio. Enriquecimiento product: Scraping Browser sobre global.oliveyoung.com/product/detail?prdtNo={id}, navegar completo para que Vue ejecute POST detail-data con CSRF matching. Brand: global.oliveyoung.com/display/page/brand-page?brandNo={no}. Sitemap: global.oliveyoung.com/sitemapindex-product.xml.

### 4.
Entidad ranking, una fila por combinacion (region, category_id, rank). Campos siempre presentes: ranking_id string derivado como oliveyoung-global_{region}_{category_id}_{rank}_{scraped_date}, site_code fijo oliveyoung-global, region_code valores permitidos KR o USA, category_id string del request, category_name string del endpoint categories, rank entero 1 a 100, prdt_no string PK del producto, product_url string https://global.oliveyoung.com/product/detail?prdtNo={prdt_no}, product_name_en string del campo name, product_name_kr string del campo original_name, brand_name_en, brand_name_kr, brand_no string, rate numero 0 a 5 un decimal, is_soldout bool, has_coupon bool, has_gift bool, promotion_name string o null, thumbnail_img_url_raw string relativo, thumbnail_img_url_full string derivado https://cdn-image.oliveyoung.com/{raw}, scraped_date YYYY-MM-DD, scraper_flags lista. Una fila por (region, category_id, rank) unica. Dedupe por esa clave.

### 5.
Entidad product. Fuente base: cada prdt_no distinto visto en la corrida de ranking. Campos core heredados del ranking: prdt_no, product_url, product_name_en, product_name_kr, product_name_clean_en, product_name_clean_kr, brand_name_en, brand_name_kr, brand_no, rate, is_soldout, thumbnail_img_url_full. Agregados: category_ids lista con todos los category_id donde aparecio el producto en la corrida, category_names lista paralela, ranks lista de enteros paralela a category_ids (rank en cada categoria), best_regions lista con KR y/o USA segun fuente. Enriquecimiento opcional via Scraping Browser sobre /product/detail?prdtNo={id} cuando el producto aparece en 2 o mas rankings: review_count entero, new_yn bool, best_yn bool, flash_yn bool, claim_tags lista (valores observables: Vegan, Clean Beauty, Cruelty Free). Si el enriquecimiento falla flag product_enrich_failed, el producto igual se emite con campos core. Dedupe por prdt_no.

### 6.
Entidad brand. Fuente: agregado del ranking + Scraping Browser sobre /display/page/brand-page?brandNo={brand_no}. Campos: brand_no string PK, brand_name_en, brand_name_kr, brand_url string https://global.oliveyoung.com/display/page/brand-page?brandNo={brand_no}, brand_total_products_in_rankings entero (cuentas de prdt_no distintos de esa marca que aparecieron en algun ranking de la corrida), brand_avg_rank numero (promedio simple de rank observado, menor es mejor), brand_og_image string o null (capturado desde meta property=og:image de la pagina de marca), scraped_date, scraper_flags. Visitar la pagina de marca solo para las top-20 marcas por brand_total_products_in_rankings en la corrida; el resto de marcas aparece solo como referencia desde product y ranking sin visita dedicada. Si la pagina de marca devuelve 404 flag brand_page_404 y emitir brand con brand_og_image null.

### 7.
Reglas de parsing y normalizacion. language-code siempre en, margin-country-code y delivery-country-code siempre 10. name_clean_en sobre product_name_en: colapsar whitespace, quitar sufijos marketing entre corchetes tipo [TRIPLE] [Valen EDITION] [dropdropdrop EDITION], quitar sufijos entre parentesis que matchen (OY-Exclusive) (Refill Set) (+1ea) (+Pouch Keyring) (2604), cortar en primer caracter pipe o slash, max 100 chars, si queda vacio fallback al raw y flag name_clean_fallback. name_clean_kr sobre product_name_kr: colapsar whitespace, quitar tokens 기획 증정 한정 단독 리필 더블 트리플 파우치 키링 콜라보 역 cuando esten al final y entre parentesis o sin ellos, quitar codigos de fecha tipo (2604) (2505), separador fullwidth al inicio, max 100 chars. rate fuera de [0,5] o no numerico null + flag rating_invalid. thumbnail_img_url_full solo se calcula si el raw matchea regex prdtImg/\d+/.

### 8.
Limites de crawl, skip rules y flags permitidos. Default operativo v1: `max_pages=10`, interpretado como maximo de 10 paginas/combinaciones de ranking region-categoria en `sc_code` y maximo de 10 product detail `next_stage` en `sc_browser`. El input puede reducir ese valor; no debe superar 10 en preview para evitar descargas masivas accidentales. El plan completo documentado para corridas controladas sigue siendo: 2 calls a /categories + 11 calls KR x categoria + 12 calls USA x categoria + 1 call a /display/product/best-seller/order-best para review_count = 26 calls API; hasta 100 product-detail enrichments via Scraping Browser (productos que aparecen en 2 o mas rankings); hasta 20 brand-page visits. Hard caps: 1000 requests totales o 60 minutos wall time. Cache local 24h por prdt_no para no reabrir la misma ficha el mismo dia. Dedupe ranking por (region, category_id, rank), product por prdt_no, brand por brand_no. SKIP sin emitir cuando: pagina 404 o 410, prdt_no vacio o no matchea ^GA\d{8,12}$, seed apunta a oliveyoung.co.kr. Flags permitidos: source_gone, cloudflare_challenge, rating_invalid, name_clean_fallback, product_enrich_failed, brand_page_404, detail_csrf_missing, sold_out, api_400, api_parse_error.

### 9.
URLs reales observadas 2026-04-21, fixtures.

API host: https://product-ranking-service.oliveyoung.com

Categorias: /v1/pages/ranking/sales/categories?region=KR&language-code=en (y region=USA).

Ranking: /v1/pages/ranking/sales/products?category-id={ctgr}&region=KR&language-code=en&margin-country-code=10&delivery-country-code=10

ctgr probados: 1000000001 All, 1000000008 Skincare, 1000000031 Makeup, 1000000052 Bath, 1000000003 Masks, 1000000011 Suncare.

Top Orders: https://global.oliveyoung.com/display/product/best-seller/order-best?ctgrNo=&acesCntryCode=00&dispPageTypeCode=30&langCode=en&mrgnCntryCode=10&dlvCntryCode=10&isGlobal=true

Landing: https://global.oliveyoung.com/display/page/best-seller

Prdt rank 1 KR All: https://global.oliveyoung.com/product/detail?prdtNo=GA240824996

Prdt rank 1 KR Skincare: prdtNo=GA260338240

Brand: https://global.oliveyoung.com/display/page/brand-page?brandNo=B00051

Sitemap: https://global.oliveyoung.com/sitemapindex-product.xml
