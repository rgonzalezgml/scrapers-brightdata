# cosme — DOM map

Fuente: `https://www.cosme.net/ranking/products`
Capturado: 2026-04-27
Encoding: `Shift_JIS` (declarado en `<meta http-equiv="Content-Type" content="text/html; charset=Shift_JIS">`)
Nota: curl con `--compressed` devuelve el body correctamente; decodificar como `shift_jis` con `iconv-lite`.

---

## Contenedor de lista de productos

```
div#list-item
```

Contiene todos los `<dl>` del ranking. Cada `<dl>` es un producto.

---

## Estructura de un producto (dos variantes según rank)

### Ranks 1–3 (`top3`)

```html
<dl class="top3 clearfix">
  <dt>
    <span class="rank-num">
      <img alt="1位" />     <!-- alt contiene el número: "1位", "2位", "3位" -->
    </span>
    <span class="status">
      <img alt="順位アップ" title="順位アップ" />   <!-- movimiento semana -->
    </span>
  </dt>
  <dd class="pic">
    <a href="https://www.cosme.net/products/{product_id}/">
      <img alt="{brand} / {name}" />
    </a>
    <!-- optional --> <span class="icon-cmn-bestcosme">ベストコスメ</span>
  </dd>
  <dd class="summary">
    <div class="clearfix">
      <span class="brand">
        <a href="https://www.cosme.net/brands/{brand_id}/">{brand_name}</a>
      </span>
    </div>
    <span class="item">
      <a href="https://www.cosme.net/products/{product_id}/">{product_name}</a>
    </span>
    <span class="category">
      [<a href="https://www.cosme.net/categories/item/{category_id}/">{category_name}</a>]
    </span>
    <div class="rating-point clearfix">
      <p class="rating reviewer-average arg-{N_N}">{rating}</p>
      <p class="votes">クチコミ<a href="..." class="count">{review_count}</a>件</p>
    </div>
    <div class="clearfix">
      <p class="price">税込価格：{price_raw}</p>
      <p class="onsale">発売日：{launch_date}</p>
    </div>
  </dd>
</dl>
```

### Ranks 4+ (sin clase `top3`)

```html
<dl class=" clearfix">
  <dt>
    <span class="rank-num">
      <span class="num">{rank_number}</span>
      <span class="rank">位</span>
    </span>
    <span class="status">
      <img alt="..." title="..." />
    </span>
  </dt>
  <!-- dd.pic y dd.summary: misma estructura que top3 -->
</dl>
```

---

## Selectores por campo

| Campo | Selector / Fuente |
|-------|-------------------|
| `rank` (1–3) | `dl.top3 span.rank-num img[alt]` → extraer número de alt ("1位" → 1) |
| `rank` (4+) | `dl:not(.top3) span.rank-num span.num` → texto directo |
| `product_id` | `dd.pic a[href*="/products/"]` → regex `/products/(\d+)/` sobre href |
| `product_url` | `dd.pic a[href*="/products/"]` → attr `href` |
| `name` | `dd.summary span.item a` → texto |
| `brand_name` | `dd.summary span.brand a:first-child` → texto |
| `brand_id` | `dd.summary span.brand a:first-child[href]` → regex `/brands/(\d+)/` |
| `category_name` | `dd.summary span.category a` → texto |
| `category_id` | `dd.summary span.category a[href]` → regex `/categories/item/(\d+)/` |
| `rating` | `dd.summary .rating-point p.rating` → texto (float) |
| `review_count` | `dd.summary .rating-point p.votes a.count` → texto (int, strip comas) |
| `price_raw` | `dd.summary div p.price` → texto (ej. `税込価格：30mL・9,900円`) |
| `launch_date` | `dd.summary div p.onsale` → texto después de `発売日：` |
| `is_bestcosme` | `dd.pic span.icon-cmn-bestcosme` → existencia del nodo |
| `rank_movement` | `dt span.status img[title]` → title text ("順位アップ", "順位ダウン", "10位以上順位アップ", o ausente = 同順位) |

---

## Periodo del ranking

```html
<div id="nav-rank-header">
  <p>集計期間：{week_start}〜{week_end}</p>
</div>
```

Selector: `div#nav-rank-header p` → texto, split por `〜`, formato `YYYY/M/D`.

---

## Paginación

### Ranking general (cosme.net/ranking/products)

```
Página 1: https://www.cosme.net/ranking/products           (no tiene /page/0)
Página 2: https://www.cosme.net/ranking/products/page/1
Página 3: https://www.cosme.net/ranking/products/page/2
...
Página 10: https://www.cosme.net/ranking/products/page/9
```

Total: 100 productos en 10 páginas de 10. Observado: `100件中 1-10件を表示`.

