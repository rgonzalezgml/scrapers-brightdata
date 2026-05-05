# cosme_new_arrivals — spec
https://www.cosme.net/calendar/
Proveedor: istyle Inc.
Categoría: I+D
Función: Calendario de lanzamientos de nuevos productos cosméticos Japón

## databrightdata

### 1.
Scraper @cosme.net calendario lanzamientos JP (I+D). 3 stages sc_code: Stage 1 extrae días activos del mes; Stage 2 parsea 9 campos — release_date >= hoy → next_stage(Stage 3), < hoy → collect directo; Stage 3 visita product_url y enriquece. Caps: 500 enriquecidos/corrida, 90 min. NO precios ni rankings.

### 2.
```json
{"base":["product_id","product_url","product_name","brand_id","brand_name","brand_url","release_date","shop_url","scraped_at"],"enriched_extra":["description","how_to_use","ingredients","classification","jan_code","official_url","manufacturer","manufacturer_url","category_full","category_path","rating_detail","points","review_count","photo_count","qa_count","cat_rank","cat_rank_name","likes","haves","all_images","stores","related_products"]}
```

### 3.
- `/calendar/index/year/{YYYY}/month/{MM}` → mes; `/day/{DD}` → día
- `/products/{id}/` → detalle producto (Stage 3)
- `/brands/{id}/` → perfil marca
- robots.txt Disallow: `/product/new/`, `/api/`, `/categories/api/`

## genomma lab

### 1.
Propósito: capturar el calendario editorial de lanzamientos de nuevos productos cosméticos en Japón de @cosme.net para detectar innovaciones en el momento exacto de su salida al mercado japonés. @cosme es el portal de referencia de reviews de cosmética en Japón (~20M usuarios). La sección `/calendar/` agrupa los productos por fecha de lanzamiento oficial, organizados jerárquicamente por marca: una marca puede lanzar múltiples productos el mismo día. Señales relevantes para I+D: fecha exacta de lanzamiento, nombre del producto en japonés, ID interno de @cosme (permite cruzar con rankings y reviews del scraper `cosme`), marca (con su URL de perfil en @cosme), y enlace de compra directa (`shop_url` a cosme.com o a JS modal). El scraper cubre el mes en curso más meses futuros e históricos accesibles por la navegación mensual.

### 2.
Infraestructura. El calendario de `www.cosme.net/calendar/` es HTML estático servido en **Shift_JIS** (igual que el scraper `cosme` de rankings). Decodificar con `iconv-lite` como `shift_jis`. Cada página de día carga completamente sin JS — es HTML puro compatible con `sc_code` worker (HTTP sin Scraping Browser). Firma de bloqueo: body < 10 KB o contiene `アクセスできません`. Ante bloqueo: reintentar hasta 3 veces con nueva sesión. Proxy: residencial JP. No hay Cloudflare ni consent wall documentado. robots.txt de `www.cosme.net`: Disallow `/product/new/` (path distinto al calendario — no afecta), `/api/`, `/categories/api/`, `/isauth/`, `/user/login`; Crawl-delay solo para Baidu/Yeti/Yandex/Applebot (no para `*`). ClaudeBot no listado. Encoding: validar que el body decodificado contiene al menos un carácter hiragana/katakana/kanji y cero U+FFFD.

### 3.
URLs canónicas.

Mes actual (redirección al mes en curso):
```
https://www.cosme.net/calendar/
```

Mes específico:
```
https://www.cosme.net/calendar/index/year/{YYYY}/month/{MM}
```

Día específico (página de listing con todos los productos que se lanzan ese día):
```
https://www.cosme.net/calendar/index/year/{YYYY}/month/{MM}/day/{DD}
```

Detalle de producto:
```
https://www.cosme.net/products/{product_id}/
```

Perfil de marca:
```
https://www.cosme.net/brands/{brand_id}/
```

Navegación mensual (extraída del `calendarNaviMonth` en la página de mes):
```html
<p class="calendarNaviMonth">
  <span class="past"><a href="/calendar/index/year/2026/month/04" rel="prev">4月</a></span>
  <span class="current"><a href="/calendar/index/year/2026/month/05">2026年5月</a></span>
  <span class="future"><a href="/calendar/index/year/2026/month/06" rel="next">6月</a></span>
</p>
```

