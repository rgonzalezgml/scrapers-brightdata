# cosmetics-design — registry

Mapa de iteraciones del scraper: archivo versionado → JSON producido → notas.

Spec canonico: `/workspace/docs/specs/scrapers/cosmetics-design.md`.
Vendor (v0, READ-ONLY): `/workspace/scrapers/cosmetics-design/vendor/`.

## Versiones

| Version | Modo         | Archivos                                                                                                                                         | Fecha       | Result JSON                      | Notas |
|---------|--------------|--------------------------------------------------------------------------------------------------------------------------------------------------|-------------|----------------------------------|-------|
| v0      | sc_browser + sc_code | `vendor/sc_browser/interaction_code.js`, `vendor/sc_browser/parser_code.js`, `vendor/sc_code/interaction_code.js`, `vendor/sc_code/parser_code.js` | pre-2026-04-21 | `results/j_mo8omwb11xys1f1359.json` | Entrega de DB AI. 50 filas. Campos fuera de contrato §2 (authors, word_count, primary_section, sections, description_basic, flags booleanos sueltos, sin website/supplier/subtype/scraped_date/slug/publish_date/last_updated_date/promo_image_url). Sin filtro cross-promo. `max_clicks=10` hardcoded. Paywalled via selector generico `.paywall`. |
| v1      | sc_browser + sc_code | `sc_browser/interaction_code_v1.js`, `sc_browser/parser_code_v1.js`, `sc_code/interaction_code_v1.js`, `sc_code/parser_code_v1.js` | 2026-04-21  | _pendiente de run_               | Bootstrap desde vendor + cierre gaps §4 (campos faltantes, website, supplier, subtype, dates, scraper_flags como lista, filtro cross-promo, input max_pages/supplier). |

## Changelog por version

### v1 (2026-04-21)

Fuente: bootstrap verbatim desde `vendor/` + iteracion sobre esas copias.

Cambios aplicados:

- **`sc_browser/interaction_code_v1.js`**:
  - Input runtime `max_pages` (default -1 = sin limite) reemplaza hardcode `max_clicks = 10`.
  - Input runtime `supplier` (default "William Reed") se propaga al stage de detalle via `next_stage({url, supplier})`.
- **`sc_browser/parser_code_v1.js`**:
  - Filtro cross-promo: descarta URLs cuyo pathname empieza con `/Product-innovations/` o `/Events/` (spec §3).
  - Log del conteo descartado.
- **`sc_code/interaction_code_v1.js`**:
  - SKIP via `dead_page()` cuando `status_code()` es 404 o 410 (spec §8).
- **`sc_code/parser_code_v1.js`**: reescritura completa para cumplir contrato §2 + §4.
  - Fuente primaria: `window.Fusion.globalContent` parseado con conteo de llaves.
  - Selectores DOM del vendor mantenidos como fallback.
  - `article_id` desde `Fusion._id` (no regex del URL).
  - Campos §2 completos: `article_id`, `url`, `slug`, `headline`, `display_date`, `publish_date`, `last_updated_date`, `website` (fijo `"nutraingredients-v2"`), `supplier` (de input), `subtype`, `author_names`, `primary_section_path`, `section_paths`, `region_tags`, `topic_tags`, `body_text`, `body_word_count`, `promo_image_url`, `paywalled`, `scraped_date`.
  - Campos §4 adicionales: `subheadline`, `description`, `author_slugs`, `promo_image_caption`, `first_publish_date`, `scraper_flags` (lista).
  - `body_text`: concatena `content_elements` `type=text`/`header` con `\n\n`; skip `image`/`divider`/`video`/`list`. Strip `<em>/<b>/<i>/<strong>/<a>`.
  - `region_tags`: `section_paths` con prefijo `/Regions/` (strip).
  - `topic_tags`: `section_paths` con `navigation.type === 'news'` (slug del ultimo segmento).
  - `paywalled`: `article_content_type === 'metered' && paywall_hit === true`.
  - `scraper_flags`: lista de strings segun triggers (`paywalled`, `date_future`, `region_missing`, `body_fallback_html`, `fusion_parse_fallback`, `consent_wall_retried`).
  - `scraped_date`: `YYYY-MM-DD` UTC del runtime.

Pendiente de confirmar con run:

- Que el `fullHtml` via `$.root().html()` contiene el bloque `Fusion.globalContent` (Arc XP lo inyecta inline en un `<script>`; esperado que si).
- Mapeo exacto de `navigation.type` (spec dice `news`, hay que ver cual es el valor real del CMS para secciones topic vs region).
- Comportamiento del `status_code()` en sc_code cuando el 404 cae tras redirect.
