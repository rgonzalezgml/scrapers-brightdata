# Results registry — made-in-china

Mapa de cada archivo de resultado de scraping a la versión del scraper que lo produjo. Se actualiza cada vez que se descarga un nuevo resultado al folder `results/`.

## Convención

- `v0` = `vendor/` (original DB AI, sin cambios).
- `v1`, `v2`, ... = iteraciones nuestras en `sc_browser/` y `sc_code/` (`*_vN.js`).
- Archivo de resultado: naming sugerido `mic_{entidad}_{YYYYMMDD_HHMMSS}.json` o `{YYYYMMDD}_{fixture}_{vN}.json`.
- Modo: `sc_browser` o `sc_code` (o `both` si corrió ambos).

## Registro

| Fecha | Archivo | Versión | Modo | Fixture / URL | Notas |
|-------|---------|---------|------|----------------|-------|
| 2026-04-21 15:53 | _(sin JSON — error antes de emitir)_ | v1 | sc_browser | TBD | Crawler error: `wait('.search-list .list-node')` timeout 30000ms. **E9-E11 identificados**, fixeados en v2. |
| _(esperando run de v2)_ | | v2 | sc_browser | | |
| _(superseded by v4 — E12 fix)_ | | v3 (interaction) + v2 (parser) | sc_browser | | Agrega `max_pages` (-1=all, N>0=cap) + `current_page` propagado en rerun (spec §9). Parser sin cambios vs v2. **Superseded**: parser v2 tiene E12 (next_page_url malformada con href protocol-relative) → usar combinación v3 + parser v4. |
| _(superseded by v5 — parallel pagination)_ | | v3 (interaction) + v4 (parser) | sc_browser | | Fix E12: helper `absolutize` para href protocol-relative (`//www.made-in-china.com/...`) en `next_page_url`, `product_urls`, `supplier_urls`. Interaction v3 sin cambios (lógica `max_pages` vigente). **Superseded**: paginación secuencial reemplazada por fan-out paralelo desde página 1 (ver v5). |
| _(esperando run de v5)_ | | v5 (interaction) + v5 (parser) | sc_browser | | Paginación **paralela** (spec §9): parser emite `total_pages` desde `span.page-total`; interaction calcula `cap = max_pages===-1 ? total_pages : min(max_pages,total_pages)` y encola `rerun_stage` para páginas 2..cap desde página 1 usando helper `buildPageUrl(next_page_url, N)` (sustitución de `-{N}.html` final). Reruns solo extraen product/supplier URLs, no re-encolan. Preserva E9/E10/E11/E12. |
| _(pendiente de run)_ | | v5 (interaction) + v6 (parser) | sc_browser | 12 seeds via-2 catalog (Alkali, Acid, Organic-Intermediate, Ester-Derivative, Essential-Oil-Balsam-Fine-Chemicals, Surface-Disposal-Agent, Fungicide-Bactericide, Inorganic-Chemicals, Packaging-Materials, Stretch-Film, Packaging-Barrels-Buckets, Woven-Bag) | **Fix E17**: product_links y supplier_links amplían selector de `.prod-item` a union `.prod-item/.list-node/.products-item` para cubrir tarjetas via-2 catalog del modo primario v6. Interaction v5 sin cambios. Preserva todos los fixes E9/E10/E11/E12 de versiones anteriores. |
| _(superseded by sc_code v2 — E1-E8, E13-E16 fixed)_ | | v1 | sc_code | copia verbatim de vendor | Culpable probable del "output vacío" observado: selectores inexistentes (E13 `.J-baseInfo-name`, E14 `.info-label`/`.info-fields`, E15 segunda clase `.only-one-priceNum-price`), `category_mic` hardcoded a "Oxide" (E1), `price_unit` del MOQ (E2), `supplier_country` no ISO-2 (E3), `supplier_audited` por image src (E4), `new URL()` como retorno (E5), `new Money()` sin confirmar runtime (E6), `business_type` solo `.first()` (E7), product+supplier mezclados en un collect (E8), JSON-LD ignorado aunque spec §4 lo declara autoritativo (E16). **Superseded por sc_code v2**. |
| _(superseded by v3 — E5/E6 reverted, §2 alignment)_ | | v2 | sc_code | product detail `IEFUtrGOCdRZ` + supplier home `whjindo` | Reescritura completa del parser: JSON-LD Product como fuente primaria (E16), DOM como fallback/complemento. Branching product vs supplier por path `/product/` en URL (E8) — emite `__entity` marker + single-record `collect()`. Fixes aplicados: E1 breadcrumb DOM `.sr-QPWords-cont a`, E2 price_unit del priceText con regex, E3 mapa COUNTRY_ISO + flag `country_iso_unknown`, E4 texto literal "Audited Supplier" en sign-items/bsc-items, E5 `url: input.url` string, E6 números puros sin `new Money()`, E7 combina todos los sign-items con regex, E8 branching por entidad, E13 `.sr-proMainInfo-baseInfoH1` pelado + fallback JSON-LD, E14 `supplier_country` solo en rama supplier home, E15 `.sa-only-property-price` simple + regex spec §7, E16 JSON-LD-first. Respeta R7/R9/R11/R12. Interaction v2 agrega guard 404/410 → dead_page y parser_skip → dead_page. **Superseded by v3** (sc_code): schema BD Studio requiere `new URL(...)` para tipo URL y `new Money(...)` para tipo Price/Money — E5 y E6 estaban mal diagnosticados en errors.md y fueron revertidos en v3; además §2 fue corregido al superset de 29 product + 14 supplier campos con nombres largos, v3 se alinea a ese §2. |
| _(esperando run de v3)_ | | v3 (parser) + v3 (interaction) | sc_code | product detail `IEFUtrGOCdRZ` + supplier home `whjindo` | **Restaura wrappers del Output Schema BD Studio** (E5/E6 revertidos por false-positive — ver errors.md Corrección 2026-04-21): `product_url`/`supplier_url` → `new URL(value)`; `price_min_usd`/`price_max_usd`/`price_normalized_per_kg` → `new Money(value, currency)`. **Alineado al §2 corregido**: 29 campos product + 14 supplier con nombres largos (`product_url`, `product_name_clean`, `supplier_name`, etc.); orden de claves matchea arrays del §2. Eliminado `__entity` marker (§2 no lo declara); el interaction no lo necesita porque `collect(data)` es pass-through. Eliminado campo duplicado `url` de la rama product. Preserva todos los fixes semánticos de v2 (E1, E2, E3, E4, E7, E8, E13, E14, E15, E16). Interaction v3: quita guard `data.__skip` obsoleta (parser ya no emite el marker); mantiene status-check 404/410 → dead_page y cortafuego `!data` → dead_page. |

| _(pendiente de run)_ | | v6 (interaction) + v7 (parser) | sc_browser | 12 seeds via-2 catalog + via-1 search | **Fix E18**: wait ampliado a `.search-list, .list-node, .products-item, .prod-item`; .search-list es el wrapper SSR más fiable para ambas variantes. **Fix E19**: supplier fan-out eliminado; interaction no emite next_stage para suppliers; parser v7 no calcula supplier_urls. Parser v7 usa `.map((_, el) => ...).get()` (R12, portable Browser+Code). |

## Cómo llenar

Cada vez que bajes un resultado:

1. Poné el JSON en `scrapers/made-in-china/results/` con nombre descriptivo.
2. Agregá una fila a la tabla arriba con: fecha, filename, versión (`v1`), modo (`sc_browser`/`sc_code`), URL fixture, notas (qué gaps del schema se cerraron, qué sigue roto, etc.).
3. Si la misma versión produjo varios resultados (varios fixtures), una fila por archivo.
