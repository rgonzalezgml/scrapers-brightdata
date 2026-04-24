# indiamart — DOM map

> Cache de selectores, structured data y patrones runtime del sitio.
> **Consultar ANTES de hacer MCP/curl/WebFetch**. Si aparece drift en un run de producción, marcar la sección `STALE` en su header y re-verificar antes del siguiente fix.
>
> Complemento de `docs/specs/scrapers/indiamart.md` (spec canónica) y `scrapers/indiamart/results/errors.md` (log de gotchas). Este archivo es el "qué-selector-matchea-hoy"; la spec es el "qué-campos-queremos".

---

## Cross-site (aplica a todos los templates)

- **HTTP encoding**: Content-Encoding gzip obligatorio. Cliente sin `--compressed` / `Accept-Encoding: gzip` lee binario (errors.md E2).
- **User-Agent**: Chrome genérico. Disallow para Scrapy, ClaudeBot, AhrefsBot, Bytespider, Baiduspider, Yandex (errors.md E1). OAI-SearchBot y GPTBot sí allowed pero safe default = Chrome.
- **Anti-bot markers**: `h1:contains("Access Denied")`, `h1:contains("Just a moment")`, `[action*="/errors/"]`, redirect a `/enquiry.html`.
- **Browser worker (sc_browser)**: `$` no tiene `.toArray()` en el runtime actual. Usar `$(sel).map((_, el) => ...).get()`. Verificado 2026-04-23 con preview que devolvió `TypeError: (intermediate value).toArray is not a function`. Skill R12 actualizada.
- **Code worker (sc_code)**: `$` es cheerio real, `.toArray()` funciona normal (consistente con alibaba / made-in-china en prod).

---

## Template: proddetail (Stage 2 detail)

`last_verified: 2026-04-23`

- **URL pattern**: `https://www.indiamart.com/proddetail/{slug}-{PID}.html` con PID 11–13 dígitos decimales.
- **Fixture URLs** (spec §11):
  - `22408594448` — Caustic Soda Flakes, Vats International, New Delhi — regresión obligatoria
  - `26047974573` — Caustic Soda IP Grade
  - `2858509198397` — Caustic Soda Lye
- **HTTP**: 200 OK, gzip, ~58 KB body (medido con curl).
- **Canonical link**: `<link rel="canonical" href="..."/>` presente; usar como `product_url`.

### JSON-LD

- **1 bloque** `<script type="application/ld+json">` observado (no 3 como decía spec §4 antigua — spec actualizada 2026-04-23).
- Tipos esperados dentro del block (puede ser array o @graph): `Product`, `BreadcrumbList`, `ImageGallery`.
- Campos clave del `Product`: `name`, `description`, `image`, `offers.price` (string), `offers.priceCurrency` (INR), `offers.availability`, `offers.seller.name`.

### Selectores DOM verificados

Probados con curl sobre fixture `22408594448` el 2026-04-23:

| Selector | Matchea | Valor ejemplo | Uso |
|---|---|---|---|
| `h1.center-heading` | ✓ | "Caustic Soda Flakes" | `product_name_original` fallback (JSON-LD primario) |
| `h2.fs15` | ✓ | "Vats International" | `supplier_name` fallback (JSON-LD primario) |
| `$('h2.fs15').closest('a').attr('href')` | ✓ | `https://www.indiamart.com/vatsinternational/?pid=...&cui=1` | raw href del supplier |
| `a:has(img.c_logo)` | ✓ (fallback) | — | alt para supplier href si h2 no lo envuelve |
| `.bo.price-unit` | ✓ | "₹ 50/" | price_raw (junto con `.units`) |
| `.units` | ✓ | "Kg" | price_unit fallback |
| `.addrs.plhn` | ✓ | bloque de dirección completo | NO usar directo (ambiguo) |
| `.verT.fs13` | ✓ pero **SEMÁNTICAMENTE ROTO** | "Verified Exporter Mobile E-Mail" | NO usar para city/state/country — no contiene esos datos |
| `a[href*="lighthouse-india"]` | ✗ NO MATCHEA | — | OBSOLETO. Removido de v2 (hotfix 2026-04-23) |
| `link[rel="canonical"]` | ✓ | URL canónica | `product_url` |
| `meta[property="og:image"]` | ✓ | URL imagen | `image_primary` fallback |
| `li.compdtsItems` | ✓ (audit analyst) | — | contenedor de `business_type`, `member_since_year` |
| `li.compdtsItems p.fs12.color1` | ✓ | label (ej. "Nature of Business") | label del compdtsItems |
| `li.compdtsItems h4.cmpfvalh4` | ✓ | value (ej. "Service Provider and Others") | value del compdtsItems |

