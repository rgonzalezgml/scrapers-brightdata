# Arquitectura — impi_scraper_mx

Documento de cómo funciona internamente. Para "cómo usarlo", ver `README.md`.

---

## Resumen en una línea

4 hops HTTP contra `https://marcia.impi.gob.mx` — todos JSON API interno,
ningún HTML parsing — con `httpx.Client` sync + `ThreadPoolExecutor(8)` para
paralelizar el paso 4.

---

## Posición en el repo

```
/workspace
├── scrapers/impi/                ← scraper BrightData (JS, Scraper Studio)
│                                    — bloqueado contra .gob.mx
├── middlewares/impi/             ← cliente Python del scraper BrightData
│                                    — depende del scraper anterior, hoy inservible
└── impi_scraper_mx/              ← ESTE PAQUETE
                                    — standalone, sin BrightData, habla
                                      directo con el portal del IMPI
```

El sufijo `_mx` es convención para variantes standalone que apuntan a sitios
que BrightData rechaza (dominios gubernamentales de México). Vive fuera de
`scrapers/` y `middlewares/` a propósito: no sigue el patrón de dos etapas
JS + middleware Python del resto del repo.

---

## El portal IMPI — lo que hay detrás

`marcia.impi.gob.mx` es una **SPA Vue** cuyo bundle vive en
`/marcas/static/js/app.e446c256.js` (~1.4 MB). El HTML del servidor es un
shell vacío que monta la SPA. Todos los datos los sirve un API interno bajo
`/marcas/search/internal/*`.

Endpoints descubiertos (solo los primeros 4 están en uso):

```
GET  /marcas/search/quick                       ← bootstrap (setea XSRF-TOKEN)
POST /marcas/search/internal/record             ← crea búsqueda → devuelve searchId
POST /marcas/search/internal/result             ← paginado del listado
GET  /marcas/search/internal/view/{id}          ← detalle del expediente
POST /marcas/search/internal/result/count       ← (no usado)
POST /marcas/search/internal/count/combination  ← (no usado)
GET  /marcas/search/internal/counts             ← (no usado)
GET  /marcas/search/internal/records            ← (no usado, búsquedas guardadas)
POST /marcas/search/internal/extract            ← (no usado, "mi lista")
POST /marcas/search/internal/extract/bulk       ← (no usado)
POST /marcas/search/internal/image              ← (no usado, búsqueda por imagen)
POST /marcas/search/internal/image/upload/bulk  ← (no usado)
```

**Autenticación**: cookie `XSRF-TOKEN` (la setea el server en el paso 1) +
header `X-XSRF-TOKEN` con el mismo valor en cada request. Sin esto, el API
devuelve 500 (no 401 ni 403 — es un framework server que crashea el handler).

---

## Flujo completo de una corrida

```
┌─────────────────────────────────────────────────────────────────────────┐
│  1. GET  /marcas/search/quick                             (1 request)   │
│     → Set-Cookie: XSRF-TOKEN=<uuid>                                     │
│     → httpx.Client.cookies captura XSRF-TOKEN                           │
│     → guardamos el token en self._xsrf para el resto de la sesión       │
│                                                                         │
│  2. POST /marcas/search/internal/record                   (1 request)   │
│     Headers: X-XSRF-TOKEN + Cookie (automática del Client)              │
│     Body:    { "_type": "Search$Structured",                            │
│                "query": {                                               │
│                  "name":   { "types": ["OWNERS"], "name": "GENOMMA LAB" },│
│                  "appType": ["REGISTRO DE MARCA"],                      │
│                  "date":    null or { "types":["DATE_EXPIRY"], ... },   │
│                  // 10+ claves más, la mayoría null                     │
│                }, "images": [] }                                        │
│     Response: { "id": "<searchId uuid>" }                               │
│                                                                         │
│  3. POST /marcas/search/internal/result     (CEIL(total/size) requests) │
│     Body:    { "searchId":       <uuid>,                                │
│                "pageNumber":     0..N,                                  │
│                "pageSize":       100,                                   │
│                "statusFilter":      [],       ← obligatorio, [] = todos │
│                "viennaCodeFilter":  [],       ← obligatorio             │
│                "niceClassFilter":   [] }      ← obligatorio             │
│     Response: { "resultPage":    [ 100 rows ],                          │
│                 "totalResults":  1231,                                  │
│                 "pageNumber":    0,                                     │
│                 "pageSize":      100,                                   │
│                 "aggregates":    { STATUS, VIENNA_CODES, NICE_CLASSES } }│
│     Loop pageNumber=0..12 hasta acumular totalResults.                  │
│     (para GENOMMA LAB: 13 páginas, 1231 ids).                           │
│                                                                         │
│  4. GET  /marcas/search/internal/view/{id}   (total_rows requests)      │
│     ↳ solo si fetch_details=True                                        │
│     Concurrente con ThreadPoolExecutor(max_workers=detail_concurrency). │
│     Response: {                                                         │
│       "details": {                                                      │
│         "generalInformation": { title, applicationNumber,               │
│                                 registrationNumber, applicationDate,    │
│                                 registrationDate, expiryDate, appType },│
│         "productsAndServices": [ { classes, goodsAndServices } ],       │
│         "trademark": { id, image, viennaCodes: "26.01.14, ..." },       │
│         "ownerInformation": { owners: [{ Name, Addr, Cry }] },          │
│         "prioridad": []                                                 │
│       },                                                                │
│       "historyData": {                                                  │
│         "historyRecords": [ { procedureEntreeSheet, receptionYear,      │
│                               description, startDate, dateOfConclusion, │
│                               details: { officios: [...],               │
│                                          promociones: [...] } } ]       │
│       },                                                                │
│       "result":       { /* la row del listado */ },                     │
│       "currentOrdinal": 1,                                              │
│       "totalResults":   1                                               │
│     }                                                                   │
└─────────────────────────────────────────────────────────────────────────┘

Para 1,231 marcas con detalle, totales:
  Pasos 1+2:          2 requests    (~200 ms)
  Paso 3 (listado):  13 requests    (~2 s)
  Paso 4 (detalle):  1231 requests  (~41 s con concurrency=8)
  ──────────────────────────────────
  Total:             ~1,246 requests, ~43 s wall time
```