Seeds de referencia (validados 2026-05-03):
- `https://www.cosme.net/calendar/index/year/2026/month/05` — mayo 2026
- `https://www.cosme.net/calendar/index/year/2026/month/05/day/01` — 1 mayo 2026 (111 productos, 40+ marcas)

### 4.
Estructura DOM del calendar day page.

La página de día tiene tres bloques lógicos:

**1. Navegación mensual** (`div.inr-calendar > p.calendarNaviMonth`): links al mes anterior y siguiente.

**2. Tabla de días** (`table.calendarNaviDay`): celdas `th > p.day{NN}[off]`. Los días con `off` en la clase no tienen productos (fin de semana o sin lanzamientos). Los días activos tienen `<a href="/calendar/index/year/{YYYY}/month/{MM}/day/{DD}">`.

**3. Lista de productos por marca** (`div.newProductList`): estructura observada real:
```html
<div class="ttl-day">
  <h3 class="subTitle">5月1日 (金)</h3>
</div>
<h4 class="brandName">
  <a href="https://www.cosme.net/brands/42/">ランコム</a>
</h4>
<ul class="productInformation">
  <li>
    <p class="productName">
      <span class="name">
        <a href="https://www.cosme.net/products/10260179/">イドル リップ バターグロウ</a>
        <a href="https://www.cosme.com/products/detail.php?product_id=339926" class="btn-cmn-buy">購入サイトへ</a>
      </span>
    </p>
    <p class="productIcon"></p>
  </li>
</ul>
```

Patrón: cada `h4.brandName` introduce una sección de productos para esa marca. Los `<li>` dentro del `<ul.productInformation>` siguiente pertenecen a esa marca hasta el próximo `h4.brandName`.

**Nota de shop_url**: algunas entradas tienen link directo a `cosme.com`; otras usan JS modal `javascript:tb_show(...)` con `/dialog/shopping-link/index/productId/{id}`. En ese caso emitir `shop_url: null` y flag `shop_url_js_modal`.

### 5.
Entidad `new_product`. Una fila por producto. Todos los productos emiten los campos base (Stage 2). Los productos con `release_date >= CURRENT_DATE` son enriquecidos por Stage 3 con campos adicionales.

**Campos base — Stage 2** (todos los productos):

| Campo | Fuente DOM | Regla |
|---|---|---|
| `product_id` | Regex `\/products\/(\d+)\/` sobre href del `a` del producto | Skip si vacío |
| `product_url` | `"https://www.cosme.net/products/" + product_id + "/"` | Construir siempre |
| `product_name` | Texto del `a` del producto (primer `a` del `span.name`) | Strip whitespace |
| `brand_id` | Regex `\/brands\/(\d+)\/` sobre href del `a` del `h4.brandName` | null si no tiene link |
| `brand_name` | Texto del `a` del `h4.brandName` | Strip whitespace |
| `brand_url` | href del `a` del `h4.brandName` (URL absoluta) | null si no tiene link |
| `release_date` | Extraído del `h3.subTitle` de la página (ej. "5月1日 (金)") + año de la URL | Normalizar a YYYY-MM-DD |
| `shop_url` | href del `a.btn-cmn-buy` si es URL HTTP(S); null si es `javascript:` | Ver nota §4 |
| `scraped_at` | `new Date().toISOString()` | ISO 8601 |

**`release_date` — normalización**: la fecha del título `"5月1日 (金)"` no incluye el año. Obtener año y mes del path de la URL (ej. `/calendar/index/year/2026/month/05/day/01`). Construir `YYYY-MM-DD` con zero-padding. Si la fecha del path y la del título de h3 son inconsistentes, priorizar el path y emitir flag `date_mismatch`.

**Campos enriquecidos — Stage 3** (solo productos con `release_date >= CURRENT_DATE`, máx 500/corrida):

Selectores en `www.cosme.net/products/{id}/` — idénticos a los del parser `cosme-ranking-products/sc_code/parser_code_v1.js`:

