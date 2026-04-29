# Handoff Fase 3 — cosme-ranking-products

> **Destino del trabajo**: `gli_scrapers/cosme_ranking_products/` (este repo).
> **Consumidor**: repo de agentes (GeommaAI). Importa este paquete como dependencia y encima coloca `ServiceRegistry`, persistencia (`scraper_runs` en PostgreSQL), cache TTL y declaración de tool al agente.
> **Agente responsable**: `middleware-python`.

---

## 0. Estado al inicio

Preguntas abiertas resueltas antes de implementar:

1. **Resource id de BrightData** — dual-mode (igual que cosmetics-design):
   - `BRIGHTDATA_DATASET_ID_COSME_RANKING` (formato `gd_...`) si el scraper está en Scraper Studio, **o**
   - `BRIGHTDATA_COLLECTOR_ID_COSME_RANKING` (formato `c_...`) si vive como colector legacy.
   Si se setean las dos, v3 gana.
2. **`product_url` ausente del output** — bug conocido en la integración Stage1→Stage2: el parser pide `input.prod_url` pero Stage 1 manda la URL del producto como `input.url`. El campo NO se incluye en el field_map hasta que se fixee el scraper JS.
3. **Env var auth compartida**: `BRIGHTDATA_API_KEY` (misma que todos los demás middlewares).

---

## 1. Contexto del scraper

- **Nombre JS**: `cosme-ranking-products` (carpeta `bd_scrapers/cosme-ranking-products/`).
- **Nombre Python**: `cosme_ranking_products` (paquete `gli_scrapers/cosme_ranking_products/`).
- **Categoría**: I+D — ranking semanal de productos de belleza en Japón.
- **Entidad única**: `ranking_entry` (una fila del ranking por producto por semana).
- **Fuente**: `https://www.cosme.net/ranking/products`.
- **Arquitectura JS**: sc_code worker, 2 stages.
  - Stage 1: HTTP fetch del listing paginado (10 productos por página, 10 páginas = 100 productos).
  - Stage 2: HTTP fetch del detalle de cada producto.
- **Output**: 100 filas por run (una por producto rankeado esa semana).
- **Cadencia**: semanal (el ranking se actualiza semanalmente en cosme.net).

---

## 2. Contrato público del paquete

### 2.1 `trigger(inputs) -> dict`

```python
async def trigger(inputs: CosmeRankingInputs | dict) -> dict:
    """
    Returns: {"job_id": str, "eta_seconds": int}
    Nunca lanza excepción — errores van por shape {"status": "failed", "error": {...}}.
    """
```

`eta_seconds` default: 900 (el run típico toma 10-15 min para 100 productos con Stage 1 + Stage 2).

### 2.2 `get_result(job_id) -> dict`

```python
async def get_result(job_id: str) -> dict:
    """
    Returns:
      {"status": "running",  "progress_pct": int}
      {"status": "done",     "data": <Envelope>}
      {"status": "failed",   "error": {"code": str, "message": str, "retriable": bool}}
    """
```

### 2.3 Inputs — `CosmeRankingInputs` (pydantic v2)

```python
class CosmeRankingInputs(BaseModel):
    max_pages: int = 10          # 1..10 — número de páginas del listing (10 productos/página)
    mode: Literal["incremental", "full-refresh"] = "incremental"
```

`max_pages` controla cuántos productos se scrapeán (1 página = 10 productos). El scraper JS acepta `page`, `max_pages` y `url` como strings vacíos para usar defaults. El middleware siempre envía el seed con estos tres campos.

### 2.4 Envelope normalizado (cuando `status == "done"`)

```python
{
  "source": "cosme_ranking_products",
  "scraped_at": "2026-04-28T05:30:00Z",
  "inputs": { "max_pages": 10, "mode": "incremental" },
  "data": [
    {
      "rank": 9,
      "rank_change": "hot",
      "product_id": "10124096",
      "product_name": "スピーディーマスカラリムーバー",
      "product_img": "https://...",
      "brand_id": "11624",
      "brand_name": "ヒロインメイク",
      "brand_url": "https://www.cosme.net/brands/11624/",
      "category": "ポイントメイクリムーバー",
      "category_url": "https://www.cosme.net/categories/item/1045/",
      "price_text": "税込価格：924円",
      "price_yen": 924.0,
      "size": null,
      "is_open_price": false,
      "tax_included": true,
      "rating": 6.0,
      "review_count": 16183,
      "release_date": "発売日：2017/2/8",
      "is_best_cosme": true,
      "is_new": false,
      "description": "...",
      "ingredients": "...",
      "all_images": ["https://...", ...],
      "shop_url": "https://...",
      "period_start": "2026/4/16",
      "period_end": "2026/4/22",
      "total_products": 100,
      "scraped_at": "2026-04-28T05:22:33.969Z",
      "input": {"page": "", "max_pages": "", "url": ""}
    }
  ],
  "meta": {
    "rows": 100,
    "emitted": 100,
    "errors": 0,
    "started_at": "...",
    "ended_at": "..."
  }
}
```

