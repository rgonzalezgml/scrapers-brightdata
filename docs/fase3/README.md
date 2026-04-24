# Fase 3 — Middleware Python

Esta carpeta ancla los handoffs de **Fase 3** de cada scraper: el diseño del paquete Python que vive en `middlewares/<name>/` y que el repo de agentes consume como dependencia.

## Fases del ciclo de vida de un scraper

1. **Análisis** — `docs/specs/scrapers/<name>.md` (skill `scraper-spec-analysis`, agente `analyst`).
2. **Implementación JS** — `scrapers/<name>/sc_browser/` + `sc_code/` en DSL de BrightData Scraper Studio (skill `scraper-implementation`, agente `analista-de-scrapers`).
3. **Middleware Python** — `middlewares/<name>/` paquete Python stateless que envuelve el scraper JS y lo expone como cliente importable (agente `middleware-python`). Contrato de diseño: `docs/fase3/<name>-handoff.md`.

## Regla de oro

`middlewares/<name>/` es **stateless y Python-puro**. No gestiona DB, cache, ni declara tools al agente. El repo de agentes importa cada middleware como dependencia y encima pone:

- `ServiceRegistry` / declaración de tool al agente (JSON schema).
- Tabla `scraper_runs` en PostgreSQL con cache TTL.
- Loop de tool-use + conversación con el usuario.

**El middleware no sabe nada de Anthropic API ni de PostgreSQL.** Solo sabe disparar BrightData y devolver un envelope normalizado.

## Arquitectura fijada (2026-04-21)

- Un paquete por scraper: `middlewares/<name>/` (nombre Python-safe con underscore).
- Contrato público: 2 funciones async (`trigger(inputs)` + `get_result(job_id)`) + dict `TOOL_SCHEMA` (JSON schema).
- Envelope uniforme cross-scraper: `{source, scraped_at, inputs, data[], meta}`.
- `data[]` respeta el §2 del spec del scraper — schema inmutable.
- Stack: Python 3.12, `httpx` async, `pydantic` v2, `pytest` + `pytest-asyncio`.
- Auth: `BRIGHTDATA_API_KEY` vía env var.
- Tests: sin mocks de BrightData (fixtures reales de snapshots).

### Dual-mode (v3 + DCA legacy)

`middlewares/core/` soporta los dos transports REST de BrightData:

- **Datasets v3** (`/datasets/v3/*`, ids `gd_...`): la API moderna, lo que
  Scraper Studio publica.
- **DCA legacy** (`/dca/*`, ids `c_...` / `j_...`): la API anterior, todavía
  soportada por BrightData, usada por scrapers publicados antes de Studio
  (p. ej. `cosmetics-design` en `c_mo8nphfk1olmzmfuin`).

La subclass declara su modo vía `API_MODE` (class attr) o `api_mode=` en el
`__init__`, y el resource id viene por env var específica al scraper:

| Env var | Modo |
|---|---|
| `BRIGHTDATA_DATASET_ID_<SCRAPER>` | `v3` |
| `BRIGHTDATA_COLLECTOR_ID_<SCRAPER>` | `dca` |

Si ambas están seteadas, **v3 gana** (asume que la migración a Studio está
hecha). Diseño completo: [`middleware-dual-mode.md`](./middleware-dual-mode.md).

## Consumo desde el repo de agentes

```python
# en shared/services/scrapers.py del repo de agentes
from middlewares.cosmetics_design import trigger, get_result, TOOL_SCHEMA

# Wrappear con cache/DB/ServiceRegistry según convención del repo de agentes
```

## Handoffs por scraper

- [cosmetics-design](./cosmetics-design-handoff.md) — **CERRADO 2026-04-22** (commit SHA: TBD — repo aún sin git inicializado). Middleware en `middlewares/cosmetics_design/`; tests pasando (19 unit/fixture, 1 skipped por requerir BrightData live). Pendiente del usuario: poblar `BRIGHTDATA_API_KEY` + `BRIGHTDATA_DATASET_ID_COSMETICS_DESIGN` y reemplazar el fixture fabricado `tests/fixtures/cosmetics_design_snapshot_s_demo01.json` por un snapshot real cuando se corra el scraper por primera vez.

Scrapers pendientes de handoff: cosme, indiamart, made-in-china, olive-young, alibaba.
