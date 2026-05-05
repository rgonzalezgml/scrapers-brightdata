# DOM Map — olive-young-new-arrivals

Fuente: `global.oliveyoung.com/display/page/new-arrivals`
Tipo: Vue 2 SPA (HTML estático + hidratación JS)
Proxy: residencial US o UK
Observado: 2026-05-03

---

## Página SPA `/display/page/new-arrivals`

### Shell HTML (antes de hidratación)
El HTML inicial contiene solo el skeleton de Vue. Los productos **no están en el HTML estático** — se inyectan tras el `axios.get('new-arrivals-data', {...})` del componente Vue.

Señal de Cloudflare challenge:
```
iframe[src*="cdn-cgi/challenge-platform"]   → challenge activo
title == "Just a moment"                    → challenge activo
body < 50 KB                                → posible challenge
```

---

## API interna (llamada axios por Vue)

```
GET https://global.oliveyoung.com/display/page/new-arrivals/new-arrivals-data
    ?acesCntryCode=00
    &langCode=en
    &dispPageTypeCode=40
    &mrgnCntry=10
```

La petición se hace con las cookies de sesión del browser ya establecidas — no requiere headers adicionales. Interceptar via `tag_response('api_data', /new-arrivals-data/)` antes del `navigate()`.

---

## Estructura de respuesta del API

```json
{
  "data": {
    "cornerList": [
      {
        "setContsMap": {
          "SET_NAME": [{ "contsCont": "New K-Beauty Essentials" }],
          "TEXT":     [{ "contsCont": "descripción del corner" }],
          "PRODUCT":  [ { ...campos del producto... } ]
        }
      }
    ]
  }
}
```

Path a corner_name: `cornerList[N].setContsMap.SET_NAME[0].contsCont`
Path a productos:   `cornerList[N].setContsMap.PRODUCT[M]`

---

## Campos de cada producto en el API

| Campo API | Tipo | Descripción |
|---|---|---|
| `prdtNo` | string | ID único formato `GA\d{9,12}` |
| `korPrdtName` | string | Nombre en coreano (invariante) |
| `prdtName` | string | Nombre en inglés (puede estar vacío) |
| `brandNo` | string | ID de marca |
| `brandName` | string | Nombre de marca en inglés |
| `korBrandName` | string | Nombre de marca en coreano |
| `saleAmt` | string numérico | Precio de venta KRW |
| `nrmlAmt` | string numérico | Precio normal KRW |
| `imagePath` | string | Ruta relativa → prefijo `https://cdn-image.oliveyoung.com/` |
| `soldOutYn` | `"Y"/"N"` | Agotado |
| `newYn` | `"Y"/"N"` | Badge New |
| `bestYn` | `"Y"/"N"` | Badge Best |
| `flashYn` | `"Y"/"N"` | Badge Flash |
| `cpnYn` | `"Y"/"N"` | Tiene cupón |
| `giftYn` | `"Y"/"N"` | Tiene regalo |
| `offrSpNm` | string | Nombre promoción especial |
| `prmtnNm` | string | Nombre promoción/cupón |

---

## Mapeo API → schema

| Schema | Fuente API | Regla |
|---|---|---|
| `prdt_no` | `prdtNo` | Skip si no matchea `^GA\d{9,12}$` |
| `product_url` | `prdtNo` | `"https://global.oliveyoung.com/product/detail?prdtNo=" + prdtNo` |
| `product_name_en` | `prdtName` | null si vacío |
| `product_name_kr` | `korPrdtName` | Skip si vacío |
| `brand_no` | `brandNo` | — |
| `brand_name_en` | `brandName` | — |
| `brand_name_kr` | `korBrandName` | — |
| `sale_amt` | `saleAmt` | `Number(saleAmt)`, null si no numérico |
| `nrml_amt` | `nrmlAmt` | `Number(nrmlAmt)`, null si no numérico |
| `image_url` | `imagePath` | `"https://cdn-image.oliveyoung.com/" + imagePath` |
| `is_soldout` | `soldOutYn` | `=== "Y"` |
| `is_new` | `newYn` | `=== "Y"` |
| `is_best` | `bestYn` | `=== "Y"` |
| `is_flash` | `flashYn` | `=== "Y"` |
| `has_coupon` | `cpnYn` | `=== "Y"` |
| `has_gift` | `giftYn` | `=== "Y"` |
| `promo_name` | `offrSpNm \|\| prmtnNm` | null si ambos vacíos |
| `corner_name` | `SET_NAME[0].contsCont` | Del corner padre |
| `scraped_date` | runtime | `new Date().toISOString().slice(0, 10)` |

---

## Fixture real observado (2026-05-03)

```
prdtNo:    GA260338924
URL:       https://global.oliveyoung.com/product/detail?prdtNo=GA260338924
image_url: https://cdn-image.oliveyoung.com/display/1056/ff868a66-94fa-4846-94a2-8de2af5dd5d0.jpg
```

Rango típico de productos únicos por run: 50–200 (rotación semanal de corners).

---

## Señales de bloqueo

| Señal | Acción |
|---|---|
| `iframe[src*="cdn-cgi/challenge-platform"]` | Flag `cloudflare_challenge` |
| `title` contiene "Just a moment" | Flag `cloudflare_challenge` |
| Body < 50 KB | Posible challenge — verificar |
| `cornerList` vacío | Flag `api_empty_response` |
| Error al parsear JSON | Flag `api_parse_error` |
