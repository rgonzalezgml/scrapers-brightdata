# Memory — Specs de scraper

> **Memoria persistente del proyecto (commited al repo).** Usar este archivo en lugar de la memoria per-container (`~/.claude/projects/.../memory/`) que no sobrevive al reset del contenedor. Referenciada desde `CLAUDE.md`.

Este documento es el **contrato canónico** del flujo de trabajo para cada scraper del proyecto. Toda spec en `docs/specs/scrapers/<name>.md` se construye y mantiene siguiendo este proceso.

El trabajo de un scraper tiene **tres etapas**:

1. **Análisis** — producir la spec (`<name>.md`) con el brief para DB AI (§1-§3 databrightdata) y la spec profunda nuestra (§1-§N genomma lab). **Definido abajo.**
2. **Implementación JS** — construir los parsers buenos en `scrapers/<name>/sc_browser/` + `sc_code/` sobre el andamiaje que DB AI genera en `vendor/`. **Definido abajo.**
3. **Middleware Python** — empaquetar el scraper como cliente Python stateless en `middlewares/<name>/` para que el repo de agentes lo consuma como dependencia. **Definido abajo.**

---

## Etapa 1 — Análisis

### Objetivo

Producir `/workspace/docs/specs/scrapers/<name>.md` con estructura fija. El archivo tiene dos secciones:

- **`databrightdata`**: brief mínimo que entregamos a DB AI para que autogenere `vendor/sc_browser/` y `vendor/sc_code/`. **≤ 1000 caracteres de prosa entre §1 + §2 + §3.**
- **`genomma lab`**: spec profunda para iterar nosotros los parsers buenos. Puntos ordenados 1–N, sin etiquetas `--- turno N ---`.

### Estructura exacta

```markdown
# <name> — spec
<URL canónica funcional>
Proveedor: <texto literal de la columna Proveedor del xlsx>
Categoría: <I+D | Precios>
Función: <texto literal de la columna Función del xlsx>

## databrightdata

### 1.
Propósito del scraper en una línea + entidades + señales principales + qué NO extrae.

### 2.
Schema JSON compacto por entidad (bloque ```json ... ```).

### 3.
Bullets de rutas útiles: listing, detail, API, sitemaps, endpoints disallow.

## genomma lab

### 1.
...propósito detallado...

### 2.
...infraestructura (render, anti-bot, encoding, proxy, retries)...

### 3.
...URLs canónicas con regex de ID, paginación, seed...

### 4–N.
...entidades, campos, reglas de parsing, clasificación, skip rules, output, límites, fixtures...
```

### Header — reglas

- **URL bajo el título**: la URL **canónica funcional**, no un tracking-tracker de Google Ads ni params de influencer/feature-flags. Ejemplo: para Olive Young fue `https://global.oliveyoung.com/`, no el `aclk` del xlsx.
- **Proveedor**: texto literal de la columna Proveedor del xlsx. Entidad legal/corporativa dueña del sitio (no el nombre comercial). Útil para entender relaciones cross-scraper (ej. CosmeticsDesign y nutraingredients comparten Proveedor=William Reed).
- **Categoría** y **Función**: texto literal de `docs/specs/source-scrapers.xlsx`, hoja `scrapers`, para la fila del scraper.

### databrightdata — reglas

- **§1**: scraper, entidades, señales clave, lo que NO se extrae. Corto.
- **§2**: schema como `{"entidad": [lista de campos]}`. Solo campos atómicos clave (drop nested). Inmutable entre versiones de implementación.
- **§3**: bullets de rutas con placeholders (`{slug}`, `{ID}`, `{YYYY}`). Incluir API endpoints, sitemaps, y Disallow críticos del `robots.txt`.
- **Límite duro**: la suma de prosa §1 + §2 + §3 no puede exceder **1000 caracteres**. Validar siempre:

```python
import re
content = open('docs/specs/scrapers/<name>.md').read()
match = re.search(r'## databrightdata\s*(.*?)## genomma lab', content, re.DOTALL)
prose = re.sub(r'###\s*\d+\.\s*\n', '', match.group(1)).strip()
assert len(prose) <= 1000, f'databrightdata excede: {len(prose)}'
```

### genomma lab — reglas