El schema de `data[]` está fijado en los 29 campos emitidos por el scraper JS (ver §4 de este handoff). **Inmutable** hasta que el scraper JS sea modificado. Siempre emitir todas las claves (null explícito si faltan; lista vacía para `all_images` si falta).

### 2.5 `TOOL_SCHEMA`

Dos tools: `cosme_ranking_trigger` y `cosme_ranking_get_result`. JSON Schema manual (`additionalProperties: false`). Ver `tool_schema.py`.

---

## 3. Integración con BrightData API (dual-mode)

Igual que cosmetics-design: el middleware habla los dos transports de BrightData.

### 3.a Modo v3 (Datasets v3 / Scraper Studio)

- `POST https://api.brightdata.com/datasets/v3/trigger?dataset_id=gd_...` con body `[{"page": "", "max_pages": "", "url": ""}]`
- `GET https://api.brightdata.com/datasets/v3/progress/<snapshot_id>`
- `GET https://api.brightdata.com/datasets/v3/snapshot/<snapshot_id>?format=json`

### 3.b Modo DCA (legacy)

- `POST https://api.brightdata.com/dca/trigger?collector=c_...&queue_next=1` con body `[{"page": "", "max_pages": "", "url": ""}]`
- `GET https://api.brightdata.com/dca/dataset?id=<collection_id>` — polling
- `GET https://api.brightdata.com/dca/dataset?id=<collection_id>&format=json` — payload final

**Precedencia env vars**: `BRIGHTDATA_DATASET_ID_COSME_RANKING` (v3) gana sobre `BRIGHTDATA_COLLECTOR_ID_COSME_RANKING` (DCA) si ambas están seteadas.

Auth: `Authorization: Bearer ${BRIGHTDATA_API_KEY}` (compartida).

### 3.c Seed enviado a BrightData

```json
[{"page": "", "max_pages": "<N>", "url": ""}]
```

Donde `<N>` es `str(inputs.max_pages)` si `max_pages < 10`, o `""` (default del scraper) cuando es el máximo. `page` y `url` siempre `""` (defaults del scraper).

---

## 4. Reglas de post-procesamiento

### 4.1 Campos del output real (29 campos)

| Campo JSON | Tipo Python | Columna DDL | Notas |
|---|---|---|---|
| `rank` | `int \| None` | `NU_RANK` | |
| `rank_change` | `str \| None` | `TX_RANK_CAMBIO` | "hot", "up", "down", "same", etc. |
| `product_id` | `str \| None` | `ID_PRODUCTO` | |
| `product_name` | `str \| None` | `NM_PRODUCTO` | Texto japonés |
| `product_img` | `str \| None` | `URL_IMG_PRINCIPAL` | |
| `brand_id` | `str \| None` | `ID_MARCA` | |
| `brand_name` | `str \| None` | `NM_MARCA` | |
| `brand_url` | `str \| None` | `URL_MARCA` | |
| `category` | `str \| None` | `NM_CATEGORIA` | |
| `category_url` | `str \| None` | `URL_CATEGORIA` | |
| `price_text` | `str \| None` | `TX_PRECIO_RAW` | Texto japonés |
| `price_yen` | `float \| None` | `NU_PRECIO_YEN` | |
| `size` | `str \| None` | `TX_TALLA` | |
| `is_open_price` | `bool \| None` | `FL_PRECIO_ABIERTO` | |
| `tax_included` | `bool \| None` | `FL_INCLUYE_IVA` | |
| `rating` | `float \| None` | `NU_RATING` | |
| `review_count` | `int \| None` | `NU_RESENAS` | |
| `release_date` | `str \| None` | `TX_FECHA_LANZAMIENTO` | Texto japonés "発売日：YYYY/M/D" |
| `is_best_cosme` | `bool \| None` | `FL_BEST_COSME` | |
| `is_new` | `bool \| None` | `FL_NUEVO` | |
| `description` | `str \| None` | `TX_DESCRIPCION` | |
| `ingredients` | `str \| None` | `TX_INGREDIENTES` | |
| `all_images` | `list[str]` | `DS_IMAGENES` | VARIANT. Nunca null → lista vacía si falta |
| `shop_url` | `str \| None` | `URL_TIENDA` | |
| `period_start` | `str \| None` | `DT_PERIODO_INICIO` | Formato "YYYY/M/D" |
| `period_end` | `str \| None` | `DT_PERIODO_FIN` | Formato "YYYY/M/D" |
| `total_products` | `int \| None` | `NU_TOTAL_RANKING` | Siempre 100 |
| `scraped_at` | `str \| None` | `DT_SCRAPING` | ISO 8601 UTC con ms |
| `input` | `dict \| None` | `DS_INPUT` | VARIANT. Metadatos del job |

**Nota**: `product_url` **NO está** en el output actual. Se agregará cuando se fixee el Stage2 del scraper JS (ver §0).

### 4.2 Coerción de filas

