# DOM Map — cosme-new-arrivals

Fuente: `www.cosme.net/calendar/`
Encoding: Shift_JIS (decodificar con iconv-lite)
Observado: 2026-05-03

---

## Página de mes `/calendar/index/year/YYYY/month/MM`

### Navegación mensual
```
div.inr-calendar > p.calendarNaviMonth
  span.past  > a[href=/calendar/index/year/YYYY/month/MM][rel=prev]  → mes anterior
  span.current > a[href=/calendar/index/year/YYYY/month/MM]           → mes actual
  span.future > a[href=/calendar/index/year/YYYY/month/MM][rel=next]  → mes siguiente
```

### Tabla de días activos
```
table.calendarNaviDay
  th > p.day{NN}           → día sin productos (no tiene <a>)
  th > p.day{NN}.off       → día inactivo (fin de semana sin lanzamientos)
  th > p.day{NN} > a[href=/calendar/index/year/YYYY/month/MM/day/DD]  → día con productos
```

---

## Página de día `/calendar/index/year/YYYY/month/MM/day/DD`

### Estructura principal
```
div.newProductList           → contenedor raíz (ausente si no hay lanzamientos ese día)
  div.ttl-day
    h3.subTitle              → "5月1日 (金)"  — texto con fecha del día
  h4.brandName
    a[href=https://www.cosme.net/brands/{brand_id}/]  → nombre y URL de marca
  ul.productInformation
    li
      p.productName
        span.name
          a[href=https://www.cosme.net/products/{product_id}/]  → nombre y URL producto
          a.btn-cmn-buy[href=https://www.cosme.com/...]         → shop_url (puede ser javascript:)
```

### Relación brand → productos
Cada `h4.brandName` introduce todos los `ul.productInformation` siguientes hasta el próximo `h4.brandName`. Traversal secuencial de hijos de `div.newProductList`.

---

## Campos extraídos

| Campo | Selector / Regex |
|---|---|
| `product_id` | `\/products\/(\d+)\/` sobre href del `<a>` del producto |
| `product_url` | `"https://www.cosme.net/products/" + product_id + "/"` |
| `product_name` | `text_sane()` del primer `<a>` de `span.name` |
| `brand_id` | `\/brands\/(\d+)\/` sobre href del `<a>` de `h4.brandName` |
| `brand_name` | `text_sane()` del `<a>` de `h4.brandName` |
| `brand_url` | href absoluta del `<a>` de `h4.brandName` |
| `release_date` | año+mes del path URL + día de `h3.subTitle` → YYYY-MM-DD |
| `shop_url` | href de `a.btn-cmn-buy` si es `https://`, null si es `javascript:` |

---

## Fixtures reales (2026-05-01)

| product_id | product_name | brand_name | brand_id | shop_url |
|---|---|---|---|---|
| 10260179 | イドル リップ バターグロウ | ランコム | 42 | `https://www.cosme.com/products/detail.php?product_id=339926` |
| 10226967 | ディオール アディクト クチュール リップスティック ケース | ディオール | 46 | JS modal |
| 10239494 | ル ボーム | ディオール | 46 | `https://www.cosme.com/products/detail.php?product_id=296513` |
| 10256030 | ディオールショウ モノ クルール | ディオール | 46 | JS modal |
| 10198811 | ネイルカラー | アナ スイ コスメティックス | 52 | `https://www.cosme.com/products/detail.php?product_id=212832` |
| 10292580 | マルチスカルプト マット リキッド カラー | M・A・C | 57 | `https://www.cosme.com/products/detail.php?product_id=401374` |

Total 2026-05-01: 111 productos, 40+ marcas.

---

## Señales de bloqueo

| Señal | Acción |
|---|---|
| Body < 10 KB | Flag `blocked_retried`, reintentar x3 |
| Body contiene `アクセスできません` | Bloqueo — reintentar |
| HTTP 404 en página de día | Skip silencioso (`dead_page`) |