### Supplier URL pattern

- Canonical: `https://www.indiamart.com/{supplier-slug}/` (directo, sin `lighthouse-india/`).
- Slug regex: `/^https?:\/\/www\.indiamart\.com\/([a-z0-9-]+)\/?(?:\?|$|#)/i`
- Ejemplo fixture: slug = `vatsinternational` (sin guión; §6 es autoritativo sobre §11 en caso de conflicto).

### Spec table auxiliar (§5)

Formato: `<table> <tr><td>{Label}</td><td>{Value}</td></tr> ... </table>`.

Labels observadas en fixture 22408594448: `Form` (Flakes), `Purity` (99%), `Grade` (Membrane Grade), `Purity %` (99%), `NaOH Concentration` (99%), `Application` (Soap And Detergent, ...), `Packaging Size` (25 kg), `Packaging Type` (Bag), `Grade Standard` (Industrial Grade), `Packaging Details` (50 Kg Bag), `Minimum Order Quantity` (20000 KG), `Availability` (In Stock).

Para químicos típicos esperar además: `CAS No` / `CAS Number`, `Appearance`, `Concentration`.

### Embedded JSON inline (fallback §5 / E5)

Regex-able sobre HTML raw (no DOM):

- `"PC_ITEM_MIN_ORDER_QUANTITY"\s*:\s*"([^"]*)"` — MOQ quantity
- `"PC_ITEM_MOQ_UNIT_TYPE"\s*:\s*"([^"]*)"` — MOQ unit
- `"FK_IM_SPEC_MASTER_DESC"\s*:\s*\[([^\]]*)\]` — array de labels (Grade, CAS No, Packaging, etc.)
- `"SUPPLIER_RESPONSE_DETAIL"\s*:\s*\[([^\]]*)\]` — array de values, índice paralelo a FK_IM_SPEC_MASTER_DESC

Usar cuando la spec table DOM no trae la fila (algunos templates B2B la omiten).

### Title format

`"{product} at {currency} {price}/{unit} | {category} in {CITY} | ID: {PID}"`

Ejemplo 22408594448: `"Caustic Soda Flakes at ₹ 50/kg | Caustic Soda in New Delhi | ID: 22408594448"`

Regex útiles:
- City: `\bin\s+([A-Z][A-Za-z\s]+?)\s*\|`
- Price block: `([₹$€£¥])\s*([\d,]+(?:\.\d+)?)(?:\s*-\s*([\d,]+(?:\.\d+)?))?\s*\/\s*([A-Za-z]+)`
- PID: `(\d{11,13})\.html$`

**Nota**: el title NO trae `state` ni `country`. Spec vieja §4 decía `"in {CITY}, {STATE}."` — es incorrecto. `supplier_state` se difiere a Stage 3 (supplier home).

### Badges (regex HTML raw, no DOM)

- `Verified\s+Exporter` → `verified = true`
- `TrustSEAL\s+Verified` → `trustseal = true`

(Selector `.slic .color1 span` devuelve "Mobile E-Mail" / "Contact Supplier", no los badges — NO usar.)

---

## Template: impcat listing (Stage 1 MCAT)

`last_verified: STALE — spec-only evidence, no curl verificado en 2026-04-23`

- **URL pattern**: `https://dir.indiamart.com/impcat/{slug}.html`
- **Fixture URLs** (spec §11): `impcat/caustic-soda.html`, `impcat/caustic-soda-pearl.html`, `impcat/caustic-soda-flakes.html`, `impcat/adhesive-chemical.html`, `impcat/industrial-drums.html`

### Selectores

