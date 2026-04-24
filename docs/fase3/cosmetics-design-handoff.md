# Handoff Fase 3 — cosmetics-design

> **Destino del trabajo**: `middlewares/cosmetics_design/` (este repo).
> **Consumidor**: repo de agentes. Importa este paquete como dependencia y encima coloca `ServiceRegistry`, persistencia (`scraper_runs` en PostgreSQL), cache TTL y declaración de tool al agente.
> **Agente responsable**: `middleware-python`.
>
> **[ACTUALIZADO 2026-04-21]** Dual-mode support — ahora el middleware habla
> tanto Datasets v3 como DCA legacy. Ver `docs/fase3/middleware-dual-mode.md`.
> Esto **no invalida** el cierre 2026-04-22 del handoff original: el contrato
> público (`trigger`/`get_result`/`TOOL_SCHEMA`) sigue idéntico. Las partes
> tocadas por el cambio llevan nota inline abajo.

---

## 0. Antes de arrancar

Confirmar con el usuario:

1. **Resource id de BrightData** para cosmetics-design. Puede ser cualquiera
   de los dos (dual-mode):
   - `BRIGHTDATA_DATASET_ID_COSMETICS_DESIGN` (formato `gd_...`) si el scraper
     ya está migrado a Scraper Studio, **o**
   - `BRIGHTDATA_COLLECTOR_ID_COSMETICS_DESIGN` (formato `c_...`) si todavía
     vive como colector legacy (estado al día 0 — valor conocido:
     `c_mo8nphfk1olmzmfuin`).
   Si se setean las dos, v3 gana. **No adivinar el id.**
2. **¿Existe `middlewares/core/`?** Si no, cosmetics-design es el POC de Fase 3 y este agente define el patrón que viven después los demás scrapers.
3. **Env var `BRIGHTDATA_API_KEY`** — ruta del `.env` local.
4. **Nombre del paquete Python**: `middlewares/cosmetics_design/` (underscore, por convención Python). El scraper JS sigue en `scrapers/cosmetics-design/` con hyphen.

---

## 1. Contexto del scraper

- **Nombre**: `cosmetics-design` (carpeta JS) / `cosmetics_design` (paquete Python).
- **Categoría**: I+D (noticias de industria cosmética, no precios).
- **Entidad única**: `article`.
- **Fuente**: `https://www.nutraingredients.com/Health-conditions/Beauty-wellness/`.
- **Spec completo**: `docs/specs/scrapers/cosmetics-design.md` (este repo). Leerlo entero antes de implementar.
- **Implementación JS de BrightData**: `scrapers/cosmetics-design/sc_browser/` + `sc_code/` (este repo). Define los campos del output — el middleware debe respetarlos, no reinterpretarlos.

Cadencia de corridas esperada (la decide el repo de agentes, no el middleware): diaria incremental o semanal full-refresh.

---

## 2. Contrato público del paquete

### 2.1 `trigger(inputs) -> dict`

```python
async def trigger(inputs: CosmeticsDesignInputs | dict) -> dict:
    """
    Returns: {"job_id": str, "eta_seconds": int}
    Raises nunca — errores van por shape {"status": "failed", "error": {...}}.
    """
```

### 2.2 `get_result(job_id) -> dict`

```python
async def get_result(job_id: str) -> dict:
    """
    Returns envelope con shape:
      {"status": "running",  "progress_pct": int}
      {"status": "done",     "data": <Envelope>}
      {"status": "failed",   "error": {"code": str, "message": str, "retriable": bool}}
    """
```

### 2.3 Inputs — `CosmeticsDesignInputs` (pydantic v2)

```python
class CosmeticsDesignInputs(BaseModel):
    window_days: int = 180                     # 1..365 — ventana sobre display_date (spec §7)
    max_articles: int = 1000                   # 1..5000 — hard cap (spec §7)
    region_filter: Literal[
        "North-America", "Europe", "Asia-Pacific", "Latin-America", None
    ] = None
    mode: Literal["incremental", "full-refresh"] = "incremental"
```

### 2.4 Envelope normalizado (cuando `status == "done"`)

