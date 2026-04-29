# cosme — spec
https://www.cosme.net/ranking/products
Proveedor: istyle Inc.
Categoría: I+D
Función: Tendencias de belleza Japón, rankings de productos

## databrightdata

### 1.
Scraper @cosme.net (I+D). Rankings semanales de belleza JP. Entidades: ranking_entry (listing + detail, 2 stages). Señales: rank, rank_change, rating, review_count, price_text/yen, release_date, description, ingredients. NO brands standalone, reviews individuales.

### 2.
```json
{"ranking_entry":["rank","rank_change","product_id","product_name","product_img","brand_name","brand_id","brand_url","category","category_url","rating","review_count","price_text","price_yen","size","is_open_price","tax_included","release_date","is_best_cosme","is_new","description","all_images","ingredients","shop_url","period_start","period_end","total_products","scraped_at"]}
```
`product_url` ausente (bug, ver §4).

### 3.
- /ranking/products + /page/{N} (N=1..9, 10/page, 100 total)
- /ranking/products/week/{W} (W=2 pasada, W=3 hace 2)
- /categories/item/{id}/ranking/?page={N}
- /categories/effect|skin|age|ingredient|pchannel/{id}/ranking/
- robots.txt: Disallow /api/ /categories/api/

## genomma lab

### 1.
Propósito: capturar el ranking semanal de productos de belleza de @cosme.net para detectar tendencias del mercado japonés en tiempo real. @cosme es el mayor portal de reviews de cosmética en Japón (~20M usuarios). El ranking se actualiza semanalmente (periodo visible en la página: `集計期間：YYYY/M/D〜YYYY/M/D`). Señales clave: posición en el ranking (rank), variación semanal (rank_movement), popularidad por reviews (rating 0–7, review_count), precio de referencia, fecha de lanzamiento, categoría del producto, y presencia de badge bestcosme. El scraper recolecta el ranking general y puede recolectar rankings filtrados por categoría de item, efecto, tipo de piel, edad, ingrediente y canal de compra. Output para GeommaAI: inteligencia de mercado de belleza JP, alertas de producto trending, análisis de tendencias semanales.

### 2.
Infraestructura. La URL canónica devuelve HTML con `charset=Shift_JIS`. Curl con `--compressed` devuelve el cuerpo; decodificar con `iconv-lite` como `shift_jis`. En BrightData Scraping Browser: `request(url, {encoding: null})` + `iconv.decode(buffer, 'shift_jis')`. Firma de bloqueo: body < 10 KB o contiene `アクセスできません`. Ante bloqueo: reintentar hasta 3 veces con nueva sesión. Proxy: residencial JP. No hay Cloudflare ni consent wall documentado. ClaudeBot no listado en robots.txt. robots.txt Disallow relevante: `/api/`, `/categories/api/`; no hay Crawl-Delay para bots genéricos. Encoding doble: el MCP/markdown puede mostrar el texto correctamente, pero el DOM real está en Shift_JIS — validar que el body contiene al menos un carácter hiragana/katakana/kanji y cero U+FFFD antes de parsear.

### 3.
URLs canónicas.

Ranking general (todas las categorías):
```
https://www.cosme.net/ranking/products              ← semana actual
https://www.cosme.net/ranking/products/page/{N}     ← N=1..9 (página 2..10)
https://www.cosme.net/ranking/products/week/2       ← semana pasada
https://www.cosme.net/ranking/products/week/3       ← hace 2 semanas
```

Rankings filtrados (misma estructura de paginación con `?page={N}`):
```
https://www.cosme.net/categories/item/{item_id}/ranking/
https://www.cosme.net/categories/effect/{effect_id}/ranking/
https://www.cosme.net/categories/skin/{skin_id}/ranking/
https://www.cosme.net/categories/age/{age_id}/ranking/
https://www.cosme.net/categories/ingredient/{ingredient_id}/ranking/
https://www.cosme.net/categories/pchannel/{channel_id}/ranking/
```

Seeds de referencia:
- `https://www.cosme.net/ranking/products` — ranking general esta semana
- `https://www.cosme.net/categories/item/800/ranking/` — skincare (item_id=800)
- `https://www.cosme.net/categories/item/802/ranking/` — makeup (item_id=802)