Selector de paginador: `div.cmn-modules-paging ul li a[href*="/page/"]` → extraer números.
Selector de última página visible: último `li:not(.next) a` del paginador.

### Ranking por categoría de item (`/categories/item/{id}/ranking/`)

```
Página 1: https://www.cosme.net/categories/item/{id}/ranking/
Página 2: https://www.cosme.net/categories/item/{id}/ranking/?page=2
```

---

## Navegación semanal

```html
<div id="nav-week-header">
  <ul>
    <li>今週</li>                                                         <!-- esta semana (sin link) -->
    <li><a href="https://www.cosme.net/ranking/products/week/2">先週</a></li>
    <li><a href="https://www.cosme.net/ranking/products/week/3">先々週</a></li>
  </ul>
</div>
```

Patrón: `/ranking/products/week/{N}` donde N=2 es la semana pasada, N=3 es hace dos semanas.
Para categorías: `/categories/item/{id}/ranking/week2/` y `/week3/`.

---

## Filtros del sidebar (nav-theme)

Todas las URLs están en `div#nav-theme div#nav-item`.

### Por categoría de item
Dropdown `<select name="item_id" id="item_id">` dentro de `form#nav-item-form` con action `https://www.cosme.net/categories`.
- Ejemplo: item_id=800 → URL generada: `https://www.cosme.net/categories/item/800/ranking/`
- Categorías top: 800=スキンケア, 802=メイクアップ, 803=ベースメイク, 804=香水, 805=ヘアケア, 806=ボディケア, 809=サプリメント

### Por efecto / お悩み
```
https://www.cosme.net/categories/effect/{effect_id}/ranking/
```
IDs observados: 1002=うるおい, 1003=毛穴, 1004=ニキビ, 1005=美白, 1006=低刺激・敏感肌, 1008=アンチエイジング, 1011=UVカット, 1035=シェイプアップ, 1086=コスパ, 1087=オーガニック, 1037=肌のハリ

### Por tipo de piel / 肌質
```
https://www.cosme.net/categories/skin/{skin_id}/ranking/
```
IDs: 1=普通肌, 2=乾燥肌, 3=脂性肌, 4=混合肌, 5=敏感肌, 6=アトピー

### Por edad / 年代
```
https://www.cosme.net/categories/age/{age_id}/ranking/
```
IDs: 1=10代, 2=20代前半, 3=20代後半, 4=30代前半, 5=30代後半, 6=40代, 7=50代〜

### Por ingrediente / 成分
```
https://www.cosme.net/categories/ingredient/{ingredient_id}/ranking/
```
IDs: 1001=コラーゲン, 1002=ヒアルロン酸, 1003=ビタミンC, 1005=プラセンタ, 1007=CoQ10, 1012=界面活性剤不使用, 1013=紫外線吸収剤不使用, 1015=パラベンフリー

### Por canal de compra / 購入場所
```
https://www.cosme.net/categories/pchannel/{channel_id}/ranking/
```
IDs: 1=デパート, 2=スーパー・ドラッグ, 3=バラエティショップ, 4=化粧品専門店, 5=コンビニ, 6=通販

---

## Seed URLs

```
https://www.cosme.net/ranking/products                      ← ranking general esta semana
https://www.cosme.net/ranking/products/week/2               ← semana pasada
https://www.cosme.net/ranking/products/week/3               ← hace 2 semanas
https://www.cosme.net/categories/item/800/ranking/          ← skincare ranking
https://www.cosme.net/categories/item/802/ranking/          ← makeup ranking
```

---

## Notas de parsing

- **product_id secundario**: también disponible como `data-object.parent.id` en los botones `.act-button` dentro de `span.clip`. Ejemplo: `data-object.parent.id="10147158"`. Alternativa robusta si el href no es suficiente.
- **Rating class**: la clase CSS del `<p>` de rating lleva el valor codificado: `reviewer-average arg-5_5` → 5.5, `arg-6` → 6.0. Usable como fallback si el texto no renderiza.
- **Ranks 1–3 vs 4+**: los tres primeros usan `<img alt="Nº位">` (requiere regex sobre alt); los demás usan `<span class="num">N</span>`. El selector debe manejar ambas variantes.
- **brand con tieup**: algunos `span.brand` tienen dos `<a>` — el primero es el nombre, el segundo lleva clase `icon-cmn-tieup`. Seleccionar `span.brand a:first-child` siempre.
- **price_raw**: incluye volumen y texto adicional, ej. `税込価格：30mL・9,900円` o `税込価格：715円` o `税込価格：6g・6,930円 (編集部調べ)`. Extraer el string completo sin `税込価格：`.
