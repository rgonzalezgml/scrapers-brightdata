# indiamart parser v3 — handoff Fase 2

**Destino**: agente `analista-de-scrapers`.
**Scope**: refactor JSON-LD-primero del Stage 2 detail parser.
**Archivo a crear**: `/workspace/scrapers/indiamart/sc_code/parser_code_v3.js`.
**NO tocar**: `sc_code/parser_code_v2.js` (baseline revertible), `sc_code/interaction_code_v2.js`, `sc_browser/*`, `middlewares/indiamart/*`.

Fecha handoff: 2026-04-23. Tech Lead: claude orquestador.

---

## 1. Contexto

- Stage 1 (listing, `sc_browser/*_v2.js`) está sano y emite URLs `/proddetail/{slug}-{PID}.html`.
- Middleware (`middlewares/indiamart/client.py`) está sano: ya no fuerza seeds, los 49 tests verdes, 2 skip (live BrightData). Baseline confirmado hoy 2026-04-23.
- Hotfix commit reciente en `sc_code/parser_code_v2.js`: solo fix del selector obsoleto `a[href*="lighthouse-india"]` → `$('h2.fs15').closest('a')`. El resto es vendor v1 = contiene bugs legacy documentados abajo.
- Spec fuente: `docs/specs/scrapers/indiamart.md`. Actualizada en este handoff (§4, §5, §6, §11 reescritos; §12 backlog Fase 2 agregado).

---

## 2. Evidencia recolectada (curl 2026-04-23)

Fixture canonical: `https://www.indiamart.com/proddetail/caustic-soda-flakes-22408594448.html` (58 KB HTML SSR).

### JSON-LD (3 bloques confirmados)

```
[0] @type=BreadcrumbList
    position=1 IndiaMART
    position=2 "Industrial Chemicals & Supplies"  @id=/indianexporters/ind_chem.html
    position=3 "Chemical Compound"                @id=/impcat/chemical-compound.html
    position=4 "Caustic Soda"                     @id=/impcat/caustic-soda.html
[1] @type=ImageGallery  (no usado por parser hoy)
[2] @type=Product
    name="Caustic Soda Flakes"
    offers.price="50"
    offers.priceCurrency="INR"
    offers.seller.name="Vats International"
    image="https://5.imimg.com/data5/SELLER/Default/.../caustic-soda-500x500.jpg"
    description="Vats International imparts a qualitative array..."
```

> Crítico: `$('script[type="application/ld+json"]').html()` sin `.each()` devuelve **solo el primero** (BreadcrumbList). El vendor v1 hace eso y aplica lógica "if @type==='BreadcrumbList'"; por eso Product no se parsea jamás.

### Embedded JSON inline (spec table ausente para MOQ en este fixture)

```
PC_ITEM_MOQ_UNIT_TYPE:      "Kg"
PC_ITEM_MIN_ORDER_QUANTITY: ""           ← el fixture tiene el value vacío en ese campo
FK_IM_SPEC_MASTER_DESC:     ["Form", "Purity", "Grade", "Purity %", "NaOH Concentration"]
SUPPLIER_RESPONSE_DETAIL:   ["Flakes", "99%", "Membrane Grade", "99%", "99%"]
```

> Observación: la spec table HTML de este fixture NO trae fila `Minimum Order Quantity`. Sí trae Form=Flakes, Purity=99%, Grade=Membrane Grade, NaOH Concentration=99%. Parser v3 debe leer AMBAS fuentes (spec table y embedded JSON) y pegarse al orden de fallback de §5.

### Supplier href real

El `<a>` que envuelve a `<h2 class="fs15">Vats International</h2>` apunta a:

```
https://www.indiamart.com/vatsinternational/?pid=22408594448&c_id=132&mid=3630&pn=Caustic Soda Flakes&cui=1
```

→ slug = `vatsinternational` (un token, **sin guión**). canonical url = `https://www.indiamart.com/vatsinternational/`.

### Title del detail

```
<title>Caustic Soda Flakes at ₹ 50/kg | Caustic Soda in New Delhi | ID: 22408594448</title>
```

Formato real: `"... in {CITY} | ID: {PID}"`. **NO trae state** (la spec vieja decía `"in {CITY}, {STATE}."` — era incorrecta, corregida en §4/§6). `.verT.fs13` en este fixture solo trae `"New Delhi"` también. `.addrs.plhn` viene vacío en SSR.

### Supplier profile — compdtsItems (NO company-details-grid)

Selector vendor `.company-details-grid dt/dd` = **obsoleto, NO existe en DOM actual**. El DOM real:

```html
<li class="compdtsItems">
  <p class="fs12 color1">{Label}</p>
  <h4 class="cmpfvalh4">{Value}</h4>
</li>
```

Labels observados en fixture §11:
- `"Legal Status of Firm"` → `Proprietorship`
- `"GST Registration Date"` → `Jul 2017`
- `"Annual Turnover"` → `40 L - 1.5 Cr`
- `"Indiamart Member Since"` → `Mar 2002` (OJO: `"Indiamart"` minúscula en el DOM, regex case-insensitive)