| Campo | Selector CSS | Notas |
|---|---|---|
| `description` | `#product-spec dl.item-description dd` | HTML → texto; `<br>` → `\n` |
| `how_to_use` | `#product-spec dl.use dd` | HTML → texto; `<br>` → `\n` |
| `ingredients` | `#product-spec dl.all-components dd` | HTML → texto; `<br>` → `\n` |
| `classification` | `#product-spec dl.quasi-drug dd` | text_sane(); null si ausente |
| `jan_code` | `#product-spec dl.jan-code dd` | text_sane(); null si ausente |
| `official_url` | `#product-spec dl.official-site dd a` attr `href` | null si ausente |
| `manufacturer` | `#product-spec dl.maker dd a` | text_sane() |
| `manufacturer_url` | `#product-spec dl.maker dd a` attr `href` → `new URL(href, base).href` | null si ausente |
| `category_full` | `#product-spec dl.item-category dd a` — join con ` > ` | string breadcrumb |
| `category_path` | `#product-spec dl.item-category dd a` — array de `{name, url}` | array |
| `rating_detail` | `p.average` | parseFloat; null si ausente |
| `points` | `p.point` | parseFloat extraer dígitos; null si ausente |
| `review_count` | `.navi-tab .review .num` | parseInt sin dígitos → 0 |
| `photo_count` | `.navi-tab .post-photo .num` | parseInt sin dígitos → 0 |
| `qa_count` | `.navi-tab .qa .num` | parseInt sin dígitos → 0 |
| `cat_rank` | `.info-ranking .info-ranking span` first | parseInt; null si ausente |
| `cat_rank_name` | `.info-ranking .info-ctg a` | text_sane(); null si ausente |
| `likes` | `.act-counter[data-object.class="product_like"]` | parseInt → 0 si ausente |
| `haves` | `.act-counter[data-object.class="product_have"]` | parseInt → 0 si ausente |
| `all_images` | `.pict-list img` attr `src` | array de URLs; deduplicar |
| `stores` | `#product-shopping-site .cosmestore .toggle ul li a` | array de text_sane() |
| `related_products` | `#product-line-up .item-list a` — `{name, url}` | array |

### 6.
Paginación y estrategia de crawl — 3 stages.

**Stage 1** (interaction + parser):
1. Cargar `/calendar/index/year/{YYYY}/month/{MM}`.
2. Extraer todos los links de días activos de `table.calendarNaviDay` (días sin clase `off`).
3. Para cada día activo emitir `next_stage({url, year, month, day})`.

**Stage 2** (interaction + parser):
1. Cargar la URL del día recibida vía `input`.
2. Parsear todos los productos de la página (estructura §4).
3. Para cada producto extraer los 9 campos base (§5).
4. **Filtro de enriquecimiento**:
   - Si `release_date >= CURRENT_DATE` → `next_stage({url: product_url, product_id, product_name, brand_id, brand_name, brand_url, release_date, shop_url, scraped_at})`.
   - Si `release_date < CURRENT_DATE` → `collect(producto_base)` directamente.
5. El Stage 2 ordena los productos futuros de más próximos a más lejanos antes de emitir `next_stage`, para que el cap de 500 priorice los lanzamientos más inmediatos.

**Stage 3** (interaction + parser):
1. Cargar `input.url` (la `product_url` del producto).
2. Extraer los campos enriquecidos (§5 tabla Stage 3) usando los selectores de `cosme-ranking-products/sc_code/parser_code_v1.js`.
3. Combinar con los campos base recibidos por `input`.
4. Emitir `collect({...campos_base, ...campos_enriquecidos})`.
5. Si la página retorna HTTP 404 o body < 5 KB → emitir `collect(campos_base)` con flag `detail_unavailable` y no abortar.

**Estrategia por día (alternativa)**:
- Cargar directamente la URL del día sin pasar por el mes. Útil para runs incrementales.

**Scope por defecto**: mes actual + 1 mes futuro = máximo ~60 páginas de día.

**Hard caps**:
- Stage 3: máx **500 productos enriquecidos** por corrida (los más próximos primero).
- Wall time total: **90 minutos** (Stage 1+2 ~10 min + Stage 3 ~80 min para 500 productos).
- Filas totales por corrida: sin límite explícito (los básicos son ilimitados; solo Stage 3 está capado).

