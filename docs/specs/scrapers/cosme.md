# cosme.net — spec
https://www.cosme.net/
Proveedor: istyle Inc.
Categoría: I+D
Función: Tendencias de belleza Japón, rankings de productos

## databrightdata

### 1.
Scraper @cosme.net (I+D cosmético). Tendencias y rankings Japón. Entidades: `product`, `ranking`, `brand`. Señales: awards bestcosme (grand/hall/rookie + 24 cat.), rating 0-7, review_count, categorías, effects, ingredients, launch_date, regulation_class (quasi_drug/cosmetic). NO precios/disponibilidad/reviews.

### 2.
```json
{"product":["product_id","url","name_raw","brand_id","category_ids","effect_ids","ingredient_tag_ids","rating_avg","review_count","launch_date","regulation_class","variants"],"ranking":["source_type","year","group","category_slug","rank","product_id"],"brand":["brand_id","name","url","total_products","total_reviews"]}
```

### 3.
- `/products/{id}/`
- `/brands/{id}/?nt=1` (nt=1 obligatorio; sin él redirige a tieup PR)
- `/bestcosme/archive/{year}/{grand|hall|rookie}/`
- `/bestcosme/archive/{year}/category/{slug}/` (24+ slugs)
- `/categories/item/{id}/ranking`
- `/maker/maker_id/{id}`, `/variations/{id}/`

## genomma lab

### 1.
Scraper de @cosme.net para investigacion y desarrollo (I+D) cosmetico. Objetivo unico: detectar tendencias de belleza en Japon y rankings de productos. NO es un scraper de precios: ignoramos pricing, disponibilidad en tienda, ingredientes en texto libre y reviews individuales. Buscamos senales de tendencia agregadas: que productos ganan awards (bestcosme grand, hall, rookie y sus 24+ categorias anuales), popularidad (rating promedio en escala 0-7 y conteo de reviews), clasificacion del producto (marca, categorias, effect ids, ingredient tag ids como proxy de activos y claims), cuando fue lanzado (launch date y launch year para distinguir novedad vs clasico) y clase regulatoria japonesa (quasi_drug o cosmetic, senal relevante para formulacion). Output: JSON estructurado por entidades. Fuente autoritaria de propiedades tecnicas: BrightData Scraping Browser con salida JP residencial, decodificacion Shift_JIS forzada. Los detalles de cada area vienen en los puntos siguientes.

### 2.
Infraestructura, decoding y bloqueo. BrightData Scraping Browser con JS render y sesion residencial JP. Delay 1-2 segundos entre requests. Precondicion de decoding antes de extraer: pedir el body como buffer crudo, decodificar como UTF-8 y validar que contenga al menos un caracter en rango hiragana katakana o kanji Y cero U+FFFD; si falla re-decodificar como Shift_JIS con iconv-lite y emitir flag shift_jis_fallback. Rutas mas bloqueadas: /products/{id}/, /categories/item/{id}/ranking, /brands/{id}/product/. Firma de bloqueo: body menor a 10 KB Y contiene el string literal ご利用の環境からはアクセスできません. Ante bloqueo reintentar hasta 3 veces con nueva session id. Si al tercer intento sigue bloqueado emitir la fila con blocked=true y flag blocked_retried. Nunca continuar con pagina sospechosa de bloqueo aunque el status sea 200.

### 3.
Entidad product fuente /products/{id}/. Campos presentes null si faltan: product_id entero PK, product_url, product_name_raw, product_name_clean, brand_id, brand_name, category_primary_id ultimo id de la primera chain, category_ids flat dedup, category_names paralela, category_chains lista de chains cada una lista de objetos id name, effect_ids, effect_names, ingredient_tag_ids, rating_avg 0-7, review_count, review_count_photo, launch_date YYYY-MM-DD, launch_year, regulation_class quasi_drug cosmetic medical_device other o null, official_name, is_official bool o null, maker_id entero desde /maker/maker_id/{id}, maker_name, price_text bruto de la fila 容量・税込価格 (validado en HTML Shift-JIS; la conversion a markdown del MCP lo muestra como 希望小売価格 pero el DOM real usa 税込価格; parser prueba ambos), variants objetos volume_raw volume_value volume_unit price_jpy price_tax_included sku_note derivados de price_text, variations objetos variation_id label desde a href=/variations/{id}/, rankings ranking_name position year scope annual H1 H2, scraped_date, scraper_flags.