En este fixture **NO** hay label `"Nature of Business"` → `business_type` debe quedar null + flag.

### Badges

- `"Verified Exporter"` presente en HTML → `verified=true`.
- `"TrustSEAL Verified"` **NO presente** en fixture §11 → `trustseal=false`. (La fixture middleware actual dice `trustseal=true` — se resincroniza.)

---

## 3. Bugs v2 → fixes v3 (mapeo 1:1)

| Campo | v2 (bug) | v3 (fix) | Spec |
|---|---|---|---|
| `type` | `$('table tbody tr:has(td:contains("Bulb Type")) td.tdwdt1')` (lámparas, no chem) | BreadcrumbList[position=2].@id regex `ind_chem`/`ind_packaging` → `chemical`/`packaging`/`other` | §4 / §8 |
| `category_path` | `.html()` del primer script JSON-LD, asume BreadcrumbList (frágil, pierde si orden cambia) | Iterar 3 bloques, filtrar por `@type==='BreadcrumbList'`, map itemListElement[1:].item.name | §4 |
| `supplier_city` | `$('.addrs.plhn').text_sane()` (SSR vacío) | regex `\bin\s+([A-Z][a-zA-Z\s]+?)\s*\|` sobre `<title>`; fallback `.verT.fs13` primer token | §4 / §7 |
| `supplier_state` | `$('.verT.fs13').split(',')[1]` (rompe: `.verT.fs13` solo trae city, no devuelve 3 partes) | `null` + flag `supplier_state_from_home_needed` | §4 / §6 |
| `supplier_country` | `split(',')[2]` (undefined) | string literal `"IN"` | §4 |
| `business_type` | `.company-details-grid div:has(dt:contains("Nature of Business")) dd` (selector obsoleto) | `li.compdtsItems:has(p:contains("Nature of Business")) h4.cmpfvalh4` — null si label ausente | §6 |
| `member_since_year` | `.company-details-grid div:has(dt:contains("IndiaMART Member Since")) dd` (obsoleto + case) | `li.compdtsItems:has(p:matches(/indiamart member since/i)) h4.cmpfvalh4` → regex `(\d{4})` sobre value | §6 |
| `verified` | `$('.slic').length > 0` (laxo, cualquier `.slic` da true) | `/Verified Exporter/i.test(raw_html)` literal | §6 |
| `trustseal` | `$('.slic .color1 span').text_sane()` (devuelve `"Mobile E-Mail"`) | `/TrustSEAL Verified/i.test(raw_html)` bool | §6 |
| `supplier_id` | OK tras hotfix (slug del href normalizado) | idem — regla §6 autoritaria, `vatsinternational` sin guión | §6 |

---

## 4. Campos nuevos obligatorios (§4/§5 completos)

v2 emite 20 fields del vendor. v3 debe emitir schema `product` completo de §4+§5:

```
product_id, site_code="indiamart", product_url, product_name_original, product_name_clean,
product_description, image_primary, type, category_mic, category_path, industry_slug,
price_raw, price_currency, price_value_raw, price_min_usd, price_max_usd, price_unit,
price_normalized_per_kg, availability, moq_quantity, moq_unit,
supplier_id, supplier_name, supplier_city, supplier_state, supplier_country,
cas_no, grade, appearance, packaging_type, concentration,
scraped_date, scraper_flags[]
```

Todos con null explícito cuando falten (§5: "nunca omitir la clave"). `category_path` y `scraper_flags` siempre arrays (nunca null).

---

## 5. Patrón de implementación recomendado (DSL Scraper Studio)

```js
// parser_code_v3.js — IndiaMART Stage 2 detail. JSON-LD primero.

// Helper: parse los N bloques JSON-LD, retorna dict por @type
const lds = $('script[type="application/ld+json"]').toArray()
  .map(el => { try { return JSON.parse($(el).html()); } catch { return null; } })
  .filter(Boolean)
  .flatMap(x => Array.isArray(x) ? x : [x]);

const breadcrumb = lds.find(x => x?.['@type'] === 'BreadcrumbList');
const product_ld = lds.find(x => x?.['@type'] === 'Product');

// ...extracción...

// MOQ: spec table primero, embedded JSON fallback
const raw_html = $.html();  // HTML completo para regex sobre embedded JSON

// Badges: literal en HTML crudo
const verified = /Verified Exporter/i.test(raw_html);
const trustseal = /TrustSEAL Verified/i.test(raw_html);

// ...resto...
```

