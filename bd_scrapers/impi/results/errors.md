# impi — errors (site-specific)

Gotchas del sitio `marcia.impi.gob.mx` y del scraper `impi`.
Memoria del proyecto: `/workspace/docs/specs/memory.md` §"Errores y gotchas — dos niveles".

Runtime errors cross-scraper en `/workspace/docs/specs/brightdata-errors.md` (R1..RN).
Acá solo lo específico de este sitio.

---

## E1 — XSRF-TOKEN llega como cookie Set-Cookie del primer GET

**Versión afectada**: v1 (documentación preventiva — pendiente de run).

**Síntoma esperado**: el POST a `/marcas/search/internal/record` sin header
`X-XSRF-TOKEN` responde **403 Forbidden** con cuerpo JSON tipo
`{"timestamp":"...","status":403,"error":"Forbidden","path":"..."}`.

**Causa**: Spring Security en backend. El endpoint exige que el valor del
header `X-XSRF-TOKEN` coincida con la cookie `XSRF-TOKEN` (double-submit
pattern). El blueprint del compañero lo resuelve en browser leyendo
`document.cookie`. En BrightData Scraper Studio no hay acceso directo a
`document.cookie` desde interaction_code; lo extraemos de
`response_headers()['set-cookie']` después del primer `navigate()`.

**Fix aplicado en v1**:
```js
navigate(BASE_URL + '/marcas/search/quick');
const setCookie = (response_headers() || {})['set-cookie'] || [];
const list = Array.isArray(setCookie) ? setCookie : [setCookie];
let xsrfToken = null;
for (const raw of list) {
    const m = raw.match(/XSRF-TOKEN=([^;]+)/);
    if (m) { xsrfToken = decodeURIComponent(m[1]); break; }
}
```
Y luego se propaga en `X-XSRF-TOKEN` + `Cookie` del POST.

**Pendiente de confirmar en run**:
- Forma exacta en que `response_headers()` expone Set-Cookie (string único con
  comas, array de strings, lowercase vs TitleCase). El parser defensivo acepta
  ambas variantes (`set-cookie` y `Set-Cookie`; string y array).
- Si la cookie llega en un hop secundario (ej. redirect interno), el primer
  `response_headers()` puede no contenerla → `xsrf_missing` + `blocked()`.
  Fix: considerar agregar un `navigate()` secundario a un endpoint distinto
  (ej. `/marcas/search/quick/init`) si el primero no la entrega.

---

## E2 — request() body: string vs objeto

**Versión afectada**: v1 (documentación preventiva — pendiente de run).

**Síntoma esperado**: el retorno de `request()` puede ser
`{body: string, headers, status_code}` o directamente el objeto parseado (el
DSL de BrightData no está formalmente documentado en este punto para code
worker). Si tratamos el body como string pero vino objeto (o viceversa), el
`JSON.parse()` lanza `SyntaxError: Unexpected token o in JSON at position 1`
o `Cannot read property 'resultPage' of null`.

**Fix aplicado en v1**:
```js
function parseJsonBody(resp) {
    const raw = resp?.body !== undefined ? resp.body : resp;
    if (raw === null || raw === undefined) return null;
    if (typeof raw === 'object') return raw;
    if (typeof raw === 'string') return JSON.parse(raw.trim() || 'null');
    return null;
}
```
Cubre las tres variantes (objeto ya parseado, string JSON, null).

**Pendiente de confirmar en run**: si el runtime devuelve un shape distinto
(ej. `{data: ...}` envolviendo el body), agregar unwrap en v2.

---

## E3 — Paginación no implementada en v1

**Versión afectada**: v1 (diseño — documentación preventiva).

**Síntoma esperado**: el POST `/result` responde
`{resultPage: [...], totalElements: N}`. Si `totalElements > page_size` la v1
solo trae la primera página (`page: 0, size: pageSize`) y emite flag
`paginated` en cada fila.

**Decisión v1**: no paginar. El mini-spec dice `page_size=50` default y el
caso base de Genomma (marcas del titular próximas a vencer) difícilmente
exceda ese número. Si alguna corrida emite `paginated` sistemáticamente,
abrir E4 y diseñar v2 con `rerun_stage({..., page})` paralelo (R3 del skill).

**Pendiente de confirmar en run**: qué campo trae el total (`totalElements`,
`total`, `totalCount`). El parser defensivo intenta ambos.

---

## E4 — item.images shape desconocido

**Versión afectada**: v1 (documentación preventiva — pendiente de run).

**Síntoma esperado**: el blueprint asume `item.images` existe pero no
especifica shape (array de URLs, array de objetos con `url`/`base64`,
string único, etc.). v1 lo emite 1:1 como llegue (`item?.images ?? null`)
sin normalizar.

**Pendiente de confirmar en run**: revisar el JSON real y decidir en v2 si:
- Aplanar a lista de URLs → `Image` wrappers del DSL.
- Filtrar imágenes vacías (`[]` → `null`).
- Agregar `imagen_primary` como primer elemento para consumo downstream.

---

## E5 — request() en Browser worker: disponibilidad no documentada

**Versión afectada**: v1 sc_browser.

**Síntoma esperado**: el skill `scraper-implementation` documenta `request()`
como primitiva "útil en sc_code para POST/PUT" pero no lo prohíbe
explícitamente en Browser worker. v1 sc_browser asume que funciona (para hacer
los POSTs subsecuentes contra `/record` y `/result`).

**Plan si falla**: si el runtime devuelve `ReferenceError: request is not
defined` en Browser worker, migrar a una de estas alternativas:
1. Ejecutar el XHR desde dentro del browser con alguna primitiva de
   inyección de JS (si existe — investigar `tag_window_field` o equivalentes
   para evaluar JS custom en el page context).
2. Usar un `navigate()` secundario con `method: 'POST'` y `body` si el DSL lo
   acepta (no documentado en el skill al 2026-04-21).
3. Dejar solo el sc_code y discontinuar el sc_browser.

**Pendiente de confirmar en run**: la salida real cuando se invoca
`request()` en Browser worker.

---

## E6 — owner como substring en response puede no matchear titular real

**Versión afectada**: v1.

**Síntoma esperado**: el payload filtra por `query.name = {types: ["OWNERS"], name: "Genomma"}`. IMPI hace match substring sobre el titular, lo que devuelve p.ej. `GENOMMA LAB MEXICO, S.A.B. DE C.V.` pero también podría devolver `GENOMMA INTERNACIONAL` o variantes no-Genomma Lab.

**Fix aplicado en v1**: flag `owner_mismatch` por fila cuando
`item.owners[0].toLowerCase()` no contiene el owner buscado en lowercase.
No filtra: emite la fila igual para que downstream (middleware Python) decida.

**Pendiente de confirmar en run**: si el cliente requiere filtrar server-side,
pasar a v2 con filter post-response + flag `filtered_owners_out: N`.
