---
name: scraper-spec-analysis
description: >
  Etapa de análisis para producir la spec de un scraper en
  /workspace/docs/specs/scrapers/<name>.md. Usar cuando el usuario pide
  "crea la spec de X", "crea el fichero de X", o cuando agrega un scraper
  nuevo al catálogo source-scrapers.xlsx. Produce un .md con header
  (URL+Proveedor+Categoría+Función), sección databrightdata (≤1000 chars) y
  sección genomma lab (puntos ordenados).
---

# SKILL: scraper-spec-analysis

Etapa **1 de 2** del trabajo de un scraper. La etapa 2 (implementación) está por definir — **no avanzar a implementar** hasta que `memory.md` lo cubra.

Memoria canónica del proceso: `/workspace/docs/specs/memory.md`. Toda duda procesual se resuelve leyéndola.

---

## 1. Cuándo se activa

- Usuario pide: "crea la spec de X", "crea el fichero de X", "prepara X para DB AI".
- Usuario agrega una fila nueva a `docs/specs/source-scrapers.xlsx` y pide arrancar.
- Usuario reporta inconsistencia entre la spec actual y lo observado en el sitio real.

---

## 2. Producto

Un archivo `/workspace/docs/specs/scrapers/<name>.md` con esta estructura exacta:

```markdown
# <name> — spec
<URL canónica funcional>
Proveedor: <texto literal de la columna Proveedor del xlsx>
Categoría: <I+D | Precios>
Función: <texto literal de la columna Función del xlsx>

## databrightdata

### 1.
<propósito + entidades + señales + NO extrae>

### 2.
```json
{"entidad": ["campo1", "campo2", ...]}
```

### 3.
- <bullets de rutas útiles con placeholders>

## genomma lab

### 1.–N.
<puntos ordenados con toda la profundidad: infra, URLs, entidades, parsing, skips, clasificación, output, fixtures>
```

**Regla dura**: `databrightdata` (§1+§2+§3 prosa) **≤ 1000 caracteres**. Validar con el snippet Python de `memory.md` antes de reportar completado.

---

## 3. Flujo de trabajo

### Paso 1 — Contexto del scraper
1. Leer `docs/specs/source-scrapers.xlsx` (hoja `scrapers`) para confirmar `Proveedor`, `Categoría` y `Función` del scraper.
2. Confirmar URL canónica funcional — NO usar `google.com/aclk?...` ni URLs con params de influencer/feature-flags.

### Paso 2 — Buscar prior work
Verificar si existe material reusable:
- `docs/specs/brightd-scrapers/<name>/current_prompt.txt` (histórico, "turnos").
- `docs/specs/brightd-scrapers/<name>/research/*.md`.
- `docs/specs/brightd-scrapers/<name>/FINDINGS.md`.

Si existe → **reutilizar el contenido**: renumerar "turnos" como puntos ordenados, sin etiquetas `--- turno N ---`. Reescribir referencias internas ("turno 7" → "punto 7").

### Paso 3 — Investigar con MCP (si no hay prior work)
Tools disponibles (pueden requerir `ToolSearch` para cargarlas):
- `mcp__brightdata__scrape_as_markdown` — una URL a la vez
- `mcp__brightdata__scrape_batch` — hasta 10 URLs
- `mcp__brightdata__search_engine` — Google/Bing/Yandex SERP

Scrapear mínimo:
1. Homepage del sitio.
2. `robots.txt` (disallow, sitemaps, Crawl-delay, bots bloqueados — revisar **ClaudeBot** en particular).
3. Una página de categoría/listing.
4. Una página de detalle.
5. Un sitemap XML si hay indicio.

### Paso 4 — Fallback curl si MCP cae
Si MCP retorna `No active transport` o similar:
```bash
curl -sS -L --compressed \
  -A "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36" \
  -H "Accept-Language: en-US,en;q=0.9" --max-time 20 "$URL" -o /tmp/<name>/<file>.html
```
Sin `--compressed` la respuesta puede ser binaria (gzip). Delay 1–2s entre requests.