Para cada fila raw de BrightData:
1. Si la fila no es un `dict` → contarla como `error` y saltarla.
2. Para cada campo de `RANKING_ENTRY_FIELDS`: si ausente → `null` (o `[]` para `all_images`).
3. Para `all_images`: si `None` → `[]`; si no es lista → envolver en lista.
4. Validar con pydantic `RankingEntry` (permisivo: `extra="allow"`).
5. No hay lógica de windowing — el ranking es semanal, el dato completo es siempre relevante.

### 4.3 SnowflakeMapper

```python
FIELD_MAP = {
    "rank":           "NU_RANK",
    "rank_change":    "TX_RANK_CAMBIO",
    "product_id":     "ID_PRODUCTO",
    "product_name":   "NM_PRODUCTO",
    "product_img":    "URL_IMG_PRINCIPAL",
    "brand_id":       "ID_MARCA",
    "brand_name":     "NM_MARCA",
    "brand_url":      "URL_MARCA",
    "category":       "NM_CATEGORIA",
    "category_url":   "URL_CATEGORIA",
    "price_text":     "TX_PRECIO_RAW",
    "price_yen":      "NU_PRECIO_YEN",
    "size":           "TX_TALLA",
    "is_open_price":  "FL_PRECIO_ABIERTO",
    "tax_included":   "FL_INCLUYE_IVA",
    "rating":         "NU_RATING",
    "review_count":   "NU_RESENAS",
    "release_date":   "TX_FECHA_LANZAMIENTO",
    "is_best_cosme":  "FL_BEST_COSME",
    "is_new":         "FL_NUEVO",
    "description":    "TX_DESCRIPCION",
    "ingredients":    "TX_INGREDIENTES",
    "all_images":     "DS_IMAGENES",
    "shop_url":       "URL_TIENDA",
    "period_start":   "DT_PERIODO_INICIO",
    "period_end":     "DT_PERIODO_FIN",
    "total_products": "NU_TOTAL_RANKING",
    "scraped_at":     "DT_SCRAPING",
    "input":          "DS_INPUT",
}
VARIANT_FIELDS = {"DS_IMAGENES", "DS_INPUT"}
```

Tabla: `DEV_STG.GNM_MEX.SRC_COSME_RANKING_HIST`.

---

## 5. Límites operativos

| Parámetro | Valor |
|---|---|
| Filas por run | 100 (10 páginas × 10 productos) |
| ETA típica | 900 s (15 min) |
| Cadencia recomendada | Semanal |
| `max_pages` máximo | 10 (hard cap: el ranking tiene 10 páginas) |
| Timeout de polling (runner) | 1800 s (30 min, margen 2×) |

No hay `PAYWALL_SATURATION` — cosme.net no tiene paywall. No hay `window_days` — el ranking es siempre el más reciente. No hay `region_filter` — el ranking es global de Japón.

---

## 6. Naming

| Concepto | Valor |
|---|---|
| Paquete Python | `gli_scrapers/cosme_ranking_products/` |
| Source en envelope | `cosme_ranking_products` |
| Tabla Snowflake | `DEV_STG.GNM_MEX.SRC_COSME_RANKING_HIST` |
| Tool trigger | `cosme_ranking_trigger` |
| Tool get_result | `cosme_ranking_get_result` |
| Env var v3 | `BRIGHTDATA_DATASET_ID_COSME_RANKING` |
| Env var DCA | `BRIGHTDATA_COLLECTOR_ID_COSME_RANKING` |
| Env var auth | `BRIGHTDATA_API_KEY` (compartida) |

---

## 7. Entregables

1. `gli_scrapers/cosme_ranking_products/__init__.py`
2. `gli_scrapers/cosme_ranking_products/models.py` — `CosmeRankingInputs`, `RankingEntry`, `RANKING_ENTRY_FIELDS`, `RANKING_LIST_FIELDS`
3. `gli_scrapers/cosme_ranking_products/config.py` — dual-mode, `SnowflakeMapper`
4. `gli_scrapers/cosme_ranking_products/client.py` — `CosmeRankingClient`, module-level `trigger` / `get_result`
5. `gli_scrapers/cosme_ranking_products/tool_schema.py` — `TOOL_SCHEMA`
6. `gli_scrapers/cosme_ranking_products/runner.py` — usa `runner_base`
7. `gli_scrapers/cosme_ranking_products/tests/__init__.py`
8. `gli_scrapers/cosme_ranking_products/tests/conftest.py`
9. `gli_scrapers/cosme_ranking_products/tests/fixtures/cosme_ranking_snapshot_demo01.json`
10. `gli_scrapers/cosme_ranking_products/tests/test_client.py`

---

## 8. Qué NO hace el middleware

- No reimplementa parsing del HTML/JSON de cosme.net — eso vive en `bd_scrapers/cosme-ranking-products/sc_code/`.
- No gestiona cache, DB, ServiceRegistry ni tool declaration al agente — eso es responsabilidad del repo consumidor.
- No aplica `window_days` — el ranking semanal siempre es actual; el windowing por fecha de ranking lo aplica el repo consumidor si lo necesita.
- No llama directamente a cosme.net — solo habla con BrightData API.
- No lanza excepciones públicas — todo error va por `{"status": "failed", "error": {...}}`.