### 4.
Entidad ranking. Dos fuentes: bestcosme archive en /bestcosme/archive/{year}/{group}/ con group en grand, hall, rookie, y bestcosme por categoria en /bestcosme/archive/{year}/category/{slug}/ con al menos 24 slugs conocidos como serum, toner, lotion, lipstick, sunscreen, face-cream, face-mask, face-wash, cleansing, exfoliating, sheet-mask, booster-serum, liquid-foundation, powder-foundation, cushion-foundation, cream-foundation, bb-cc-cream, makeup-base, concealer, highlighter, shading, lip-care, eye-care, eyelash-serum, shampoo-treatment. Segunda fuente: /categories/item/{id}/ranking para rankings por categoria interna. Campos por fila: source_type con valores bestcosme o category_ranking, award_year, award_group, award_category_slug, category_id, rank, product_id, product_url, product_name_raw, product_name_clean, brand_name_raw, ai_highlights lista de strings, scraped_date. Una fila por combinacion year, group, category_slug, rank.

### 5.
Entidad brand. Fuente canonica /brands/{id}/?nt=1. IMPORTANTE: la ruta desnuda /brands/{id}/ sin el parametro nt=1 redirige a un tieup PR advertorial; nunca usar esa forma. Para paginacion de productos de marca usar /brands/{id}/product/. Campos: brand_id entero, brand_name, brand_url normalizada a la forma /brands/{id}/?nt=1, brand_total_products entero leido de la pestana 商品 (N), brand_total_reviews entero leido de la pestana クチコミ (N), brand_official_site url, brand_country string aunque suele estar ausente, scraped_date. No extraer logos ni descripciones libres de marca. Solo marcas que aporten al menos 20 productos entre los rankings de la corrida seran visitadas para listado completo de productos; el resto aparece solo por referencia desde product.