### Paso 5 — Extraer estructura
Con Python + regex + `json.loads`:
- Bloques `<script type="application/ld+json">` → `BreadcrumbList`, `Product`, `Article`, `Organization`, `ImageGallery`.
- Embedded JSON inline (`window.Fusion.globalContent`, `PC_ITEM_*`, etc.).
- Tabla de specs HTML → `<tr><td>key</td><td>value</td></tr>`.
- Regex del path → `product_id`.
- Breadcrumb → `type` + `category_path`.
- Robots.txt → routes Disallow + sitemaps.

### Paso 6 — Redactar el .md
- **Header**: URL + Proveedor + Categoría + Función tal cual xlsx.
- **databrightdata §1**: una línea densa — propósito, entidades, señales, NO extrae. ~250-350 chars.
- **databrightdata §2**: JSON compacto `{"entidad": [campos]}`. Drop campos derivables/meta. ~300-400 chars.
- **databrightdata §3**: bullets de rutas con placeholders. ~250-350 chars.
- **genomma lab**: 10–11 puntos siguiendo la plantilla de `memory.md`.

### Paso 7 — Validar
```python
import re
content = open('/workspace/docs/specs/scrapers/<name>.md').read()
match = re.search(r'## databrightdata\s*(.*?)## genomma lab', content, re.DOTALL)
prose = re.sub(r'###\s*\d+\.\s*\n', '', match.group(1)).strip()
assert len(prose) <= 1000, f'databrightdata excede: {len(prose)}'
```

Si se pasa → trimear §1 o §3 (no §2, que es el contrato).

### Paso 8 — Reportar al usuario
Resumen corto:
- Ruta del archivo creado.
- Tamaño de `databrightdata` (N chars / 1000).
- Si hubo prior work reutilizado.
- Fixtures / URLs reales anotadas.
- Hallazgos críticos (ej: ClaudeBot Disallowed, paywall, CSRF, SPA obligatorio).

---

## 4. Patrones frecuentes por tipo de scraper

### I+D — Rankings/Bestsellers (cosme, olive-young)
- Entidades múltiples: `ranking`, `product`, `brand`.
- API JSON interna sin CSRF si existe.
- Dedupe por `(region, category_id, rank)`.
- Enriquecimiento opcional del detail vía SPA con CSRF.

### I+D — Noticias (cosmetics-design)
- Entidad única: `article`.
- CMS identificable (Arc XP Fusion, WordPress) → JSON embebido tipo `window.Fusion.globalContent`.
- Paywall/consent wall común → flag `paywalled`.
- Sitemap de categoría para delta incremental.

### Precios — Marketplace B2B (alibaba, made-in-china, indiamart)
- Entidades: `product`, `supplier`.
- JSON-LD `Product` + `BreadcrumbList` es la fuente autoritaria.
- Schema alineado cross-source: `price_min_usd`/`max_usd`/`unit`, `moq_quantity`/`unit`, `supplier_*`.
- Currency local → USD vía `EXCHANGE_RATES`.
- Breadcrumb position=1-2 da `industry` + `category_mic`.

---

## 5. Qué NO hacer

- NO escribir código Python ni parsers JS en esta etapa. Esta skill produce solo la spec `.md`.
- NO generar `scrapers/<name>/vendor/` ni tocar `scrapers/` — eso es Etapa 2.
- NO inferir campos que no viste en el HTML scrapeado. Si `genomma lab` especula, marcar `(selector pendiente)` explícito.
- NO exceder 1000 chars en `databrightdata` — es un contrato duro.
- NO inventar URLs para fixtures — usar IDs reales del scrape.
- NO renombrar campos del schema entre versiones — el `§2` es inmutable.

---

## 6. Referencias

- Memoria canónica: `/workspace/docs/specs/memory.md`
- Catálogo: `/workspace/docs/specs/source-scrapers.xlsx`
- Specs existentes como ejemplo: `docs/specs/scrapers/{alibaba,cosme,cosmetics-design,indiamart,made-in-china,olive-young}.md`