- Todos los puntos que conocemos del scraper. Plantilla típica de 10–11 puntos:
  1. Propósito detallado (qué, por qué, alineación cross-source).
  2. Infraestructura: render, Cloudflare/consent, encoding, UA, proxy region, delay, robots.txt, retry.
  3. URLs canónicas: regex de ID, paginación, seeds, sitemaps.
  4. Entidad principal — fuentes de datos (JSON-LD, DOM, API embebida) y campos base.
  5. Campos derivados / entidades secundarias.
  6. Skip rules — cuándo no emitir fila.
  7. Reglas de clean_name / parsing de texto.
  8. Parsing de precio / unidades / monedas.
  9. Clasificación / tipo / categorías.
  10. Output: naming, límites, flags permitidos.
  11. Fixtures reales: IDs concretos con expectativas de campos.
- Si hay prior work (`current_prompt.txt` histórico con "turnos"), **reutilizar el contenido** — renumerar como puntos ordenados, sin etiquetas `--- turno N ---`. Las referencias internas a "turno X" se reescriben a "punto X".

### Cómo obtener el material para genomma lab

1. **Prior work primero.** Si existe `docs/specs/brightd-scrapers/<name>/current_prompt.txt` o equivalente, reutilizar. Histórico: cosme, cosmetics-design, olive-young, alibaba, made-in-china.
2. **MCP brightdata** si no hay prior work. Tools: `mcp__brightdata__scrape_as_markdown`, `mcp__brightdata__scrape_batch`, `mcp__brightdata__search_engine`. Scrapear:
   - Homepage (estructura, navegación).
   - `robots.txt` (disallow, sitemaps, Crawl-delay, bots bloqueados — **revisar si ClaudeBot está Disallowed**).
   - Una página de categoría (listing, paginación, JSON-LD Breadcrumb).
   - Una página de detalle (JSON-LD Product/Article, DOM selectors, spec table embebida).
   - Un sitemap XML si hay.
3. **Fallback curl** si MCP está caído. Compressed + Chrome UA + Accept-Language:
   ```bash
   curl -sS -L --compressed \
     -A "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36" \
     -H "Accept-Language: en-US,en;q=0.9" --max-time 20 "$URL"
   ```
   Usado con indiamart cuando MCP retornaba `No active transport`.
4. **Extraer con Python + regex + `json.loads`**:
   - Bloques `<script type="application/ld+json">` → `BreadcrumbList`, `Product`, `ImageGallery`, `Organization`.
   - Embedded JSON inline (ej. `window.Fusion.globalContent`, `PC_ITEM_*` de IndiaMART).
   - Tabla de specs HTML → `key: value`.
   - Regex de URL del detail → `product_id`.

### Fuente de verdad del catálogo

**`/workspace/docs/specs/source-scrapers.xlsx`**, hoja `scrapers`.
Columnas: `#`, `API/Servicio`, `Proveedor`, `Categoría`, `Función`, `CUENTA`.
Consultar antes de redactar la spec para el header (Categoría + Función).

### Hand-off a DB AI

Una vez aprobada la spec, entregar SOLO la sección `databrightdata` (§1-§3) a DB AI para que genere el andamiaje en `vendor/sc_browser/` y `vendor/sc_code/`. La sección `genomma lab` se queda con nosotros para iterar nuestras versiones.

---

## Etapa 2 — Crear scrapers

### Objetivo

Producir los parsers de producción en `/workspace/scrapers/<name>/sc_browser/` y `sc_code/` (JS para BrightData: cheerio / iconv / DOM selectors), partiendo del andamiaje que DB AI entregó en `vendor/`.

### Estructura de carpetas

```
/workspace/scrapers/<name>/
├── __init__.py
├── vendor/                          ← v0: entrega de DB AI, READ-ONLY archivo
│   ├── sc_browser/
│   │   ├── interaction_code.js      ← nombre sin versión (tal como DB AI lo entregó)
│   │   └── parser_code.js
│   └── sc_code/
│       ├── interaction_code.js
│       └── parser_code.js
├── sc_browser/                      ← v1+: nuestras versiones iterables
│   ├── interaction_code_v1.js       ← v1: arranca como copia de vendor; recibe cambios
│   ├── parser_code_v1.js
│   ├── interaction_code_v2.js       ← v2: siguiente iteración (cierra gaps)
│   └── parser_code_v2.js
├── sc_code/
│   ├── interaction_code_v1.js
│   └── parser_code_v1.js
└── results/                         ← JSON descargados de corridas + registry
    ├── registry.md                  ← mapa archivo → versión + notas
    └── *.json
```