- `a[href*="proddetail"]` → links a detail pages.
- Browser worker: **usar `$(sel).map((_, el) => ...).get()`**, no `.toArray()` (skill R12).
- Filtrar rutas Disallow (robots.txt): `/(pd|proddetail[12])/`

### Pagination

- NO existe `?page=N` (errors.md E3). El listing muestra top-N del MCAT.
- Discovery adicional via: subcats hijas (`caustic-soda-pearl.html`, etc.), sitemaps `dir.indiamart.com/*-sitemap*.xml`, supplier drill-down.

---

## Template: indianexporters hub (Stage 1 industry)

`last_verified: STALE — spec-only evidence`

- **URL pattern**: `https://dir.indiamart.com/indianexporters/ind_{industry}.html`
- **Fixture URLs** (spec §9): `ind_chem.html`, `ind_packaging.html`
- Enumera MCATs para la industria (hasta ~100 por spec §9).

### Variante `m_{abbr}.html` (hallazgo 2026-04-23)

- **URL pattern paralelo**: `https://dir.indiamart.com/indianexporters/m_{abbr}.html`
- Observado en links salidos de `dir.indiamart.com/industry/plant-machinery.html`: `m_miscel.html`, `m_prmach.html`.
- "m_" parece prefijo para sub-grupos de maquinaria/manufactura (distinto al `ind_` de industrias principales).
- Sin verificar directamente — se infieren por links visibles. Si se integran, verificar cada uno antes de usar como seed.

---

## Template: industry taxonomy index (dir, Stage 1b hub-of-hubs)

`last_verified: 2026-04-23`

- **URL pattern**: `https://dir.indiamart.com/industry/{slug}.html`
- **Fixture verificada**: `https://dir.indiamart.com/industry/plant-machinery.html` → HTTP 200, 20 KB, H1 "Industrial Plants & Machinery".
- **NO es un listing de productos**: no tiene proddetail links directos.
- **ES** un índice taxonómico: linkea a MCATs (`/impcat/{slug}.html`) y a hubs (`/indianexporters/m_{abbr}.html`).
- Renderizado: React SSR parcial (bundles JS: `main.bundle197.js`, `react.bundle197.js`). Los links importantes ya están en el SSR inicial, no requiere hidratación.
- Sin JSON-LD (no es product-level).
- Sin `<meta robots>` evidente en HTML inicial (verificar si hay Disallow para scrapers antes de integrar masivamente).

### Integración propuesta (backlog)

- Agregar Stage 1b que abre `dir/industry/{slug}.html`, extrae `a[href*="impcat"]` absolutizado, y encola como seeds del Stage 1 actual.
- Ganancia: 1 seed-de-industria se expande a ~30-100 MCATs automáticamente, sin ampliar manualmente `DEFAULT_MCAT_SLUGS`.
- Candidatas útiles para Genomma Lab: `chemicals-fertilizers.html`, `packaging-material.html`, `plant-machinery.html` (maquinaria de producción), `drugs-medicines.html` (farma).

---

## Template: m.indiamart.com alternate (mobile)

`last_verified: STALE — solo observado como link desde dir`

- **URL pattern**: `https://m.indiamart.com/dir/{slug}.html/` (con trailing slash)
- Variante mobile-first servida por IndiaMART a browsers móviles. Contenido equivalente al `dir` pero con markup adaptado.
- No verificado en curl directo; aparece como `<link rel="alternate" media="only screen and (max-width: 640px)">` en `dir/industry/*.html`.
- Potencialmente útil como fallback si el proxy residencial IN de BrightData es bloqueado en `dir` pero no en `m`. No probado.

---

## Template: export.indiamart.com (subdominio exporters-only, Stage 3 discovery alt)

`last_verified: 2026-04-23`

- **Subdominio separado** del `www` y `dir`. Focalizado solo en Verified Exporters (suppliers que exportan internacionalmente, subset premium de los que aparecen en `dir/impcat/`).
- **robots meta**: `index, follow` (sin Disallow).
- HTTP 200, gzip, SSR completo.

### URL patterns