```python
{
  "source": "cosmetics-design",
  "scraped_at": "2026-04-21T15:30:00Z",
  "inputs": { ... echo de inputs efectivos ... },
  "data": [ { ... article según spec §4 y §6 ... } ],
  "meta": {
    "rows": 123,
    "emitted": 123,
    "skipped_by_reason": { "no_headline": 2, "out_of_window": 45 },
    "paywalled": 5,
    "blocked": 0,
    "errors": 0,
    "started_at": "...",
    "ended_at": "..."
  }
}
```

El schema de `data[]` (campos de `article`) está fijado en `docs/specs/scrapers/cosmetics-design.md` §4 y §6 — **inmutable**. Siempre emitir todas las claves (null explícito si faltan; lista vacía en vez de null para claves lista).

### 2.5 `TOOL_SCHEMA` (JSON Schema consumido por el repo de agentes)

Exportar en `tool_schema.py` un dict que el repo de agentes pueda pasar directo a la API de Anthropic como parte del `tools` array. Debe describir `trigger` y `get_result` como dos tools separadas, con inputs derivados de `CosmeticsDesignInputs`.

---

## 3. Integración con BrightData API (dual-mode)

El middleware dispara el scraper JS vía REST API de BrightData (**no reimplementa parsing**; el parsing vive en `scrapers/cosmetics-design/sc_*`).

Desde 2026-04-21 el middleware soporta los **dos** transports que BrightData
expone (ver `docs/fase3/middleware-dual-mode.md`):

### 3.a Modo v3 (Datasets v3 / Scraper Studio)

- `POST https://api.brightdata.com/datasets/v3/trigger?dataset_id=gd_...` con body `inputs=[{...}]` → devuelve `snapshot_id`.
- `GET https://api.brightdata.com/datasets/v3/progress/<snapshot_id>` → estado (`running`, `ready`, `failed`).
- `GET https://api.brightdata.com/datasets/v3/snapshot/<snapshot_id>?format=json` → payload.

### 3.b Modo DCA (legacy)

- `POST https://api.brightdata.com/dca/trigger?collector=c_...&queue_next=1` con body `[{...}]` → devuelve `collection_id`.
- `GET https://api.brightdata.com/dca/dataset?id=<collection_id>` → `{"status": "building"}` mientras corre; array de rows cuando termina; `{"status": "failed", ...}` en error.
- `GET https://api.brightdata.com/dca/dataset?id=<collection_id>&format=json` → payload final (mismo endpoint, re-fetch).

**Confirmar el `resource_id` exacto con el usuario antes de escribir `config.py`.** El middleware trata el id como opaco (no valida prefijos).

Auth: `Authorization: Bearer ${BRIGHTDATA_API_KEY}`. Variable vía env (`python-dotenv` local, AWS Secrets Manager en prod). La `BRIGHTDATA_API_KEY` es la misma en los dos modos.

---

## 4. Qué NO gestiona el middleware

Responsabilidad del repo de agentes (no del paquete Python):

- **Cache TTL** — el repo de agentes mantiene `scraper_runs(scraper_name, inputs_hash, ...)` y decide si relanza o devuelve cache.
- **Persistencia** — tabla `scraper_runs` en PostgreSQL RDS; el middleware NO lee/escribe esa tabla.
- **ServiceRegistry** — el repo de agentes declara este scraper en su registry.
- **Tool declaration al agente Anthropic** — el repo de agentes consume `TOOL_SCHEMA` y lo pasa al API.
- **Loop de tool-use** — el repo de agentes maneja polling de `get_result` y conversación con el usuario.

El middleware es una **capa delgada sobre BrightData API** + normalización del envelope. Nada más.

---

## 5. Estructura del paquete