### 4.
Entidad principal: `ranking_entry`. Una fila por producto por ranking (combinación de page URL + rank position). El output final combina datos del listing (Stage 1) y datos de la página de detalle del producto (Stage 2).

Campos Stage 1 (listing):

- `rank` (int): posición en el ranking. Ranks 1–3: leer `dl.top3 dt span.rank-num img[alt]` → strip no-dígitos, cast int. Ranks 4+: `dl dt span.rank-num span.num` → texto, cast int. Fallback: posición por índice en página (`page * 10 + i + 1`).
- `rank_change` (string): variación respecto a la semana anterior. Valores: `"up"`, `"down"`, `"hot"` (subió 10+ posiciones), `"new"` (entrada nueva), `"same"` (sin cambio). Derivado del atributo `src` del `img` en `dt span.status img`.
- `product_id` (string): regex `/products/(\d+)/` sobre `href` del `dd.summary span.item a`. Skip si vacío.
- `product_name` (string): `dd.summary span.item a` → texto. (Spec anterior: `name`.)
- `product_img` (string URL): `dd.pic img[src]` → URL del thumbnail del listing. Campo nuevo.
- `product_url` (string URL): **AUSENTE en el output actual por bug de key mismatch.** Stage 1 emite la clave `url` (variable `prod_url`) en el objeto de input para Stage 2, pero `parser_code_v1.js` la lee como `input.prod_url` → resulta `undefined` → campo no emitido en el JSON final. Fix pendiente: renombrar `url` → `prod_url` en Stage 1, o `input.prod_url` → `input.url` en Stage 2.
- `brand_name` (string): `dd.summary span.brand a:first-child` → texto. Nota: algunos `span.brand` tienen segundo `<a class="icon-cmn-tieup">` — ignorarlo.
- `brand_id` (string): regex `/brands/(\d+)/` sobre href del `span.brand a:first-child`.
- `brand_url` (string URL): href absoluto del `span.brand a:first-child`. Campo nuevo.
- `category` (string): `dd.summary .category a` → texto. (Spec anterior: `category_name`.)
- `category_url` (string URL): href absoluto del `dd.summary .category a`. (Spec anterior: `category_id` int; ahora es URL string.)
- `rating` (float): clase CSS `p.rating` → regex `arg-(\d+)(?:_(\d+))?`. Ej: `arg-5_5` → 5.5, `arg-6` → 6. Rango 0–7. Fuera de rango → null + flag `rating_invalid`.
- `review_count` (int): `p.votes a.count` → strip no-dígitos, cast int.
- `price_text` (string): `p.price` → texto completo, ej. `"税込価格：924円"` o `"30mL・9,900円"`. (Spec anterior: `price_raw`.)
- `price_yen` (float | null): precio numérico extraído de `price_text` — regex `([\d,]+)\s*円`, strip comas, cast int. Null si no aplica.
- `size` (string): volumen/cantidad extraído de `price_text` — regex `([\d,.]+\s*(?:mL|ml|g|kg|個入り|枚|本))`. Cadena vacía si no aplica.
- `is_open_price` (bool): true si `price_text` contiene `オープン価格` o `open` (case-insensitive).
- `tax_included` (bool): true si `price_text` contiene `税込`.
- `release_date` (string): `p.onsale` → texto completo incluyendo label, ej. `"発売日：2017/2/8"`. Emitido como texto raw — sin normalizar a ISO. (Spec anterior: `launch_date`; spec anterior proponía normalización YYYY-MM-DD, no implementada.)
- `is_best_cosme` (bool): presencia de `span.icon-cmn-bestcosme`. (Spec anterior: `is_bestcosme`.)
- `is_new` (bool): presencia de `span.icon-cmn-new`. Campo nuevo.
- `shop_url` (string URL): `a.btn-cmn-buy[href]` del listing. Emitido como input para Stage 2 y re-emitido en el output final.
- `period_start` (string `"YYYY/M/D"`): primer componente del período `集計期間：{date1}〜{date2}` extraído de `#nav-rank-header p`. Formato source preservado, sin normalizar a ISO. (Spec anterior: `week_start` YYYY-MM-DD normalizado.)
- `period_end` (string `"YYYY/M/D"`): segundo componente del período. (Spec anterior: `week_end`.)
- `total_products` (int): total de productos en el ranking extraído del paginador (`(\d+)件中`). Típicamente 100 para el ranking general. Campo nuevo.
- `input` (object): snapshot de los parámetros de entrada del run (`page`, `max_pages`, `url`). Metadato de debug — presente en el JSON del run real.

