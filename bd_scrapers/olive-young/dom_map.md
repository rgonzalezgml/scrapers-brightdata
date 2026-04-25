# olive-young — DOM map
last_verified: 2026-04-24 (inferido de spec §3/§9, errors.md, parsers v1/v2 — no curl directo)

## Cross-site

| Item | Valor |
|---|---|
| Dominio principal | `global.oliveyoung.com` |
| Dominio API rankings | `product-ranking-service.oliveyoung.com` |
| Anti-bot | Cloudflare bot-challenge silente (iframe `cdn-cgi/challenge-platform`) |
| Worker requerido | **Browser** para `global.oliveyoung.com`; Code OK para `product-ranking-service` |
| Crawl-delay | 5s (robots.txt) |
| Dominio bloqueado | `oliveyoung.co.kr` → 403 siempre (E1) |

---

## URL-template 1: Best-seller listing

```
https://global.oliveyoung.com/display/page/best-seller
```

| Item | Valor |
|---|---|
| last_verified | 2026-04-21 (spec §9) |
| Worker | Browser (Cloudflare, JS render) |
| Fixture | URL directa arriba |

### Tabs
| Selector | Descripción |
|---|---|
| `.nav-item.nbs-tab-item` | Tab container (esperar antes de click) |
| `#pillsTab1Nav1` | Tab USA/Global |
| `#pillsTab1Nav2` | Tab Korea |
| `#pillsTab1Nav1.active` | Tab USA activo |
| `#pillsTab1Nav2.active` | Tab Korea activo |
| `#pillsTab1Cont1` | Contenido tab USA |
| `#pillsTab1Cont2` | Contenido tab Korea |

### Productos en listing
| Selector | Descripción |
|---|---|
| `#orderBestProduct li a[href*='/product/detail']` | Links productos tab USA |
| `#koreaBestProduct li a[href*='/product/detail']` | Links productos tab Korea |

---

## URL-template 2: Rankings API (JSON, no browser)

```
https://product-ranking-service.oliveyoung.com/v1/pages/ranking/sales/products
  ?category-id={categoryId}&region={region}&language-code=en&margin-country-code=10&delivery-country-code=10
```

| Item | Valor |
|---|---|
| last_verified | 2026-04-21 (spec §9) |
| Worker | Code (HTTP JSON, sin CSRF) |
| Regiones válidas | `KR`, `US` (E3: `USA` → 400, `Global` → 400, `language-code=ko` → array vacío) |
| Respuesta | JSON, ~100 items por request |

### Campos JSON del response (verificados contra API live 2026-04-24)
| Campo JSON | Campo output | Notas |
|---|---|---|
| `id` | `prdt_no` | `^GA\d{8,12}$` — skip si no matchea (E5) |
| `name` | `product_name_en` | |
| `original_name` | `product_name_kr` | nombre coreano |
| `brand_name` | `brand_name_en` | |
| `kor_brand_name` | `brand_name_kr` | |
| `brand_no` | `brand_no` | string (ej. "B00051") |
| `rate` | `rate` | float 0-5; flag `rating_invalid` si fuera rango |
| `is_soldout` | `is_soldout` | bool |
| `has_coupon` | `has_coupon` | bool |
| `has_gift` | `has_gift` | bool |
| `promotion_name` | `promotion_name` | string o "" (nunca null en API) |
| `thumbnail_img_url` | `thumbnail_img_url_raw` | relative path; full URL si matchea `prdtImg/\d+` |
| `original_price` | `original_price` | float USD |
| `sale_price` | `sale_price` | float USD |
| _(posición en array)_ | `rank` | no hay campo rank en el response — usar índice+1 |

### URL endpoint categorías
```
/v1/pages/ranking/sales/categories?region=KR&language-code=en
```
Devuelve lista de categorías con `id` y `name`. Usar para `category_name` (no disponible en /products).

**Categorías conocidas:**
| ID | Nombre |
|---|---|
| 1000000001 | All |
| 1000000008 | Skincare |
| 1000000031 | Makeup |
| 1000000052 | Bath & Body |
| 1000000003 | Masks |
| 1000000011 | Suncare |

---

## URL-template 3: Product detail

```
https://global.oliveyoung.com/product/detail?prdtNo={GA...}
```

| Item | Valor |
|---|---|
| last_verified | 2026-04-21 (spec §3, E6) |
| Worker | **Browser obligatorio** — Vue + CSRF; Code worker → contenido vacío (E6) |
| Fixture KR rank1 | `?prdtNo=GA240824996` |
| Fixture KR Skincare rank1 | `?prdtNo=GA260338240` |
| Cloudflare | iframe `cdn-cgi/challenge-platform` → flag `cloudflare_challenge`, rotar sesión |

### Selectores producto detail
| Selector | Campo | Notas |
|---|---|---|
| `[data-testid=product-name]` | `name_en` | Vue-rendered — esperar ≥15s |
| `[data-testid=product-brand-name]` | `brand_name` | |
| `.prd-rating-info dt span` | `rate` | float string |
| `[data-testid=product-review-link] span.notranslate` | `review_count` | quitar comas antes de parseInt |
| `[data-testid=product-addtocart-button].state-stock` | `is_soldout` | presencia = soldout |
| `.prd-bedge span` | badges | puede haber múltiples: BEST, NEW, EARLY ACCESS, HOT DEAL |
| `.list-emblem li` | `claim_tags` | Vegan, Clean Beauty, Cruelty Free |
| `.location-bar .loc_cat` | `category_ids` | breadcrumb |
| `.main.type-error.error-not-found` | 404 guard | dead_page si existe |

---

## URL-template 4: Brand page

```
https://global.oliveyoung.com/display/page/brand-page?brandNo={B...}
```

| Item | Valor |
|---|---|
| last_verified | 2026-04-21 (spec §6) |
| Worker | Browser |
| Fixture | `?brandNo=B00051` |
| og:image | `meta[property="og:image"]` |
| 404 guard | flag `brand_page_404`, emitir brand con `brand_og_image=null` |

---

## Gotchas y errores conocidos

| Código | Síntoma | Fix |
|---|---|---|
| E1 | `oliveyoung.co.kr` → 403 | Flag `source_gone`, skip sin request |
| E2 | Cloudflare iframe `cdn-cgi/challenge-platform` | Flag `cloudflare_challenge`, rotar sesión residencial US/UK |
| E3 | `region=Global` o `region=USA` o `language-code=ko` → 400/vacío | Hardcodear `en` + `KR`/`US` únicamente |
| E5 | `prdt_no` no matchea `^GA\d{8,12}$` | Skip sin emitir |
| E6 | Product detail requiere Vue+CSRF | Stage 2 = Browser worker; Code worker → HTML skeleton vacío |
| E7 | Stage 1 Browser listing → Stage 2 Code detail (arquitectura v1) | Invertido en v2: Stage 1 Code API → Stage 2 Browser detail |