### Versionado de iteraciones

- **v0 = vendor** (original DB AI). Vive en `vendor/` con nombres sin sufijo. Read-only.
- **v1, v2, ... = nuestras versiones** en `sc_browser/` y `sc_code/` con sufijo `_vN`.
- **v1 arranca como copia exacta de vendor** — sobre esa copia hacemos los primeros cambios. Mientras no haya cambios, root está vacío o los `_v1.js` son equivalentes a vendor (transición).
- Cada nueva versión se agrega como `_vN+1` **al lado** — las previas no se borran (A/B + rollback).

### Resultados y feedback loop

- Cada corrida del scraper produce un JSON que se guarda en `scrapers/<name>/results/`.
- `scrapers/<name>/results/registry.md` mantiene el mapa **archivo → versión** con fecha, modo (`sc_browser`/`sc_code`), fixture/URL, notas.
- El registry es la fuente para decidir qué gap cerrar en la siguiente `_vN+1`: leer el JSON más reciente, comparar contra el schema de la spec §2, identificar el próximo bug o campo faltante, iterar.

### Errores y gotchas — dos niveles

Consultar ambos **antes** de proponer una nueva versión:

- **Cross-scraper (runtime BrightData)**: `/workspace/docs/specs/brightdata-errors.md`
  Reglas `R1..RN` del runtime: `navigate()` solo top-level, `parse()` sin args, funciones browser-only en Code worker, patrones de retry, etc. Se alimenta de runs que fallan con errores del runtime (no del sitio).
- **Per-scraper (site-specific)**: `/workspace/scrapers/<name>/results/errors.md`
  Gotchas del sitio concreto con `E1..EN`: selectores hardcoded en vendor, encoding raro, anti-bot, redirects, paginación atípica, etc. Se alimenta de cada JSON en `results/` que expone un problema nuevo.

Cuando un error nuevo sale en un run:
1. Si es del runtime (mensaje tipo `async code is not allowed`, `parse validation error`, function not defined en Code worker) → va a `brightdata-errors.md`.
2. Si es del sitio (selector no atrapa, encoding, paywall, estructura cambió) → va al `errors.md` del scraper.

### Flujo canónico

1. **Input de DB AI**: usuario entrega la sección `databrightdata` (§1-§3) de la spec a DB AI externo. DB AI genera 4 archivos JS y el usuario los coloca en `scrapers/<name>/vendor/sc_browser/` y `sc_code/`.
2. **First boot — copia verbatim con sufijo `_v1`**: copiar los 4 archivos de `vendor/` a `sc_browser/` y `sc_code/` **tal cual, sin editar**, agregando sufijo `_v1` al nombre. Después de este paso `vendor/` queda archivado y **no se toca más**.
   ```bash
   cp vendor/sc_browser/interaction_code.js sc_browser/interaction_code_v1.js
   cp vendor/sc_browser/parser_code.js     sc_browser/parser_code_v1.js
   cp vendor/sc_code/interaction_code.js   sc_code/interaction_code_v1.js
   cp vendor/sc_code/parser_code.js        sc_code/parser_code_v1.js
   diff -q vendor/sc_browser/interaction_code.js sc_browser/interaction_code_v1.js  # sanity
   ```
3. **Gap analysis** vendor vs spec: comparar el output real del vendor contra el schema §2 y las reglas §4-§9 de la spec (`docs/specs/scrapers/<name>.md`). Documentar qué campos faltan, qué reglas no se aplican, qué bugs tiene el andamiaje (hardcodes, selectores frágiles, typos de clase CSS).
4. **Iteración en root**: todas las mejoras suceden en `sc_browser/` y `sc_code/` al root. Cada cambio debe cerrar un gap concreto del análisis.
5. **Retroalimentación**: cada versión corrida contra fixtures emite JSON — el output alimenta la próxima iteración (ver "Resultados y fixtures" abajo).