Campos Stage 2 (detalle del producto — scrape de `/products/{product_id}/`):

- `description` (string): texto de la descripción del producto. Selector: `[class*="description"], .product-detail-text, .product-info` → primer match → `text_sane()`.
- `all_images` (array de strings URL): todas las URLs de imágenes `img[src*="media/product"], img[src*="skuimg"]` encontradas en la página de detalle, deduplicadas.
- `ingredients` (string): texto de ingredientes. Selector: `[class*="ingredient"], .product-ingredient` → primer match → `text_sane()`.

Campos de metadato:

- `scraped_at` (string ISO 8601): timestamp de ejecución de Stage 2, `new Date().toISOString()`. (Spec anterior: `scraped_date` YYYY-MM-DD.)

Campos del spec anterior NO implementados:
- `filter_type`, `filter_id` — no implementados. Pendiente para cuando se soporten rankings filtrados por categoría.
- `scraper_flags` — no implementado.

### 5.
Paginación.

**Ranking general**: página 1 en `/ranking/products`, páginas 2–10 en `/ranking/products/page/{N}` con N=1..9. Total 100 productos (10 por página). Detectar última página: último `li:not(.next) a` en `div.cmn-modules-paging ul`.

**Rankings filtrados**: página 1 en `/categories/{type}/{id}/ranking/`, páginas siguientes en `?page={N}`. Mismo paginador DOM.

**Semanas anteriores**: sufijo `/week/2` (semana pasada) o `/week/3` (hace 2 semanas) en la URL base, antes de `/page/{N}` si aplica. Para filtrados: `/categories/item/{id}/ranking/week2/` y `/week3/`.

Límite por corrida: máximo 10 páginas por ranking URL (100 productos). Hard cap total: 5000 filas o 60 minutos.

### 6.
Skip rules. No emitir fila cuando:
- No se puede extraer `product_id` (fila totalmente inválida).
- Página bloqueada tras 3 retries.
- HTTP 404.
- El `<dl>` no contiene `dd.summary` (nodo incompleto).

### 7.
Flags permitidos en `scraper_flags[]`:
- `rating_invalid` — rating fuera de rango 0–7.
- `launch_day_missing` — fecha de lanzamiento solo YYYY/M, asumido día 01.
- `launch_date_future` — fecha de lanzamiento futura, nullificada.
- `blocked_retried` — página bloqueada, reintentada 3 veces.
- `shift_jis_fallback` — body re-decodificado como Shift_JIS.
- `rank_movement_unknown` — img de status presente pero title no reconocido.
- `name_missing` — `span.item a` vacío o ausente.

No inventar flags fuera de esta lista.

### 8.
Output y naming.

Archivo de salida: `cosme_ranking_{YYYYMMDD}.json` — array de `ranking_entry` objects. El run real de referencia es `bd_scrapers/cosme-ranking-products/results/j_moi6iped88egk7mwf.json` (100 filas, periodo 2026/4/16–2026/4/22, ejecutado 2026-04-28).

Reglas: UTF-8, `scraped_at` como ISO 8601 timestamp, `period_start`/`period_end` como string `"YYYY/M/D"` (no ISO), `product_id` como string, `brand_id` como string, números numéricos, `all_images` como array nunca null.

Scope de corrida estándar: ranking general esta semana (10 páginas, 100 productos). Scope ampliado opcional: ranking general + 3 semanas (esta + 2 anteriores) = hasta 300 filas.

### 9.
Fixtures de regresión.

Semana 2026/4/16–2026/4/22 (run ejecutado 2026-04-28, archivo `j_moi6iped88egk7mwf.json`, 100 filas):