### 6.
Reglas de parsing. Product name raw: cascada de 5 fuentes en orden, primera no vacia gana. F1 breadcrumb (#header-sub o nav.breadcrumb), ultimo nodo de texto distinto de アットコスメ y no link a /brands/. F2 header anchor a href=/products/{product_id}/ match estricto del path, filtrar navegacion 商品情報 口コミ ブログ 写真 動画. F3 title split por ／ o /, primer segmento brand, resto name con strip de sufijo (の公式商品情報, の口コミ一覧, の口コミ写真・動画一覧, のブログ記事, の写真一覧, o cualquier の.*). F4 meta og:title mismo split. F5 img[alt] del carrusel, split por /, primer segmento con strip de variation suffix (2-3 digitos o unidades ml g 個 本 枚 trailing). Si las 5 fallan product_name_raw=null y flag name_extract_failed. Rating 0-7 un decimal, fuera de rango null + rating_invalid. Review count regex (\d+(?:,\d+)*)件 a int sin comas.

### 7.
Mas reglas de parsing. Launch date acepta YYYY/MM/DD, YYYY-MM-DD, YYYY年MM月DD日; solo YYYY年MM月 asumir dia 01 y flag launch_day_missing; solo YYYY年 dejar launch_date null y completar launch_year; fecha futura nulificar y flag launch_date_future. IDs dobles: aceptar /products/{id}/ y legacy /products/detail.php?product_id={id}; brand acepta /brands/{id}/ y /brand/brand_id/{id}/top. Name clean sobre raw: colapsar whitespace, quitar sufijos 【限定】 【数量限定】 【新発売】 【NEW】 【リニューアル】 y hashtags, si hay separador ／ o | quedarse con texto antes, preservar kanji katakana hiragana, max 100 chars, si queda vacio usar raw y flag name_clean_fallback. Limites por corrida: bestcosme grand/hall/rookie 1 pagina cada uno, categoria 24+ slugs x 1 pagina, category ranking max 5 x 30 cats, product detail max 3000 unicos con dedupe, brand listing max 10 paginas con >=20 productos, cache 24h por product_id, hard cap 10000 requests o 120 minutos.

### 8.
Output y reglas finales. Emitir tres arrays JSON y un summary: cosme_products_{YYYYMMDD}.json, cosme_rankings_{YYYYMMDD}.json, cosme_brands_{YYYYMMDD}.json, cosme_run_{YYYYMMDD}.json. El run summary contiene started_at, ended_at, requests, blocked, retried, errors, emitted_by_entity, skipped_by_reason. Todo en UTF-8, fechas ISO 8601, numeros como numeros, claves siempre presentes con null explicito; listas que no aplican van como [] nunca null. SKIP cuando: no se pueda extraer product_id, pagina siga bloqueada tras 3 retries, 404, o fila totalmente null. Flags permitidos: rating_invalid, launch_date_future, launch_day_missing, blocked_retried, shift_jis_fallback, name_clean_fallback, name_extract_failed. No inventar campos fuera de los puntos 3, 4, 5. Fixture de regresion obligatorio: product_id 10248076 debe devolver product_name_raw ルース パウダー y brand_name コスメデコルテ.

### 9.
URLs de ejemplo con IDs reales para fixtures antes del crawl completo.

Product detail formato moderno id largo: https://www.cosme.net/products/10264676/ (SK-II Genoptics Infinite Aura Essence, Grand Prize 2025 rank 1).
Product detail id corto 7 digitos legacy: https://www.cosme.net/products/2893546/ (SK-II Facial Treatment Essence).

Fixture obligatorio post v5 (decoding + name cascade): https://www.cosme.net/products/10248076/ (コスメデコルテ / ルース パウダー).

Bestcosme awards anuales grand: https://www.cosme.net/bestcosme/archive/2025/grand/
Bestcosme por categoria: https://www.cosme.net/bestcosme/archive/2025/category/serum/
Category ranking interno: https://www.cosme.net/categories/item/800/ranking (id 800 = skincare).

Brand page canonica con nt=1 obligatorio: https://www.cosme.net/brands/73/?nt=1 (SK-II brand_id=73). Listado paginado: https://www.cosme.net/brands/73/product/.

Todos estos IDs confirmados por muestreo en exploracion previa.

### 10.
Arquitectura 2-stage. Stage 1 sc_browser Chrome: DESCUBRIMIENTO en /bestcosme/archive/{year}/ y award/category, emite URL hija con next_stage. Stage 2 sc_code HTTP sin browser: FETCH via request(encoding:null) + Shift_JIS + parse. PROHIBIDO navigate() en Stage 2. R1: navigate() async interno, solo plano top-level; prohibido en sync (rebota async code is not allowed in sync functions). R4: parse() valida input contra schema y rechaza campos no declarados (rebota parse validation error: [0].<field> is not allowed); default parse() SIN args, derivar del DOM o location.href. Stage 1 parser deriva award_year con regex /bestcosme\/archive\/(\d+)\// sobre location.href, fallback new Date().getFullYear(). next_stage: {url, page_type in [grand,hall,rookie,category,product], award_year, award_group, award_category_slug o null} — sidecar NO pasa por parse(). award_year al integration viene de input; si falta o invalido fallback con warn award_year_defaulted o award_year_invalid.

### 11.
Resiliencia y rate limit. Stage 1 navigate() PLANO top-level una sola vez sin retry interno (R1). Si falla el worker termina sin parcial; orquestacion externa detecta, aplica backoff y reencola. No sleep/jitter antes de next_stage(): presion sobre Stage 2 se controla via concurrencia de plataforma. Recordatorio R4: parser_code Stage 1 NO recibe variables via parse({...}); canal seguro es derivar del DOM o location.href (ver punto 10 award_year). Stage 2 request() SI mantiene retry 3 intentos backoff 3s 8s 15s (HTTP puro, R1 no aplica): reintenta en excepciones, 429 y 5xx; no reintenta en 4xx distintos de 429. Tras 3 intentos collect minimal {product_id, product_url, scraper_flags:[rate_limit_blocked], fetch_error, fetch_attempts}. Flags agregados al punto 8: rate_limit_blocked, unexpected_page_type, award_year_defaulted, award_year_invalid. Eliminado v5.3: nav_failed_rate_limit. v5.4 sin nuevos flags (R4 fix es patron de invocacion).