---

## Archivos clave

```
impi_scraper_mx/
├── client.py     ← IMPIClient. Todos los hops HTTP + mapping.
├── models.py     ← SearchInputs, Marca, SearchResult (pydantic v2).
├── errors.py     ← Jerarquía de excepciones.
├── cli.py        ← argparse + orquestación del CLI (`python -m impi_scraper_mx`).
├── __main__.py   ← hook para `python -m`.
└── __init__.py   ← re-exports: IMPIClient, SearchInputs, Marca, ...
```

Responsabilidades:

- **`IMPIClient`** (en `client.py`): sesión `httpx.Client`, los 4 hops,
  paginado, enriquecimiento concurrente.
- **`IMPIClient.search(inputs)`**: orquesta los pasos 1→4 y devuelve
  `SearchResult`.
- **`IMPIClient.get_detail(mark_id)`**: un solo hit al paso 4. Lo usan los
  scripts de la capa de orquestación para traer detalle selectivo.

---

## Decisiones de diseño

### D1. `httpx` síncrono + `ThreadPoolExecutor`, no `asyncio`

Para 1,231 requests I/O-bound, los dos son equivalentes en throughput, pero
threads mantienen la API síncrona (sin `async def`, sin `asyncio.run`, sin
contaminar los scripts de arriba con event loops). Trade-off: un thread pool
de 8 ocupa más memoria que 8 tareas async, pero irrelevante a esta escala.

### D2. Descarga iterativa forzada

No hay forma de pedirle al IMPI "traeme las 1,231 marcas en un solo hit":

- `/internal/result` tiene `pageSize` máximo ~200 (server trunca o rechaza).
- `/internal/view/{id}` es un recurso por request, no acepta batch.

Por eso el paso 3 ITERA (secuencial) y el paso 4 ITERA (concurrente).

### D3. El detalle es opcional

El paso 4 cuesta 95% del wall time. Los scripts de la capa de arriba
(p.ej. `fetch_pending.py`) piden `fetch_details=False`, filtran en Python,
y recién ahí llaman `get_detail(id)` caso por caso. Para GENOMMA LAB eso
baja de 1,231 a ~204 detalles (6× menos requests). Con detail loop
secuencial tarda ~50 s; con `ThreadPoolExecutor(8)` ~10 s.

### D4. `detalle` como passthrough `dict`

En vez de definir modelos pydantic para `generalInformation`, `trademark`,
`ownerInformation`, `historyRecords[]`, etc., se dejan como `dict[str, Any]`
con las keys nativas del portal. Razones:

- El shape lo decide IMPI, no nosotros. Si agregan un campo, passthrough
  no rompe.
- Normalizar 7 subestructuras anidadas cuesta mucho código para un valor
  dudoso — los scripts de arriba las leen sin problema.