### Contrato duro

- El schema `§2` de la spec es **inmutable** entre versiones. Toda iteración debe producir exactamente ese shape. Un cambio de schema requiere **nueva spec**, no nueva versión.

  **Excepción: corrección de inconsistencia interna.** Si §4/§5/§6 (u otros puntos de `genomma lab`) describen campos o nombres que contradicen §2, se puede **corregir §2** para alinear con la prosa — eso no es un cambio de contrato, es reparar la spec. Debe hacerse explícitamente, con una nota en el resumen del cambio, y SÓLO cuando la prosa de la spec es la fuente correcta (lo que los parsers ya emiten / lo que el schema del Studio espera). Si en cambio §2 es lo correcto y §4+ lo contradicen, actualizá §4+ para alinear con §2, NO al revés.

  Esto aplica cuando:
  - La prosa describe nombres largos / extras y §2 usa nombres cortos / incompleto.
  - El schema del Output Schema del BD Studio (cuando existe) coincide con la prosa, no con §2.
  - El vendor v1 generado por DB AI ya usa nombres / campos de la prosa — §2 fue una abreviación defectuosa desde el inicio.

  NO aplica cuando:
  - El cambio altera el shape de forma que downstream (exportadores, comparadores cross-source) deja de funcionar → eso es cambio de contrato, requiere nueva spec.
- `vendor/` es archivo histórico — nunca editar. Si DB AI regenera, poner la nueva entrega en `vendor/` reemplazando la vieja, pero **el bootstrap verbatim ya ocurrió una vez**: no se re-copia a root.

### Gap analysis — patrones frecuentes del vendor

Basado en made-in-china v0 observado el 2026-04-21:

- **No usa JSON-LD Product** aunque la spec lo designe como fuente autoritaria → usa DOM selectors frágiles. **Acción**: reescribir con `JSON.parse($('script[type="application/ld+json"]').html())` cuando la spec lo pide.
- **Hardcodes por haber testeado 1 fixture** (ej. `$('a[href*="Oxide"]')` hardcoded). **Acción**: derivar del breadcrumb genérico.
- **Campos del contrato faltantes**: `scraped_date`, `site_code`, `price_normalized_per_kg`, `category_path`, `scraper_flags[]`, `product_name_original`, `image_primary`. **Acción**: agregarlos con `null` explícito cuando no se pueden derivar.
- **Entidades mezcladas**: vendor mete `supplier_*` dentro del product en vez de emitir entidad `supplier` aparte. **Acción**: separar.
- **Unit crossing**: `price_unit` derivado del MOQ en vez de del price_raw. **Acción**: parsear del price_raw.
- **País no ISO-2**: `supplier_country` viene como `"China"` literal; spec pide `"CN"`. **Acción**: mapa país→ISO.
- **Wrappers inventados**: `new Money(...)`, `new URL(...)` como valores de retorno. **Acción**: devolver números y strings puros salvo que el runtime BrightData requiera el wrapper.
- **Sin bot-check**: interaction no detecta body<50KB + title "Access Denied" + cadena CF antes de `collect`. **Acción**: agregar guard + `scraper_flags: ['blocked']`.

### Pendiente de decidir (no redactar hasta consenso)

- **Convención de tests**: fixtures en `tests/<name>/fixtures/`, validador JS en `tests/<name>/validate_vN.js` (patrón cosme).
- **sc_code HTTP-puro vs browser**: el vendor actual de made-in-china usa `navigate()` en ambos modos. La spec `§5-§6` puede pedir que `sc_code` sea HTTP sin browser (cheerio + iconv + request()); decidir si reescribir o actualizar la spec.

Redactar estas decisiones aquí a medida que el usuario las confirme en uso real.

Temas candidatos a cubrir aquí cuando toque:

- Cómo leer el `vendor/` generado por DB AI (una sola pasada, no editar).
- Dónde y cómo versionar nuestras iteraciones (`parser/sc_{browser,code}/vN/`).
- Flujo de retroalimentación: resultados JSON → análisis de fallos → actualización de spec → nueva versión.
- Restricciones de runtime BrightData (R1 `navigate()` top-level, R4 `parse()` validación de schema, etc.) — doc común cross-scraper a crear.
- Convenciones de tests (fixtures en `tests/<name>/fixtures/`, validadores JS, regresión obligatoria).
- Catálogo de flags permitidos por tipo de scraper.

