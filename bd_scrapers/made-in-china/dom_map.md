# made-in-china DOM map

Generado 2026-04-24 mediante curl SSR (Chrome UA, Accept-Language en-US).

---

## Via-1 — Search page (`/products-search/hot-china-products/{KW}.html`) — keyword search

> **Usada para búsqueda por keyword** (p. ej. `search_keyword: "citric acid"`).
> Slug: `"citric acid anhydrous"` → `"Citric_Acid_Anhydrous"` (Title_Case, guiones bajos).
> Página 1: `/products-search/hot-china-products/{Slug}.html`
> Página 2+: `/products-search/find-china-products/0b0nolimit/{Slug}-{N}.html` (href de `a.main.nextpage`).
>
> **NOTA — multi-search URL descartada (v11):**
> `/multi-search/{slug}/F0/pg-{N}.html` fue probada en v11.
> La página responde HTTP 200 pero no contiene `.products-item` ni `.list-node` ni `.prod-item`.
> Causa: DOM distinto (posiblemente modal de login o estructura diferente).
> Via-1 es el path correcto para búsqueda por keyword.

## Via-1 — Search page (`/products-search/hot-china-products/{KW}.html`)

Fixture: `https://www.made-in-china.com/products-search/hot-china-products/Industrial_Chemicals.html`
Tamaño SSR: ~880 KB. HTTP 200 estable a curl.

### Contenedor listing

```
div.search-list-container
  div.prod-list.J-prod-list.gallary
    div.prod-item.J-focus-faw   ← carrusel de anuncios top (50 elementos)
    ...
  div.products-item             ← lista principal SSR (30 elementos por página)
    div.img-list.swiper-wrapper.prod-banner-list [data-attr pdid:PRODUCT_ID]
      a.img-wrap.swiper-slide   href="https://{slug}.en.made-in-china.com/product/{ID}/..."  ← href absoluto
    a.company-name              href="https://{slug}.en.made-in-china.com/"
```

**Clase de card de la lista principal**: `div.products-item` (30 por página).
**Clase del carrusel ads**: `a.prod-item.J-focus-faw` (50 por página, incluyen hrefs de product).
**NO aparece `div.list-node` en via-1 search.**

Product hrefs: `href="https://..."` (absolutos, no protocol-relative).
Product hrefs dentro de `products-item`: ~52 únicos por página (con duplicados por swiper).

### Paginación via-1

Widget: `div.page-num` (misma estructura que via-2).
Next anchor: `<a href="//www.made-in-china.com/products-search/find-china-products/0b0nolimit/{KW}-2.html" class="main nextpage" rel="nofollow">`
— clase: `main nextpage` (dos palabras). Href **antes** de class en el HTML.
`span.page-total` = 10 (para Industrial_Chemicals, 2026-04-24).

---

## Via-2 — Catalog page (`/{Chem|Packaging-Printing}-Catalog/{SubCat}.html`)

Fixture: `https://www.made-in-china.com/Chemicals-Catalog/Alkali.html`
Tamaño SSR: ~670 KB. HTTP 200 estable a curl.

### Contenedor listing

```
div.search-list.search-list-wrapper
  div.list-node [ads-data="pdid:PRODUCT_ID,..."]   ← lista principal SSR (30 por página)
    div.list-node-content
      div.product-wrap
        a.img-wrap.swiper-slide  href="https://{slug}.en.made-in-china.com/product/{ID}/..."
        a.company-name           href="..."
  (también existen div.list-node.even para items alternos)

div.slide-box.J-focus-top-slide-box.swiper-ltr
  a.prod-item.J-focus-faw   ← carrusel de anuncios top (48 elementos)
```

**Clase de card de la lista principal**: `div.list-node` (con trailing space en el HTML: `class="list-node "`).
El `div.list-node.even` es una variante alterna de la misma lista.
**NO aparece `div.products-item` en via-2 catalog.**

Product hrefs: `href="https://..."` (absolutos) dentro de `list-node-content`.
pdid está en el atributo `ads-data` del `div.list-node`, no en un atributo `href` del div.

30 `div.list-node` únicos por página (con pdids únicos). ~53 product hrefs únicos por página.

### Paginación via-2 (catalog p1)

Canonical next: `<link rel="next" href="https://www.made-in-china.com/catalog/item999i132/Alkali-2.html"/>` (en `<head>`).
Next anchor (en body): `<a href="//www.made-in-china.com/catalog/item999i132/Alkali-2.html" class="next" rel="nofollow">Next...</a>`
— clase: `next` (solo). Dentro de `div.page-num` > `div.pager`.
`span.page-total` = 9 (para Alkali, 2026-04-24).

Todas las páginas paginadas del catálogo (p2..pN) siguen el patrón:
`https://www.made-in-china.com/catalog/item{CAT_ID}/{SubCat}-{N}.html`
donde `CAT_ID` (ej. `999i132`) se extrae del href del anchor "next" en p1.

---

## Via-3 — Detail product (`https://{slug}.en.made-in-china.com/product/{ID}/...`)

No aplica a listing. Ver spec §11 para fixtures.

---

## Selectores CSS del listing (resumen operativo)

| Propósito | Selector CSS | Notas |
|-----------|-------------|-------|
| Wait listing cargado | `.prod-item, .list-node, .products-item` | `.prod-item` presente en ambos; `.list-node` en via-2; `.products-item` en via-1 |
| Product links via-2 | `.list-node a[href*="en.made-in-china.com/product/"]` | En `div.list-node-content > a.img-wrap.swiper-slide` |
| Product links via-1 | `.products-item a[href*="en.made-in-china.com/product/"]` | `a.img-wrap.swiper-slide` dentro de `div.products-item` |
| Product links ambos (union) | `.list-node a, .products-item a, .prod-item` | Con filtro `href.includes('/product/')` |
| Company name via-2 | `.list-node .company-name` | href a supplier home |
| Company name via-1 | `.products-item .company-name` | href a supplier home |
| Next page via-1 | `a.main.nextpage` | Clase `main nextpage` |
| Next page via-2 | `.page-num a.next` | Clase `next`, dentro de `div.page-num` |
| Next page union | `a.main.nextpage, .page-num a.next` | Cubre ambos tipos |
| Total páginas | `span.page-total` | Mismo widget en ambos |
| Página actual | `span.page-current.J-page-current` | Mismo widget en ambos |

---

## Notas importantes

- `class="list-node "` tiene un espacio trailing en el HTML real de via-2. CSS selector `.list-node` matchea igualmente (CSS ignora trailing spaces en el atributo).
- Product hrefs en via-1 son `https://` (absolutos). En via-2 `div.list-node-content` también usan `https://`. En el carrusel `prod-item` de ambas páginas pueden ser protocol-relative `//`.
- El filtro `href.includes('en.made-in-china.com/product/')` es suficiente para distinguir product links de otros anchors (supplier home, inquiry, etc.).
- Company-name hrefs pueden ser `https://` o `//` — usar helper `absolutize()` en ambos.
- En el browser (Chromium + BrightData), el `__cf_bm` cookie de Cloudflare se asigna en la primera respuesta. No ha sido observado como redireccionador a challenge page en curl — no se espera Cloudflare challenge activo.
- El "carrusel ads" `prod-item J-focus-faw` en ambas páginas incluye hrefs de producto válidos (slugs diferentes al listing principal). Son los mismos 12 chars de product_id; se pueden incluir en el fan-out sin problema.