Orden sugerido de bloques dentro del parser:
1. Parse 3 JSON-LD blocks → variables `breadcrumb`, `product_ld`, (image_gallery opcional).
2. product_id desde input.url regex.
3. name_original / description / image_primary desde `product_ld`.
4. category_path / category_mic / industry_slug / type desde `breadcrumb`.
5. price_* desde `product_ld.offers` + título para price_raw.
6. MOQ: spec table → fallback embedded JSON regex.
7. Specs auxiliares (CAS, grade, appearance, packaging_type, concentration) desde spec table.
8. supplier_id / supplier_url / supplier_name desde href del wrapper de `h2.fs15` (patrón ya probado en v2).
9. supplier_city desde título regex.
10. verified / trustseal desde HTML raw.
11. scraped_date = UTC hoy ISO date (YYYY-MM-DD).
12. scraper_flags acumulado durante todo el parse.
13. Return dict único (entity product; supplier queda para Fase 3).

---

## 6. Criterios de aceptación (test de la fixture §11)

Ejecutar parser v3 contra `/proddetail/caustic-soda-flakes-22408594448.html` debe emitir:

```json
{
  "product_id": "22408594448",
  "site_code": "indiamart",
  "product_url": "https://www.indiamart.com/proddetail/caustic-soda-flakes-22408594448.html",
  "product_name_original": "Caustic Soda Flakes",
  "product_description": "Vats International imparts a qualitative array...",  // truncar 500
  "image_primary": "https://5.imimg.com/data5/SELLER/Default/.../caustic-soda-500x500.jpg",
  "type": "chemical",
  "category_mic": "Caustic Soda",
  "category_path": ["Industrial Chemicals & Supplies", "Chemical Compound", "Caustic Soda"],
  "industry_slug": "chem",
  "price_currency": "INR",
  "price_value_raw": "50",
  "price_unit": "kg",
  "moq_quantity": 20000,     // desde embedded JSON fallback
  "moq_unit": "kg",
  "supplier_id": "vatsinternational",  // sin guión, slug crudo del href
  "supplier_name": "Vats International",
  "supplier_city": "New Delhi",
  "supplier_state": null,    // flag supplier_state_from_home_needed
  "supplier_country": "IN",
  "appearance": "Flakes",
  "concentration": "99%",
  "grade": "Membrane Grade",
  "verified": true,
  "trustseal": false,        // NO presente en HTML de este fixture
  "scraper_flags": ["supplier_state_from_home_needed", "moq_from_embedded_json", "supplier_enrichment_pending"]
}
```

---

## 7. Post-implementación (responsabilidad del orquestador, no del agente)

Después de que el agente entregue `parser_code_v3.js`:

1. Resincronizar fixture `middlewares/indiamart/tests/fixtures/indiamart_snapshot_s_demo01.json`:
   - `supplier_id: "vatsinternational"` (era `vats-international`).
   - `supplier_state: null` + flag `supplier_state_from_home_needed`.
   - `trustseal: false` en product 22408594448 (en supplier aparte puede mantenerse según spec §6 literal check).
2. Actualizar test `test_fixture_obligatorio_spec11` en `middlewares/indiamart/tests/test_client.py`:
   - `assert prod["supplier_id"] == "vatsinternational"`.
   - `assert prod["supplier_state"] is None`.
3. Correr `python -m pytest middlewares/indiamart/tests/ -q` — deben seguir 49 passed.
4. Usuario sube `parser_code_v3.js` al dashboard de BrightData (manual, fuera de scope del agente).

---

## 8. Restricciones duras para el agente

- **NO tocar `parser_code_v2.js`**: queda como baseline revertible (convención memoria `feedback_scraper_versioning.md`).
- **NO tocar `interaction_code_v2.js`**: los guards están bien alineados con §3 y con invariantes. Si el agente detecta algún gap menor en interaction, documentarlo y NO implementarlo en este ticket.
- **NO tocar middleware**: shape de rows se mantiene; cambios van en fixture + test en el mismo commit del orquestador post-handoff.
- **NO emitir entidad `supplier`**: Stage 2 emite solo `product` con supplier_* embedded. Supplier entity completa es Fase 3.
- **NO usar try/catch para esconder parse errors**: usar optional chaining `?.` + default null (R7 de `scraper-implementation`).
- **NO inventar campos** fuera del catálogo §4/§5.
- **Flags permitidos** solo los de §9: `route_disallowed, currency_unexpected, price_unit_unknown, moq_missing, supplier_location_missing, supplier_profile_missing, spec_table_missing, name_clean_fallback, jsonld_parse_fallback, breadcrumb_missing, blocked, blocked_retried, rate_limit_blocked` + los tres nuevos: `supplier_state_from_home_needed`, `moq_from_embedded_json`, `supplier_enrichment_pending`. Agregar los nuevos a §9 si el agente los usa.

---

## 9. Entregable esperado

1. `/workspace/scrapers/indiamart/sc_code/parser_code_v3.js` — parser completo JSON-LD-primero cubriendo §4 + §5.
2. Comentario header del archivo explicando diff semántico vs v2 (qué gap cierra cada bloque).
3. Report breve al orquestador con:
   - Lista de campos nuevos emitidos.
   - Lista de bugs v2 cerrados (referenciando tabla §3 del handoff).
   - Gaps que quedan fuera de scope (price range del title, supplier entity, Stage 3).
