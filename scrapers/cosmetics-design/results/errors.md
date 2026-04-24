# cosmetics-design — errors (site-specific)

Gotchas del sitio `nutraingredients.com` y del scraper `cosmetics-design`.
Memoria del proyecto: `/workspace/docs/specs/memory.md` §"Errores y gotchas — dos niveles".

Runtime errors cross-scraper en `/workspace/docs/specs/brightdata-errors.md` (R1..RN).
Aqui solo lo especifico de este sitio.

---

## E1 — Vendor v0 usa campos fuera del contrato §2

**Version afectada**: v0 (vendor, entrega DB AI).

**Sintoma**: el JSON `results/j_mo8omwb11xys1f1359.json` emite 20 campos, pero no coinciden con §2 del spec:

- Nombres mal: `authors` (debe ser `author_names`), `word_count` (debe ser `body_word_count`), `primary_section` (debe ser `primary_section_path`), `sections` (debe ser `section_paths`), `description_basic` (debe ser `description`).
- Faltantes: `slug`, `publish_date`, `last_updated_date`, `website`, `supplier`, `subtype`, `promo_image_url`, `scraped_date`.
- Flags booleanos sueltos (`date_future`, `region_missing`, `body_fallback_html`, `fusion_parse_fallback`, `consent_wall_retried`, `paywalled`) en lugar de `scraper_flags: string[]` (§8).

**Causa**: DB AI genero andamiaje sin leer §2/§4/§8 con precision; uso selectores DOM en vez de `Fusion.globalContent` (§5).

**Fix**: reescritura completa en `sc_code/parser_code_v1.js` con contrato §2 + §4.

---

## E2 — Vendor v0 ignora cross-promo paths

**Version afectada**: v0.

**Sintoma**: `sc_browser/parser_code.js` no filtra URLs `/Product-innovations/` ni `/Events/`, pese a que §3 dice "Ignorar `/Product-innovations/`, `/Events/` (cross-promo)".

**Causa**: omision en el andamiaje DB AI.

**Fix**: `sc_browser/parser_code_v1.js` aplica `filter()` sobre `pathname.indexOf('/Product-innovations/') === 0 || '/Events/'`.

---

## E3 — Vendor v0 hardcodea cap de paginacion (max_clicks=10)

**Version afectada**: v0.

**Sintoma**: `sc_browser/interaction_code.js` hardcodea `let max_clicks = 10`. §7 del spec y §10 exigen que sea input runtime `max_pages` con default `-1` (sin limite).

**Fix**: `sc_browser/interaction_code_v1.js` lee `input.max_pages` con default `-1`. `-1` = loop hasta que el boton desaparezca. `>=0` = cap de clicks.

---

## E4 — Vendor v0 deriva article_id del slug de URL (no del `_id` de Fusion)

**Version afectada**: v0.

**Sintoma**: `sc_code/parser_code.js` hace `urlMatch[1]` del URL `/Article/YYYY/MM/DD/{slug}/` y emite el slug como `article_id`. §4 del spec dice explicitamente "article_id string (tomar _id del JSON Fusion)".

**Fix**: `sc_code/parser_code_v1.js` lee `fusion._id`.

---

## E5 — Vendor v0 detecta paywall con selector generico .paywall

**Version afectada**: v0.

**Sintoma**: `paywalled = $('.paywall, [class*="paywall"], [class*="subscription-required"]').length > 0`. Trigger falsos (50/50 filas emitidas con `paywalled: true`). §2 spec: `article_content_type === 'metered' && paywall_hit === true`.

**Fix**: `sc_code/parser_code_v1.js` usa los dos campos explicitos del Fusion.

---

## Patrones candidatos (a confirmar tras run v1)

- `Fusion.globalContent` puede venir como `window.Fusion.globalContent=` (sin espacios) o con espacios variables; el parser v1 busca el substring literal `Fusion.globalContent` y luego el primer `{`. Confirmar en run real.
- `navigation.type` del CMS — §6 spec dice `'news'`; hay que ver si el valor real es ese exacto o variaciones.
- Subtypes observados: `news_text`, `news_video`. Confirmar que Fusion expone en `.subtype` directo.
- `first_publish_date` emitido como campo §4 pero NO esta en §2; confirmar si downstream (middleware) lo tolera.