| rank | product_id | product_name | brand_name | rating | review_count | rank_change |
|------|-----------|-------------|-----------|--------|-------------|-------------|
| 1 | 10147158 | クリーミータッチライナー | キャンメイク | 5.5 | 26102 | (confirmar) |
| 2 | 10289905 | アプソリュ ザ UV クリーム | ランコム | 5.1 | 1419 | (confirmar) |
| 3 | 10264676 | ジェノプティクス インフィニットオーラ エッセンス | SK-II | 5.8 | 6164 | (confirmar) |
| 4 | 10268965 | プードルトランスパラントｎ Ｍ | クレ・ド・ポー ボーテ | 5.9 | 1391 | (confirmar) |
| 7 | 10259468 | ジェニフィック アルティメ セラム | (confirmar) | (confirmar) | (confirmar) | hot |
| 9 | 10124096 | スピーディーマスカラリムーバー | ヒロインメイク | 6 | 16183 | hot |
| 11 | 10248076 | ルース パウダー | コスメデコルテ | 5.6 | 10297 | (confirmar) |

Campos validados del objeto rank=9 (product_id 10124096) extraído del JSON real:
- `price_text`: `"税込価格：924円"`, `price_yen`: 924, `tax_included`: true, `is_open_price`: false
- `release_date`: `"発売日：2017/2/8"` (texto raw)
- `is_best_cosme`: true, `is_new`: false
- `period_start`: `"2026/4/16"`, `period_end`: `"2026/4/22"`
- `scraped_at`: `"2026-04-28T05:22:33.969Z"`
- `total_products`: 100
- `brand_url`: `"https://www.cosme.net/brands/11624/"`, `brand_id`: `"11624"`
- `category`: `"ポイントメイクリムーバー"`, `category_url`: `"https://www.cosme.net/categories/item/1045/"`
- `shop_url`: `"https://www.cosme.com/products/detail.php?product_id=302195"`
- `all_images`: array de 29 URLs
- `description` e `ingredients`: strings con texto japonés

product_id 10248076 (rank 11) es el fixture de regresión heredado del scraper anterior.

### 10.
Notas de arquitectura. Este scraper usa **sc_code worker con 2 stages**:

- **Stage 1** (`sc_browser/parser_code_v1.js` en lógica, pero el worker activo es `sc_code`): HTTP puro, scrape del listing `/ranking/products/page/{N}`. Parsea el DOM con cheerio/jQuery-like DSL. Emite un objeto por producto con todos los campos del listing más `meta_*` de período y paginación. La URL del producto se emite bajo la clave `url` (no `prod_url`).
- **Stage 2** (`sc_code/interaction_code_v1.js` + `sc_code/parser_code_v1.js`): navega a la URL de cada producto (vía `input.url`), espera carga, extrae `description`, `all_images`, `ingredients`. Combina con los campos de Stage 1 (recibidos como `input.*`) y emite el objeto final.

La página de ranking es HTML estático (Shift_JIS) — no requiere JS execution (no es SPA). BrightData sc_code con `request(url, {encoding: null})` + iconv es suficiente para Stage 1. Stage 2 puede requerir renderizado JS según la página de detalle de cada producto.

El directorio `bd_scrapers/cosme-ranking-products/sc_browser/` contiene versiones paralelas de los mismos archivos (interaction_code_v1.js, parser_code_v1.js) pero el worker principal en producción es **sc_code**, no sc_browser. No usar sc_browser a menos que se detecte anti-bot que requiera JS en el listing.

Comparar con scraper cosme_deprecated (sc_browser) que apuntaba a `/bestcosme/archive/{year}/` — ese target es distinto y no aplica aquí.

### 11.
Nota sobre cosme_deprecated. El directorio `bd_scrapers/cosme_deprecated/` apuntaba a premios anuales bestcosme (`/bestcosme/archive/{year}/`) — rankings estáticos anuales, no semanales. Este spec cubre un target distinto: rankings semanales dinámicos en `/ranking/products`. Si en el futuro se necesita volver a scrapear los awards anuales, ese es un scraper separado con spec propia.
