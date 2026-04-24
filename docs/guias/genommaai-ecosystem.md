# GenommaAI / Genesis — ecosistema downstream

> Guía del repo **consumidor** de los middlewares de brightdata-scrapers.
> Verificado 2026-04-23. Path absoluto del repo: `/workspace/GeommaAI/`.
> Documento canónico interno: `Genesis_Manual_IT_Arquitectura_v3.md` (51 KB, v3.2 abril 2026).

---

## Qué es

Plataforma multi-agente de **Genomma Lab Internacional** (CRM/ERP/BI/marketing). 12 agentes IA + 1 meta-agente (`14-ai-commander`).

**Stack uniforme**: Python (FastAPI) backend + Next.js frontend + Docker/Fargate deploy. **No hay NestJS** ni otros backends en el ecosistema — todo Python end-to-end.

---

## Estructura del repo

```
/workspace/GeommaAI/
├── shared/                              ← código compartido entre agentes
│   ├── middleware.py                    ← ServiceRegistry singleton (PATRÓN CANÓNICO)
│   ├── middleware/                      ← 40 wrappers de APIs externas
│   │       ├── *_main.py        (9 archivos, FastAPI standalone)
│   │       ├── *_client.py      (cliente importable)
│   │       ├── *_gateway.py     (cliente importable, alt nombre)
│   │       └── *_config.py      (Pydantic Settings por servicio)
│   ├── services/                        ← 7-9 servicios core del registry
│   │       ├── meltwater.py, tiktok_ads.py, sharepoint.py
│   │       ├── supermetrics.py, qlik_cloud.py
│   │       ├── snowflake.py, snow_cortex.py, snowflake_reports.py
│   │       └── pipeline_qlik_snowflake.py, capa_semantica/
│   ├── sap/                             ← integración SAP completa (CO/FI/MM/PP/SD/TR)
│   │       └── middleware_sap.py, sap_bridge.py, api_*.py
│   └── credentials/                     ← .env + llaves RSA (gitignored)
│           ├── .env.global
│           ├── rsa_key_cortex_agent_svc.p8
│           ├── qlik_private_key.pem
│           └── private_key.pem
├── agents/
│   ├── 01-motor-bi-conversacional/      Qlik + Snow Cortex Analyst
│   ├── 02-agente-ejecucion-pdv/         PDV / PSAI
│   ├── 03-supply-chain-inteligente/
│   ├── 04-costeo-tiempo-real/           ← candidato consumidor de scrapers de precios
│   ├── 05-gestion-activa-cash/
│   ├── 06-optimizacion-pauta/           Marketing digital
│   ├── 07-performance-nomina/           Promotoría
│   ├── 08-control-bruto-neto/           SAP heavy (B2N)
│   ├── 09-plataforma-kam/
│   ├── 10-motor-marca-creative-engine/  Creative AI: Kling, Heygen, Veo, etc.
│   ├── 11-nerve-center/
│   ├── 12-rd-innovacion/                ← candidato consumidor de scrapers de I+D
│   └── 14-ai-commander/                 Meta-agente / Jefe de Staff AI
├── apps/
│   ├── genesis/                         App frontend principal
│   └── pulso/
├── docs/
│   ├── DESIGN_SYSTEM_GUIDE.md
│   ├── GENESIS_DEVELOPMENT_GUIDE.md
│   └── PostgresSQL_HowTo.md
├── Semantica/                           Schemas Snowflake (YAML/CSV/XLSX)
├── Genesis_Manual_IT_Arquitectura_v3.md (51 KB, biblia v3.2 abril 2026)
├── API_CONTRACTS_SPRINT.md              (41 KB, contratos de endpoints por agente)
├── ESTADO_AGENTES.md                    (12 KB, qué agente tiene qué pendiente)
├── ENDPOINTS_BY_AGENT.js                Endpoints listados mecánicamente
├── SPRINT_GUIA_EQUIPO.md
├── CONTRIBUTING.md
└── CLAUDE.md                            Guía Claude Code para el repo
```

---

## Tres patrones de middleware conviviendo

### Patrón 1 — `shared/middleware.py` + `shared/services/` (ServiceRegistry singleton)

**El patrón canónico documentado.** Servicios "core" del proyecto: meltwater, tiktok, sharepoint, supermetrics, qlik, snowflake, snow_cortex.