```
middlewares/
├── core/                              ← crear si cosmetics-design es el POC
│   ├── __init__.py
│   ├── client.py                       ← BaseScraperClient: _trigger_brightdata, _poll, _fetch_snapshot
│   ├── envelope.py                     ← Envelope (pydantic, source+scraped_at+inputs+data+meta)
│   └── errors.py                       ← ScraperError, NORMALIZED_CODES
└── cosmetics_design/
    ├── __init__.py                     ← from .client import trigger, get_result; from .tool_schema import TOOL_SCHEMA
    ├── client.py                       ← CosmeticsDesignClient(BaseScraperClient); funciones module-level trigger/get_result
    ├── models.py                       ← CosmeticsDesignInputs, Article (pydantic)
    ├── config.py                       ← DATASET_ID, BRIGHTDATA_APIcore, DEFAULT_TIMEOUT
    ├── tool_schema.py                  ← TOOL_SCHEMA dict
    └── tests/
        ├── __init__.py
        ├── conftest.py
        ├── fixtures/
        │   └── snapshot_<id>.json      ← respuesta real de BrightData para tests
        └── test_client.py
```

---

## 6. Catálogo de errores normalizados

| code | retriable | cuándo |
|---|---|---|
| `SITE_BLOCKED` | false | BrightData reporta bloqueo sostenido |
| `STRUCTURE_CHANGED` | false | parser de `sc_code` falla en >20% artículos |
| `TIMEOUT` | true | 90 min wall time sin respuesta |
| `INVALID_INPUTS` | false | validación pydantic falla (no llama a BrightData) |
| `BRIGHTDATA_ERROR` | true | 5xx de la API |
| `PAYWALL_SATURATION` | false | >50% artículos con `paywall_hit` (específico cosmetics-design) |

El middleware solo normaliza — no decide retry ni alarmas. Eso lo hace el consumidor.

---

## 7. Tests

- **Sin mocks** de BrightData API. Fixture con un `snapshot_id` real (corrida conocida del dashboard) cacheado en `tests/fixtures/snapshot_<id>.json`.
- Tests mínimos:
  - `test_trigger_happy_path` — inputs default → devuelve `job_id` válido (contra BrightData si hay key, skip si no).
  - `test_get_result_done_from_fixture` — parsea fixture → envelope correcto, todos los campos de `article` presentes (incluye null explícitos y listas vacías).
  - `test_invalid_inputs_window_days` — `window_days=9999` → `INVALID_INPUTS` sin llamar BrightData.
  - `test_invalid_inputs_region_filter` — valor fuera del enum → `INVALID_INPUTS`.
  - `test_envelope_shape` — envelope tiene exactamente las claves del contrato, sin extras.
- Unit tests de transformación pueden usar dicts inline.
- Usar `pytest-asyncio` con `asyncio_mode = "auto"`.

---

## 8. Qué NO hacer

- **No reimplementar parsing del artículo**. El `sc_code/parser_code_vN.js` ya lo hace según spec §5/§6. El middleware solo consume el payload que BrightData entrega.
- **No modificar el schema de `article`**. Está fijado en el spec §4.
- **No saltarse el paywall**. Si un artículo viene `paywalled=true`, respetar y flaggear.
- **No llamar endpoints directos de nutraingredients.com**. Eso es responsabilidad del scraper JS; el middleware solo habla con BrightData API.
- **No usar MCP** — middleware Python plano.
- **No gestionar cache / DB / ServiceRegistry**. Eso vive en el repo de agentes.
- **No crear `client_v1.py` / `client_v2.py`**. El versionado del middleware es por git commit (a diferencia del scraper JS).
- **No inventar campos** fuera de los definidos en el spec §4 y §6.

---

## 9. Entregables esperados al terminar

1. `middlewares/cosmetics_design/` con las 5 subentidades (`__init__.py`, `client.py`, `models.py`, `config.py`, `tool_schema.py`).
2. `middlewares/core/` si no existía — `BaseScraperClient`, `Envelope`, `errors`.
3. Tests en `middlewares/cosmetics_design/tests/` pasando (con o sin key de BrightData; skip condicionales si no).
4. `requirements.txt` del repo actualizado con `httpx`, `pydantic>=2`, `structlog`, `pytest-asyncio` (si no están).
5. Nota en `docs/fase3/README.md` marcando cosmetics-design como handoff **cerrado** con fecha y commit SHA.

Opcional pero deseable: README breve en `middlewares/cosmetics_design/README.md` con ejemplo de consumo.
