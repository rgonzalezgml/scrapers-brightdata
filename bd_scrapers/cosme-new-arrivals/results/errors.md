# cosme-new-arrivals — errors.md

Catálogo de bugs específicos del sitio y del scraper.
Formato: E{N} | versión afectada | síntoma | causa | fix aplicado.

---

## E1 | v1 (sc_code) | "didn't collect anything" en preview de BrightData

**Síntoma**: Stage 1 o Stage 2 no colectan nada. BrightData preview reporta "didn't collect anything".

**Causa (dos sub-causas encadenadas)**:

1. `year`/`month` siempre `null` en Stage 1 cuando `input.url` es la URL corta `https://www.cosme.net/calendar/` (sin `/year/YYYY/month/MM` en el path). El parser v1 solo extraía year/month del regex sobre `input.url` y de `input.year`/`input.month`. Cuando la URL corta redirige a `/calendar/index/year/2026/month/05`, esa URL final solo es accesible via `location.href` en el parser — no via `input.url`.

2. Consecuencia en `next_stage`: los campos `year` y `month` propagados a Stage 2 eran `null`. En Stage 2 el parser sí podía extraerlos del path de la URL del día (que siempre tiene el formato completo), pero si por algún motivo ese path tampoco estaba disponible, `release_date` quedaba `null`.

3. Sub-causa adicional (sin fallback): si `location.href` tampoco tiene año/mes (redirect opaco), no había ningún mecanismo para recuperar esa información.

**Fix aplicado en v2**:

- `parser_code_v2.js` Stage 1: extrae year/month de `location.href` (URL real del Code worker tras redirect) antes de intentar `input.url`. Si ambos fallan, extrae del primer `href` de link de día encontrado en la tabla (que siempre tiene el formato completo).
- `interaction_code_v2.js` Stage 1: usa `redirect_history()` para capturar la URL final y extraer year/month antes del dispatch de `next_stage`, pasándolos como `resolved_year`/`resolved_month` al campo `year`/`month` del next_stage.
- Si la URL resuelta no tiene year/month y `day_urls` está vacío, se emite `blocked()` en vez de `dead_page()` para forzar retry con nuevo peer (señal de redirect no resuelto).