**No hay paginación dentro de un día** — todos los productos de un día aparecen en una sola página (observado: 111 productos en 2026/05/01, sin paginar).

### 7.
Skip rules. No emitir fila cuando:
- No se puede extraer `product_id` (product URL no matchea `/products/\d+/`).
- La página del día retorna HTTP 404 (el día no tiene lanzamientos registrados).
- Body < 10 KB — emitir flag `blocked_retried` y reintentar 3 veces.
- El `div.newProductList` no existe en la página (sin lanzamientos ese día).
- `product_name` está vacío después de strip.

### 8.
Flags permitidos en `scraper_flags[]`:
- `shift_jis_fallback` — body re-decodificado como Shift_JIS.
- `blocked_retried` — página bloqueada, reintentada 3 veces.
- `shop_url_js_modal` — `btn-cmn-buy` usa JS modal, `shop_url` emitido como null.
- `brand_no_link` — `h4.brandName` no tiene `<a>`, `brand_id` y `brand_url` son null.
- `date_mismatch` — fecha del h3.subTitle inconsistente con path de URL.
- `product_name_missing` — `span.name a` vacío o ausente.
- `detail_unavailable` — Stage 3: página de detalle retornó 404 o body < 5 KB; producto emitido con solo campos base.
- `enrichment_cap_reached` — Stage 3: se alcanzó el límite de 500 productos enriquecidos; productos restantes emitidos como básicos aunque `release_date >= hoy`.

No inventar flags fuera de esta lista.

### 9.
Output y naming.
- Archivo de salida: `cosme_newarrivals_{YYYYMM}.json` — array mixto de `new_product` objects del mes (básicos + enriquecidos en el mismo array).
- Tabla destino: `SRC_COSME_RANKING_NEWARRIVALS`.
- Encoding: UTF-8 (decodificar Shift_JIS internamente, emitir UTF-8).
- `product_id` como string, `brand_id` como string.
- `release_date` como string YYYY-MM-DD (ISO date).
- `scraped_at` como string ISO 8601 con timezone Z.
- `shop_url`: string URL o null.
- Campos de Stage 3 ausentes en registros básicos: omitidos (no emitir `null` explícito para campos de enriquecimiento). El consumidor diferencia por presencia/ausencia de `description` u otro campo enriched.
- `category_path`: array de objetos `{name: string, url: string}`.
- `all_images`: array de strings (URLs).
- `stores`: array de strings (nombres de tiendas).
- `related_products`: array de objetos `{name: string, url: string}`.

### 10.
Fixtures reales observados 2026-05-03 (página `/calendar/index/year/2026/month/05/day/01`).

Productos confirmados en la página del 1 mayo 2026:
| product_id | product_name | brand_name | brand_id | shop_url |
|---|---|---|---|---|
| 10260179 | イドル リップ バターグロウ | ランコム | 42 | `https://www.cosme.com/products/detail.php?product_id=339926` |
| 10226967 | ディオール アディクト クチュール リップスティック ケース | ディオール | 46 | JS modal |
| 10239494 | ル ボーム | ディオール | 46 | `https://www.cosme.com/products/detail.php?product_id=296513` |
| 10256030 | ディオールショウ モノ クルール | ディオール | 46 | JS modal |
| 10198811 | ネイルカラー | アナ スイ コスメティックス | 52 | `https://www.cosme.com/products/detail.php?product_id=212832` |
| 10292580 | マルチスカルプト マット リキッド カラー | M・A・C | 57 | `https://www.cosme.com/products/detail.php?product_id=401374` |
| 10294444 | オーキッド ハイライター | シスレー | 76 | `https://www.cosme.com/products/detail.php?product_id=411753` |

Total de marcas en la página del 1 mayo: 40+ marcas. Total de productos: 111.

### 11.
Relación con scraper `cosme`. El scraper existente captura el ranking semanal de los productos más revieweados (señal de demanda acumulada). Este scraper captura la fecha de lanzamiento oficial en el mercado japonés (señal de novedad). La clave de join cross-scraper es `product_id` — el mismo entero numérico aparece como `product_id` en el ranking de `cosme` y como `product_id` en el calendario de `cosme_new_arrivals`. Esto permite analizar el tiempo desde lanzamiento hasta aparición en ranking (time-to-trend).