```python
from shared.middleware import services
mentions = await services.meltwater.get_brand_mentions("Suerox")
campaigns = await services.tiktok.get_campaigns()
status = await services.check_all()
```

- Lazy-loaded: cada servicio se instancia en primer acceso.
- Singleton: una sola instancia por proceso.
- Config: `shared/credentials/.env.global` cargado al import.
- Para servicios con auth compleja (KEYPAIR_JWT, OAuth M2M, RSA, etc.).

### Patrón 2 — `shared/middleware/*_main.py` (FastAPI standalone)

**9 archivos**: `kling_main.py`, `creatify_main.py`, `heygen_main.py`, `elevenlabs_main.py`, `veo_api.py`, `seedream_api.py`, `youtube_api.py`, `explodingtopic_api.py`, `auth.py`.

```python
app = FastAPI(title="Kling Video v3 Pro API")

@app.post("/video/generate") async def generate_video(req: VideoRequest): ...
@app.get("/video/status/{request_id}") async def get_status(request_id: str): ...
@app.get("/video/wait/{request_id}") async def wait_for_video(request_id: str): ...
@app.delete("/video/cancel/{request_id}") async def cancel_job(request_id: str): ...
```

- **Microservicios HTTP independientes**, contenedor propio.
- Config separada en `{servicio}_config.py` con `pydantic_settings.BaseSettings`.
- Triplete canónico para async-con-polling: `/generate` + `/status/{id}` + `/wait/{id}`.
- Contract = HTTP/JSON. Cualquier cliente (Python, frontend Next.js, mobile) consume vía fetch.
- Para servicios async / long-running jobs (video, imagen, voice gen).

### Patrón 3 — `shared/middleware/*_client.py` / `*_gateway.py` (cliente Python importable)

**31 archivos**: `anthropic_client.py`, `pubchem.py`, `canva_gateway.py`, `dallE_gateway.py`, `google_ads_monitoreo.py`, `Google_analytics.py`, `producthunt_gateway.py`, `meta_adlibrary.py`, `newsapi_gateway.py`, `pinterest_gateway.py`, `figma_gateway.py`, `removebg_gateway.py`, `openWeather_gateway.py`, etc.

```python
from shared.middleware.anthropic_client import AnthropicClient
client = AnthropicClient()
response = await client.chat(messages, system_prompt, tools)
```

- Módulo Python importable, NO corre como servicio aparte.
- Clases o funciones puras.
- Contract = import Python (Python-only, no portable a otros lenguajes).
- Para wrappers sync de APIs externas (request → response inmediato).

---

## Convenciones de agente

Cada agente sigue el shape definido en `Genesis_Manual_IT_Arquitectura_v3.md` §3:

```
agents/{NN}-{nombre}/
├── backend/
│   ├── routes.py                 ← endpoints FastAPI específicos del dominio
│   └── (más módulos según agente)
├── frontend/
│   ├── config.js                 ← constantes de negocio
│   ├── dataService.js            ← capa de datos (consume backend)
│   └── DataStates.jsx            ← componentes de estado (loading/error/empty)
├── docker-compose.yml            (build context: ../..)
└── (otros)
```

**Backend**: FastAPI con verbos REST específicos del dominio del agente. Ejemplos canónicos del `API_CONTRACTS_SPRINT.md`:

| Agente | Endpoints |
|---|---|
| 01 — Motor BI | `POST /consultar`, `GET /apps` |
| 02 — PDV | `POST /analisis`, `GET /inventario`, `GET /sellout`, `POST /foto/analizar` |
| 03 — Supply Chain | `POST /analisis`, `GET /materiales`, `GET /produccion` |
| 06 — Pauta | `POST /pronostico`, `GET /senales` |

**Frontend**: Next.js 16 + React 19 + Tailwind v4 + Recharts + Genesis Design System.

**Endpoint obligatorio (TODOS los agentes)**: `Genesis_Manual_IT_Arquitectura_v3.md` §5 lo define pero no lo expandimos acá; ver el manual.

---

## Cómo encajan nuestros `brightdata-scrapers/middlewares/`

**Estado actual**: nuestros middlewares están en **patrón 3** (cliente Python importable). Por ejemplo:

```python
from middlewares.indiamart import trigger, get_result, TOOL_SCHEMA
```

Igual que `anthropic_client.py` o `pubchem.py` en GenommaAI. Funciona perfecto si el agente que consume es Python (que es el caso de TODO el ecosistema GenommaAI).

**Naturaleza técnica**: BrightData es async-con-polling (trigger devuelve `job_id`, después polling con `get_result` hasta que el snapshot esté ready). Conceptualmente esto encaja con **patrón 2** (FastAPI standalone, igual que `kling_main.py`). Pero solo conviene migrar a patrón 2 si:

- Algún cliente no-Python necesita consumir el scraper (frontend Next.js direct, mobile, otra plataforma). Hoy esto NO está en el horizonte — todo el stack es Python.
- O se quiere desplegar el middleware como microservicio aparte para escalabilidad/aislamiento.

**Decisión actual** (2026-04-23): mantener patrón 3 hasta que un consumidor lo justifique. Refactor a patrón 2 sería ~50 líneas (un FastAPI envolvente + 3 endpoints + Dockerfile), no es destructivo.

### Mapeo de scrapers a agentes consumidores (presunto)

| Scraper de brightdata-scrapers | Agente consumidor probable | Categoría |
|---|---|---|
| `indiamart` | Agente 04 (Costeo Tiempo Real) o 12 (R&D) | Precios B2B India |
| `alibaba` | Agente 04 o 12 | Precios B2B China |
| `made-in-china` | Agente 04 o 12 | Precios B2B China |
| `cosme` | Agente 12 (R&D) | I+D Japón |
| `cosmetics-design` | Agente 12 (R&D) | I+D News |
| `olive-young` | Agente 12 (R&D) | I+D Korea |

⚠️ **Confirmar con el equipo** qué agente consume cada scraper antes de hacer integraciones específicas. La columna "Categoría" sale del catálogo `docs/specs/source-scrapers.xlsx` (hoja `scrapers`).

---

## Documentos clave del repo GenommaAI a leer si hace falta

Por orden de importancia:

1. **`Genesis_Manual_IT_Arquitectura_v3.md`** — manual canónico v3.2 abril 2026. 10 secciones: Visión, los 13 agentes, Arquitectura por agente, Detalle de módulos, Conexiones entre agentes, Fuentes externas (150+), Design System, Deploy (Docker + Fargate + CI/CD), Seguridad, Países soportados.
2. **`API_CONTRACTS_SPRINT.md`** — endpoints exactos de cada agente con request/response Pydantic. Si vas a integrar con un agente, este es el spec.
3. **`ESTADO_AGENTES.md`** — qué tiene cada agente pendiente, en qué rama trabajar, contexto de sesiones recientes.
4. **`ENDPOINTS_BY_AGENT.js`** — listado mecánico de endpoints (referencia rápida).
5. **`shared/middleware.py`** + **`shared/services/*.py`** — código de los servicios core del registry.
6. **`shared/middleware/{servicio}_main.py`** — referencia del patrón 2 (FastAPI standalone).

---

## Preguntas abiertas para el equipo Genomma

1. ¿Qué agente concreto va a consumir cada scraper de `brightdata-scrapers/middlewares/`? Hoy es presunción.
2. ¿Conviene migrar nuestros middlewares de patrón 3 (importable) a patrón 2 (FastAPI standalone)? Solo si se justifica con un cliente no-Python o necesidad de aislamiento.
3. ¿Las credentials de BrightData deberían vivir en `shared/credentials/.env.global` de GenommaAI? Hoy viven en el `.env` local de cada middleware del repo brightdata-scrapers — duplicación si el agente Python termina cargando ambos.
4. ¿Convenio de naming si migramos a patrón 2: `indiamart_main.py` + `indiamart_config.py` siguiendo el patrón Kling/Heygen?

---

## Mantenimiento de este doc

- Re-verificar cada vez que clonamos / actualizamos el repo `GeommaAI/`. Los archivos `.md` del repo son la fuente de verdad — este es resumen.
- Si la doc oficial cambia (ej. `Genesis_Manual_IT_Arquitectura_v4.md`), actualizar este resumen.
- Si aparece NestJS o cualquier stack no-Python en agentes, actualizar la sección "Stack uniforme".
- Última verificación: 2026-04-23.