**No redactar hasta que el usuario lo indique.**

---

## Etapa 3 — Middleware Python

### Objetivo

Producir `/workspace/middlewares/<name>/`: paquete Python stateless que envuelve el scraper JS (Etapa 2) y lo expone como cliente importable por el **repo de agentes**.

### Regla de oro

El middleware es **stateless y Python-puro**. No gestiona DB, cache, ni declara tools al agente. El repo de agentes importa el paquete y encima coloca `ServiceRegistry`, persistencia (`scraper_runs` en PostgreSQL), cache TTL y declaración de tool al agente Anthropic.

El middleware solo sabe:
- Disparar BrightData Scraper Studio vía REST API.
- Pollear el snapshot hasta `ready`.
- Normalizar el payload al envelope común.
- Devolver errores tipificados.

### Contrato público

Cada `middlewares/<name>/` expone:

```python
from middlewares.<name> import trigger, get_result, TOOL_SCHEMA

job = await trigger(inputs)                 # {"job_id": str, "eta_seconds": int}
res = await get_result(job["job_id"])       # {"status": "running|done|failed", "data"?: envelope, "error"?: {...}}
```

Envelope normalizado (shape uniforme cross-scraper):

```json
{
  "source": "<name>",
  "scraped_at": "YYYY-MM-DDTHH:MM:SSZ",
  "inputs": {...},
  "data": [...],
  "meta": {"rows": int, "emitted": int, "errors": int, ...}
}
```

`data[]` sigue EXACTAMENTE el §2 del spec del scraper — **inmutable**.

### Estructura canónica

```
middlewares/
├── core/                        ← compartido
│   ├── client.py                 ← BaseScraperClient
│   ├── envelope.py
│   └── errors.py                 ← SITE_BLOCKED, TIMEOUT, INVALID_INPUTS, BRIGHTDATA_ERROR, ...
└── <name>/                       ← underscore, no hyphen (Python-safe)
    ├── __init__.py               ← exports públicos
    ├── client.py
    ├── models.py                 ← pydantic v2
    ├── config.py                 ← DATASET_ID, endpoints, defaults
    ├── tool_schema.py            ← TOOL_SCHEMA dict (JSON Schema)
    └── tests/
        ├── conftest.py
        ├── fixtures/<name>_snapshot_<id>.json
        └── test_client.py
```

### Reglas duras

- **Nombres Python-safe**: `middlewares/cosmetics_design/` con underscore. El scraper JS sigue siendo `scrapers/cosmetics-design/` con hyphen.
- **Async por default**: `httpx.AsyncClient`, `async def`.
- **Pydantic v2** para `inputs` y envelope. Validación estricta de `inputs` antes de llamar BrightData — si falla, devolver `INVALID_INPUTS` sin llamar la API.
- **Errores normalizados**: catálogo común (ver `core/errors.py`). No inventar códigos.
- **Tests sin mocks** de BrightData API — fixtures reales de snapshots.
- **Auth**: `BRIGHTDATA_API_KEY` vía env var. Nunca hardcodear.
- **Versionado por git commit**, no por `client_v1.py` / `client_v2.py`. Excepción: si el contrato público rompe, crear `middlewares/<name>/v2/` al lado y mantener v1 hasta migración del consumidor.

### Handoff de diseño

Antes de implementar, cada scraper necesita su handoff en `/workspace/docs/fase3/<name>-handoff.md`. El handoff es la fuente de verdad del contrato (inputs pydantic, envelope, DATASET_ID, errores específicos, tests esperados). Ver `docs/fase3/README.md` como índice.

### Agente responsable

`middleware-python` — implementa `middlewares/<name>/` a partir de `docs/fase3/<name>-handoff.md` y `docs/specs/scrapers/<name>.md`. Definido en `.claude/agents/middleware-python.md`.

### Consumo desde el repo de agentes

```python
# shared/services/scrapers.py en el repo de agentes
from middlewares.cosmetics_design import trigger, get_result, TOOL_SCHEMA

# El repo de agentes wrappea con cache/DB/ServiceRegistry según su propia convención.
```