| Tipo | Pattern | Qué devuelve |
|---|---|---|
| Home | `https://export.indiamart.com/?VElogo=1` | Portal con 39 industries + countries + top search links |
| Industry | `https://export.indiamart.com/industry/{slug}/` | Lista de search-links + h3 de subcategorías. **NO trae proddetail directo.** Slugs distintos al `dir/indianexporters/ind_{cat}.html` |
| Country | `https://export.indiamart.com/country/{country}-exports/` | Exportadores filtrados por mercado destino (china, uae, usa, etc.) |
| Search | `https://export.indiamart.com/search.php?ss={query}` | **Lista de supplier homes** (NOT proddetail). h1 literal: "Verified Exporters for {query}" |
| Quote | `https://export.indiamart.com/get-quote/?ss={query}` | RFQ form (no útil para scraping precios) |

### Slugs de industry relevantes (para química/packaging)

- `chemicals-fertilizers/` (equivalente a `ind_chem.html` del dir pero distinta convención)
- `packaging-material/` (eq. `ind_packaging.html`)
- `drugs-medicines/`, `cosmetics-toiletries/`, `ores-metals/`, `paper/`

### Search result structure (confirmado con `ss=Hydrochloric+Acid`)

- h1: `Verified Exporters for {product}` ← literal, flag `verified_exporter=true` implícito para todos los resultados.
- Cards de supplier linkeando a `https://www.indiamart.com/{supplier-slug}/` (supplier homes del dominio `www`).
- **NO hay proddetail links en search results** — hay que visitar cada supplier home y scrapear su catálogo.

### JSON-LD

- 2 blocks en home (WebSite, Organization, WebPage, SearchAction, ContactPoint, BreadcrumbList, AggregateRating, ItemList, ImageObject, SpeakableSpecification, EntryPoint, ListItem) — level marketing, NO Product.
- Search page: JSON-LD tipo `@type` no detectado en check rápido.

### Cuándo usar este subdominio (backlog)

- **NO integrar en Stage 1 actual**: no agrega proddetail directos, duplica el flow con 2 hops extras.
- **SÍ integrar en Stage 3 (supplier enrichment, spec §12)**: cuando toquemos suppliers, esta via da solo verified-exporters con filtro gratis. Entrar por `search.php?ss={product}` → supplier home → catálogo → proddetail es equivalente en data final al flow del `dir`, pero con pre-filtro de calidad.
- Señal única: `/country/{mercado}-exports/` es la única forma de filtrar exportadores por mercado destino en todo el sitio.

---

## Template: supplier home (Stage 3 enrichment, pendiente)

`last_verified: STALE — nunca curl-verificado, datos inferidos de spec §6`

- **URL pattern**: `https://www.indiamart.com/{supplier-slug}/`
- Fuente canónica de: `supplier_state`, `supplier_city` (formato largo), `year_established`, `annual_turnover`, `certifications`, `gst`, `import_export_code`.
- No implementado en Stage 2 actual — los 4 campos de supplier que hoy se embeben en product row (`supplier_name`, `supplier_id`, `supplier_city`, `supplier_country=IN`) salen del detail; el resto de §6 va a Stage 3 (backlog §12 de la spec).

---

## Sitemaps útiles

Listados en `dir.indiamart.com/robots.txt`:

- `https://dir.indiamart.com/impcat-mcat-sitemap.xml`
- `https://dir.indiamart.com/impcat-pmcat-sitemap.xml`
- `https://dir.indiamart.com/items/stdprd-sitemap.xml`
- `https://dir.indiamart.com/city-mcat-bizR-sitemap01.xml`
- `https://dir.indiamart.com/city-mcat-bizM-sitemap01.xml`
- `https://dir.indiamart.com/IndExpoSer-sitemap.xml`

---

## Staleness policy

- **Re-verificar** cualquier sección si pasan >30 días desde `last_verified`.
- **Cualquier parse-error en un run real** → marcar la sección afectada `STALE` en su header antes del siguiente fix.
- **Cuando se verifica**, actualizar `last_verified: YYYY-MM-DD` + diff explícito si algo cambió.
- **Nunca borrar entradas**: si un selector deja de matchear, marcarlo `OBSOLETO` con fecha. El historial es útil para detectar drift recurrente.