- **Limitación conocida**: `history_records[].details.officios` y
  `.promociones` usan keys con tildes españolas
  (`"descripciónDeLaPromoción"`, `"númeroDelOficioQueGuardaRelaciónConLaPromoción"`).
  No rompen JSON pero son incómodas en DB. Si esto se persiste en una tabla,
  la capa de arriba hace el rename.

### D5. Mapping mínimo del listado

El mapping `_map_row` solo renombra a español las 13 claves principales
(`title` → `denominacion`, `applicationNumber` → `expediente`, etc.) y deja
pasar lo que no usamos. No hay normalización de tipos (fechas siguen como
strings `"2/9/2010"` — IMPI mezcla formatos con y sin ceros a la izquierda).

### D6. Sin retry automático

Si un `/view/{id}` falla, el flag `detail_http_<code>` queda en la row y
seguimos. El caller decide si reintenta. Para un prototipo alcanza — en
ninguna corrida real vimos errores.

### D7. No somos el agente, no manejamos caching ni persistencia

Este paquete es un **dumb pipe**: descarga y devuelve JSON. NO:

- NO mantiene estado entre corridas.
- NO guarda snapshots ni hace diff.
- NO implementa `trigger` / `get_result` / envelope normalizado.
- NO expone `TOOL_SCHEMA`.
- NO corre en background.

Todo eso vive en la capa de arriba (scripts de orquestación hoy,
eventualmente un adapter cuando se integre al agente).

---

## Bugs que fueron corregidos

### B1. `totalElements` → `totalResults`

El prototipo inicial buscaba `totalElements` en el response de `/result`.
El portal usa `totalResults`. Resultado: `paginated` siempre `False` y
`total=0` aunque llegaran filas.

### B2. Body del paginado equivocado

Inicial: `{ searchId, page, size }`. Real (el que manda el SPA):
`{ searchId, pageNumber, pageSize, statusFilter, viennaCodeFilter, niceClassFilter }`.
Con el body equivocado el server ignora `page` y devuelve siempre
`pageNumber: 0` (50 filas repetidas × N páginas → 50 IDs únicos × 25
duplicados = 1,250 filas "fantasma"). Los filtros son arrays vacíos
obligatorios; sin ellos, 500.

### B3. Enriquecimiento por dict[id] perdía duplicados

`idx = {m.id: m for m in marcas}` colapsaba marcas con ID igual (cuando
había duplicados por el B2). Ahora el enriquecimiento itera por índice
posicional.

### B4. `scraped_date = ""` cuando no había filas

CLI leía `result.rows[0].scraped_date if result.rows else ""`. Ahora siempre
`datetime.utcnow().date().isoformat()`.

---

## Limitaciones actuales

- **Se nota como bot.** User-Agent `python-httpx/X`, 28 req/s pico en el
  paso 4. Para una corrida puntual alcanza. Para cadencia diaria hay que
  agregar User-Agent realista + jitter + bajar concurrencia a 3 (costo:
  43 s → ~4 min). Pendiente.
- **Una sola IP.** Si IMPI decide bloquear, todo el paquete se cae. No
  hay rotación de proxies — para este dominio y esta escala no vimos
  necesidad.
- **Estado de sesión volátil.** Cada corrida vuelve a hacer GET
  `/quick` + POST `/record`. No se reutiliza `searchId` entre ejecuciones
  (el portal lo atenúa a la sesión XSRF, y el XSRF caduca rápido).
- **Sin tests.** Decisión explícita: es prototipo. Se agregan cuando se
  integre al agente y el contrato se estabilice.

---

## Qué falta para integrar con el agente del repo

Cuando se decida formalizar la integración (ver handoffs en
`/workspace/docs/fase3/*-handoff.md` como plantilla):

1. `impi_scraper_mx/tool_schema.py` — dict JSON Schema con `trigger` +
   `get_result`, consumible por la API de Anthropic.
2. `impi_scraper_mx/agent_adapter.py` — envuelve `IMPIClient.search` en un
   job async con `job_id`, devuelve envelope
   `{source, scraped_at, inputs, data, meta}` estándar, maneja paginación
   de entrega al LLM (no full 8 MB en un tool_result).
3. Entrada en `/workspace/agent_harness/registry.py`.
4. `/workspace/docs/fase3/impi-mx-handoff.md` documentando el contrato.

Mientras tanto, el patrón recomendado para consumir este middleware es
**scripts de orquestación en Python** (ver README §"Uso desde un script
Python"): el script decide qué pedirle al middleware (p.ej. solo marcas
EN TRÁMITE) y escribe el JSON resultante a disco o a la DB.
