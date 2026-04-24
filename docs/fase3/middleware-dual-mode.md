# Middleware Dual-Mode — Datasets v3 + DCA legacy

> **Tipo**: spec de cambio arquitectónico transversal a `middlewares/core/`.
> **Scope**: capa base del middleware Python (Fase 3).
> **Estado**: propuesto — implementación delegada al agente `middleware-python`.
> **Fecha**: 2026-04-21.
> **Relacionado**: `docs/fase3/README.md`, `docs/fase3/cosmetics-design-handoff.md`, `docs/specs/memory.md` Etapa 3.

Este documento tiene 9 secciones. Las secciones §1-§7 describen el diseño; §8 son los criterios de aceptación copiables al brief del implementador; §9 marca lo que queda fuera de alcance.

---

## 1. Motivación y alcance

### 1.1 El problema

`middlewares/core/client.py` hoy solo habla **BrightData Datasets v3** (endpoint `/datasets/v3/*`, ids formato `gd_...`). Esa es la API moderna, la que BrightData recomienda y la que usan los scrapers que se publican desde **Scraper Studio** en el dashboard.

El usuario tiene scrapers ya publicados en **Data Collectors Archive (DCA)** — la API anterior, marcada por BrightData como *legacy* pero todavía soportada. Los ids son `c_...` (collector) y los endpoints viven en `/dca/*`. Ejemplo concreto: `cosmetics-design` está publicado como collector `c_mo8nphfk1olmzmfuin`.

Consecuencia actual: `middlewares/cosmetics_design/` **no puede disparar** el scraper real hasta que se migre manualmente a Studio. Esa migración toma ~15 min por scraper en la UI del dashboard (New scraper → pegar JS → Save to Production → copiar `gd_...`) y es puramente trabajo de dashboard, no código. Hasta que se haga, el middleware queda bloqueado esperando.

### 1.2 La decisión

Agregar **dual-mode** al `BaseScraperClient`: una misma interfaz pública (`await client.run(inputs) -> Envelope`) que por dentro elige uno de dos transports según configuración de la subclass.

Esto desacopla dos decisiones que hoy están acopladas:

- **Cuándo migrar cada scraper a Studio** (decisión del usuario, trabajo en UI).
- **Cuándo el middleware puede ejercitarse contra el scraper real** (queremos: ya).

### 1.3 Scrapers afectados

| Scraper | Estado actual | Modo de arranque |
|---|---|---|
| `cosmetics-design` | Publicado en DCA (`c_mo8nphfk1olmzmfuin`) | DCA al día 0; v3 cuando se migre |
| Futuros del catálogo gob (`inpi-ar`, `impi`, etc.) | Sin publicar | Cualquiera (la spec decide por scraper) |
| POCs nuevos publicados directo en Studio | Futuro | v3 de entrada |

El dual-mode no es una transición global con cutover — es una coexistencia permanente durante el período en que haya scrapers legacy vivos. Una vez que todos los scrapers estén en Studio, `_DCATransport` puede retirarse (eso es cleanup futuro, no parte de esta spec).

### 1.4 No-objetivos

- No migrar ningún scraper existente a Studio como parte de este cambio (trabajo en UI, no en código).
- No introducir una tercera API de BrightData (p. ej. Web Unlocker, SERP API). Scope fijo: Datasets v3 + DCA.
- No cambiar la interfaz pública del middleware hacia arriba (el repo de agentes y los tests externos no deben tocar una línea).
- No introducir features nuevas en este cambio (cache, retry agresivo, webhooks) — `docs/fase3/README.md` "Regla de oro" sigue vigente.

---

## 2. Arquitectura propuesta

### 2.1 Decisión de diseño

**Strategy pattern por protocolo de transport.** `BaseScraperClient` mantiene su contrato hacia subclasses y consumers; delega las 3 operaciones BrightData-específicas (`trigger`, `poll`, `download`) a un objeto `Transport` inyectado que se elige según `API_MODE` de la subclass.

La decisión está tomada y es definitiva — no discutir alternativas (herencia doble, factory externa, feature flag global). La razón es que:

- El set de métodos a abstraer es pequeño y estable (3 operaciones).
- Subclasses existentes no necesitan saber nada del transport — siguen overrideando solo `_build_brightdata_inputs` y `_build_envelope`, que son puras sobre inputs/rows y no dependen del transport.
- Los tests del base pueden parametrizar por transport con una sola dimensión.

### 2.2 Contrato de `Transport`

```python
# middlewares/core/transports/base.py
class BaseTransport:
    """Protocolo que cada implementación concreta satisface."""

    async def trigger(
        self,
        *,
        api_key: str,
        resource_id: str,                     # gd_... (v3) o c_... (DCA)
        inputs: list[dict[str, Any]],
        http: httpx.AsyncClient,
    ) -> str:
        """Returns snapshot_id (v3) o collection_id (DCA), normalizado como str opaco hacia arriba."""
        ...

    async def poll(
        self,
        *,
        api_key: str,
        job_id: str,
        http: httpx.AsyncClient,
    ) -> dict[str, Any]:
        """Returns {"status": "running|ready|failed", ...}. Normalizado cross-transport."""
        ...

    async def download(
        self,
        *,
        api_key: str,
        job_id: str,
        http: httpx.AsyncClient,
    ) -> list[dict[str, Any]]:
        """Returns rows[] — shape crudo tal como BrightData lo entrega."""
        ...
```

- Cada método recibe dependencias explícitas (api_key, http client). Los transports son **stateless**: una instancia por class-level, reutilizable.
- El transport **no sabe** de `ScraperError` del catálogo del proyecto — levanta sus propios errores tipados internos (`_TransportError` con código normalizado) que el `BaseScraperClient` mapea. Ver §4.3.
- `job_id` hacia arriba es siempre un string opaco — internamente v3 lo usa como `snapshot_id` y DCA como `collection_id`, pero el consumer no se entera.

### 2.3 Dos implementaciones concretas

```
middlewares/core/transports/
├── __init__.py            ← exporta V3Transport, DCATransport, BaseTransport
├── base.py                 ← BaseTransport ABC + _TransportError
├── v3.py                   ← V3Transport (migración de la lógica actual de client.py)
└── dca.py                  ← DCATransport (nueva, basada en scripts/test_connector.py y docs BrightData)
```

**`V3Transport`** es una extracción directa de `_trigger_brightdata`, `_get_progress`, `_fetch_snapshot` que hoy viven en `BaseScraperClient`. Ningún cambio semántico.

**`DCATransport`** es nuevo. Endpoints (ver §4.1):
- Trigger: `POST /dca/trigger?collector=<c_...>&queue_next=1` body `[{...}]`.
- Poll: `GET /dca/dataset?id=<collection_id>` — si devuelve `{"status": "building"}` sigue pendiente; si devuelve array → listo.
- Download: `GET /dca/dataset?id=<collection_id>&format=json`.

### 2.4 Cómo la base delega al transport correcto

`BaseScraperClient` gana:

```python
class BaseScraperClient:
    API_MODE: ClassVar[Literal["v3", "dca"]] = "v3"
    """Qué transport usar. Override en subclass si corre contra DCA."""

    # Existentes:
    SOURCE_NAME: ClassVar[str] = ""
    APIcore: ClassVar[str] = DEFAULT_APIcore
    HTTP_TIMEOUT: ClassVar[float] = DEFAULT_HTTP_TIMEOUT

    # Resuelve el transport en __init__ según API_MODE.
    # Resource id resolution (§3) sustituye al antiguo DATASET_ID único.
```

Internamente `_transport` es elegido de un mapping class-level:

```python
_TRANSPORTS: dict[str, type[BaseTransport]] = {
    "v3":  V3Transport,
    "dca": DCATransport,
}
```

Las 3 operaciones privadas del client ya no implementan la REST plumbing — delegan:

```python
async def _trigger_brightdata(self, inputs):
    await self._ensure_credentials()
    try:
        return await self._transport.trigger(
            api_key=self._api_key,
            resource_id=self._resource_id,
            inputs=inputs,
            http=await self._client(),
        )
    except _TransportError as e:
        raise ScraperError(e.code, e.message, details=e.details) from e
```

Los nombres `_trigger_brightdata` / `_get_progress` / `_fetch_snapshot` se **conservan** como métodos del base porque las subclasses no los llaman directo, pero son el punto natural de mapeo error → `ScraperError`. Esto también minimiza el diff: la subclass existente (cosmetics-design) sigue funcionando sin tocar.

### 2.5 Qué NO se toca

- `_build_brightdata_inputs` y `_build_envelope` de cada subclass **no cambian**. Son puras: transforman pydantic → seeds list y rows → envelope. No conocen el transport.
- `Envelope`, `ScraperError`, `NORMALIZED_CODES`, `error_payload` — sin cambios (solo se amplía el mapeo de errores en §4.3).
- `TOOL_SCHEMA` de cada subclass — sin cambios.
- `CosmeticsDesignInputs` y demás pydantic — sin cambios.
- `build_envelope_for_rows` — sin cambios.
- `trigger` / `get_result` / `run` públicos — sin cambios de firma ni de shape de retorno.
- Tests externos (tests del repo de agentes) — sin cambios.

### 2.6 Diagrama ASCII

```
                          ┌──────────────────────────────────┐
                          │  Repo de agentes (consumer)      │
                          │  from middlewares.cosmetics_...  │
                          │    import trigger, get_result    │
                          └──────────────┬───────────────────┘
                                         │
                       public API unchanged (trigger/get_result)
                                         │
                   ┌─────────────────────▼─────────────────────┐
                   │  CosmeticsDesignClient(BaseScraperClient) │
                   │  - _build_brightdata_inputs(public)       │
                   │  - _build_envelope(rows, public)          │
                   │  - API_MODE = "v3" | "dca"                │
                   └─────────────────────┬─────────────────────┘
                                         │
                          BaseScraperClient delega
                                         │
                                         ▼
                            selects _TRANSPORTS[API_MODE]
                                         │
                ┌────────────────────────┼────────────────────────┐
                │                                                 │
         ┌──────▼──────┐                                   ┌──────▼──────┐
         │ V3Transport │                                   │ DCATransport│
         │  /datasets/ │                                   │   /dca/     │
         │  v3/*       │                                   │   *         │
         │  gd_...     │                                   │  c_...      │
         └──────┬──────┘                                   └──────┬──────┘
                │                                                 │
                │          httpx.AsyncClient                      │
                └────────────────────┬────────────────────────────┘
                                     │
                                     ▼
                           api.brightdata.com
```

---

## 3. Contrato de env vars

### 3.1 Convención de nombres

Regla: **una env var por scraper por modo**. Nombres:

| Env var | Modo | Valor esperado |
|---|---|---|
| `BRIGHTDATA_API_KEY` | ambos | API key (global, compartida) |
| `BRIGHTDATA_DATASET_ID_<SCRAPER>` | `v3` | `gd_...` |
| `BRIGHTDATA_COLLECTOR_ID_<SCRAPER>` | `dca` | `c_...` |

`<SCRAPER>` es el nombre del scraper en **SCREAMING_SNAKE_CASE** (hyphen → underscore, mayúsculas). Ejemplos:

- `cosmetics-design` → `BRIGHTDATA_DATASET_ID_COSMETICS_DESIGN` / `BRIGHTDATA_COLLECTOR_ID_COSMETICS_DESIGN`
- `inpi-ar` → `BRIGHTDATA_DATASET_ID_INPI_AR` / `BRIGHTDATA_COLLECTOR_ID_INPI_AR`

Esta convención extiende la que ya existe hoy para v3 (`BRIGHTDATA_DATASET_ID_COSMETICS_DESIGN` está en `.env.example`) — nada se renombra.

La env var genérica `BRIGHTDATA_COLLECTOR_ID` (sin sufijo) **sigue existiendo** pero se congela como env var exclusiva de `scripts/test_connector.py`, que es un smoke test histórico. El middleware **no** la lee. Documentado en §9.

### 3.2 Declaración en la subclass

Cada subclass declara qué env var usa y en qué modo corre. Propuesta:

```python
# middlewares/cosmetics_design/config.py
from __future__ import annotations
import os

SOURCE_NAME: str = "cosmetics-design"

# v3
DATASET_ID_ENV_VAR:   str = "BRIGHTDATA_DATASET_ID_COSMETICS_DESIGN"
# DCA (nuevo)
COLLECTOR_ID_ENV_VAR: str = "BRIGHTDATA_COLLECTOR_ID_COSMETICS_DESIGN"

def get_dataset_id()   -> str | None: return os.getenv(DATASET_ID_ENV_VAR)
def get_collector_id() -> str | None: return os.getenv(COLLECTOR_ID_ENV_VAR)

def resolve_mode_and_id() -> tuple[Literal["v3","dca"] | None, str | None]:
    """Decide modo + resource id según env vars presentes. v3 gana si ambos."""
    ds  = get_dataset_id()
    col = get_collector_id()
    if ds:                      # v3 gana: ya migraste; ignora DCA.
        return ("v3", ds)
    if col:                     # solo DCA seteado.
        return ("dca", col)
    return (None, None)         # ninguno — INVALID_INPUTS al trigger time.
```

La clase cliente usa ese helper en `__init__`:

```python
class CosmeticsDesignClient(BaseScraperClient):
    def __init__(self, api_key=None, resource_id=None, api_mode=None, http_client=None):
        if api_mode is None or resource_id is None:
            mode, rid = resolve_mode_and_id()
            api_mode    = api_mode    or mode
            resource_id = resource_id or rid
        super().__init__(
            api_key=api_key,
            api_mode=api_mode,
            resource_id=resource_id,
            http_client=http_client,
        )
```

### 3.3 Precedencia cuando ambas están seteadas

**v3 gana.** Razón: el estado final deseado es migrar a Studio. Cuando el usuario puebla `BRIGHTDATA_DATASET_ID_COSMETICS_DESIGN` significa "la migración está hecha, dejá de usar DCA". Este es un comportamiento explícito y testeado (ver §6).

### 3.4 Cuando ninguna está seteada

Al construir el cliente, la ausencia de ambas envs **no** falla — mantenemos el comportamiento actual ("los imports nunca explotan"). El error surge recién en `trigger` time, mapeado a `INVALID_INPUTS` con mensaje explícito:

```
No BrightData resource id configured for source='cosmetics-design'.
Set one of:
  BRIGHTDATA_DATASET_ID_COSMETICS_DESIGN   (for Datasets v3, gd_...)
  BRIGHTDATA_COLLECTOR_ID_COSMETICS_DESIGN (for DCA legacy, c_...)
```

Esto es consistente con la lógica existente en `middlewares/core/client.py:109-114`, que ya levantaba `INVALID_INPUTS` cuando `DATASET_ID` faltaba. Solo cambia el mensaje.

### 3.5 Override programático

El caller puede pasar `api_mode` y `resource_id` explícitos al constructor (usado por tests). Estos overrides **ganan sobre las env vars**. Es decir, la precedencia completa es:

```
argumento explícito al __init__  >  env var específica del scraper  >  None
```

Entre env vars (v3 vs DCA), v3 gana por §3.3.

---

## 4. Mapeo de shapes y errores DCA ↔ v3

### 4.1 Endpoints y payloads

| Operación | v3 | DCA |
|---|---|---|
| **Trigger** URL | `POST https://api.brightdata.com/datasets/v3/trigger?dataset_id=gd_...` | `POST https://api.brightdata.com/dca/trigger?collector=c_...&queue_next=1` |
| **Trigger** body | `[{...inputs...}]` | `[{...inputs...}]` |
| **Trigger** respuesta ok | `{"snapshot_id": "s_..."}` | `{"collection_id": "j_..."}` |
| **Poll** URL | `GET /datasets/v3/progress/<snapshot_id>` | `GET /dca/dataset?id=<collection_id>` |
| **Poll** respuesta pendiente | `{"status": "running"\|"processing"\|"queued"\|"collecting"\|"ready_to_run"}` | `{"status": "building"}` (objeto, no array) |
| **Poll** respuesta ready | `{"status": "ready"\|"done"\|"completed"\|"success"}` | respuesta **es un array** de rows (DCA no tiene endpoint separado de progreso) |
| **Poll** respuesta fail | `{"status": "failed"\|"error", "message"\|"error": str}` | `{"status": "failed"\|"error", ...}` o 4xx/5xx |
| **Download** URL | `GET /datasets/v3/snapshot/<snapshot_id>?format=json` | `GET /dca/dataset?id=<collection_id>&format=json` |
| **Download** respuesta | array de rows o `{"data": [...]}` | array de rows |

**Notas específicas DCA:**

- DCA no expone un endpoint de "progress" separado. La misma URL `/dca/dataset?id=...` responde con un dict `{"status": "building"}` mientras el job está corriendo, y con un **array** cuando termina. El `DCATransport.poll()` detecta esto así:
  - Si la respuesta es un dict con `"status"` y el status es no-terminal → `{"status": "running"}` normalizado.
  - Si la respuesta es un array → `{"status": "ready"}` normalizado.
  - Si es un dict con error → `{"status": "failed", "message": ...}`.
- Como la URL de poll y download es la misma, el transport puede implementar `download` como un re-fetch con `format=json`, o cachear el array que vio al final del poll. Propuesta: **re-fetch** (stateless, evita guardar estado en el transport). Es un round-trip extra pero irrelevante (rows ya están en CDN de BrightData).
- `queue_next=1` en el trigger es un detalle operativo que `scripts/test_connector.py` no setea pero que la docs DCA recomienda para encolar el run. Incluirlo por default.

### 4.2 Normalización del status hacia arriba

El base ya tiene lógica en `CosmeticsDesignClient.get_result` para mapear `bd_status` a un enum interno. Esa lógica se mueve al nivel de `transport.poll`, que devuelve un dict con un `status` **ya normalizado** a una de:

```
"running" | "ready" | "failed"
```

+ opcionalmente `progress_pct: int` (v3 puede derivarlo, DCA típicamente no). El client sigue construyendo la respuesta pública `{"status": "running", "progress_pct": N}` como hoy — pero ahora consume el status ya normalizado del transport, no el raw.

Ventaja: la subclass `CosmeticsDesignClient.get_result` se simplifica — puede borrar el switch de strings sueltos (`"running"|"processing"|"queued"|...`).

### 4.3 Mapeo de errores al catálogo del proyecto

El catálogo `NORMALIZED_CODES` (en `middlewares/core/errors.py`) **no necesita ampliarse**: los códigos existentes cubren ambos modos. Lo que se amplía es la **tabla de mapeo HTTP/status → código**. Propuesta:

| Condición | Código proyecto | Aplica a |
|---|---|---|
| Transport HTTP exception (timeout, connection) | `BRIGHTDATA_ERROR` | ambos |
| 5xx en cualquier endpoint | `BRIGHTDATA_ERROR` | ambos |
| 451 en trigger | `SITE_BLOCKED` | ambos |
| 401 / 403 | `INVALID_INPUTS` (credencial mal setada, no llamamos otra vez) | ambos |
| 4xx genérico en trigger | `INVALID_INPUTS` | ambos |
| 404 en poll | `INVALID_INPUTS` (job_id inválido o expirado) | ambos |
| 4xx genérico en poll/download | `BRIGHTDATA_ERROR` | ambos |
| Response JSON malformado | `BRIGHTDATA_ERROR` | ambos |
| Trigger response sin `snapshot_id` (v3) | `BRIGHTDATA_ERROR` | v3 |
| Trigger response sin `collection_id` (DCA) | `BRIGHTDATA_ERROR` | dca |
| Poll normalizado → `{"status": "failed"}` | `BRIGHTDATA_ERROR` (con message adjunto) | ambos |
| DCA: collection_id devuelve `{"status": "expired"\|"deleted"}` | `INVALID_INPUTS` | dca |
| DCA: array vacío con `len==0` y `meta` ausente | **no es error** — envelope con 0 rows | dca |
| Wall-time agotado del lado del caller | `TIMEOUT` (retriable) — **lo decide el repo de agentes, NO el middleware** | n/a |
| Parser side: `STRUCTURE_CHANGED` | n/a — decisión del scraper JS o de la subclass | n/a |

`STRUCTURE_CHANGED` y `TIMEOUT` **no se generan en el transport** — `STRUCTURE_CHANGED` lo surfacea cada subclass si detecta que los rows no cumplen shape (no es parte de esta spec); `TIMEOUT` lo asigna el consumer/caller que administra el wall-time budget (el repo de agentes, per Regla de oro).

### 4.4 `snapshot_id` uniforme hacia arriba

Clave: el `job_id` que el consumer ve es **opaco**. Concretamente:

- En v3 es el `snapshot_id` de BrightData (`s_...`).
- En DCA es el `collection_id` de BrightData (`j_...`).

El consumer **no distingue** ni necesita distinguir. El middleware:
1. En `trigger()` retorna `{"job_id": "<s|j>_..."}` sin anotar de qué tipo es.
2. En `get_result(job_id)` usa la misma subclass (ya configurada con su `API_MODE`) para pollear/bajar — la subclass ya sabe qué transport usar.

**Corolario**: si un día se migra cosmetics-design de DCA a v3, los `job_id` emitidos antes (formato `j_...`) **dejan de ser válidos** para el nuevo cliente. Esto no es un problema en la práctica (los jobs son ephemeral, TTL de BrightData < días), pero se documenta en el handoff del scraper cuando toque. Fuera del alcance de esta spec.

---

## 5. Impacto en subclasses existentes

Revisado contra `middlewares/cosmetics_design/` real:

### 5.1 `config.py`

- Agregar `COLLECTOR_ID_ENV_VAR` (constante) y `get_collector_id()` (helper), siguiendo el patrón existente de `DATASET_ID_ENV_VAR` / `get_dataset_id()`.
- Agregar `resolve_mode_and_id()` (ver §3.2).

### 5.2 `client.py`

- `__init__` de `CosmeticsDesignClient`: refactor para llamar `resolve_mode_and_id()` si no se pasan overrides; pasar `api_mode` y `resource_id` al `super().__init__`.
- `get_result`: simplificar — el status ya viene normalizado del transport (ver §4.2). El switch de strings (`running|processing|queued|...`) se borra. El client solo hace el mapeo de status normalizado → shape público.
- `trigger`: sin cambios de shape, usa `_trigger_brightdata` como hoy.
- `build_envelope_for_rows`: sin cambios.

### 5.3 `tests/conftest.py`

Hoy el marker `@pytest.mark.brightdata` se salta si falta `BRIGHTDATA_API_KEY` **O** `BRIGHTDATA_DATASET_ID_COSMETICS_DESIGN`. Ahora también debe considerarse live si está seteada `BRIGHTDATA_COLLECTOR_ID_COSMETICS_DESIGN`:

```python
has_key      = bool(os.getenv("BRIGHTDATA_API_KEY"))
has_dataset  = bool(os.getenv("BRIGHTDATA_DATASET_ID_COSMETICS_DESIGN"))
has_coll     = bool(os.getenv("BRIGHTDATA_COLLECTOR_ID_COSMETICS_DESIGN"))
if has_key and (has_dataset or has_coll):
    return  # no saltar
```

Mensaje de skip actualizado para mencionar las dos opciones.

### 5.4 `tests/test_client.py`

Dos cambios:

1. **Parametrizar** los tests que ejercitan el flow trigger/poll/download por modo:
   ```python
   @pytest.mark.parametrize("api_mode,resource_env", [
       ("v3",  "BRIGHTDATA_DATASET_ID_COSMETICS_DESIGN"),
       ("dca", "BRIGHTDATA_COLLECTOR_ID_COSMETICS_DESIGN"),
   ])
   async def test_trigger_happy_path(api_mode, resource_env, monkeypatch): ...
   ```
   Cada caso construye el cliente con `api_mode` explícito y se salta si el env correspondiente no está.

2. **Tests nuevos** específicos de selección de modo (unit, no live):
   - `test_resolve_mode_v3_wins_over_dca` — ambas envs seteadas → `api_mode == "v3"`.
   - `test_resolve_mode_dca_when_only_dca_set`.
   - `test_resolve_mode_none_when_neither_set_surfaces_invalid_inputs`.
   - `test_explicit_api_mode_overrides_env`.

3. Los tests fixture-driven (`test_get_result_done_from_fixture`, `test_envelope_shape`, etc.) **no cambian**: operan sobre `build_envelope_for_rows`, que es agnóstico al transport. Ninguna duplicación de fixtures.

4. Mocks: los transports se pueden mockear inyectando una subclass con `API_MODE` de test + `_transport` swapped, o pasando `http_client=` con `httpx.MockTransport`. **No hace falta duplicar fixtures de snapshot** — el shape de rows es idéntico (el JS scraper emite el mismo output en DCA o v3; BrightData solo cambia el wrapper de la API).

### 5.5 Backwards-compat del cliente cosmetics-design

Escenario | env vars | Modo efectivo | Comportamiento
---|---|---|---
Día 0 (hoy) | solo `BRIGHTDATA_COLLECTOR_ID_COSMETICS_DESIGN` | `dca` | middleware funciona contra DCA
Migración en curso | solo `BRIGHTDATA_DATASET_ID_COSMETICS_DESIGN` | `v3` | middleware funciona contra v3 (comportamiento del pre-cambio)
Transición | ambas seteadas | `v3` | **v3 gana** — la DCA se ignora
Sin configurar | ninguna | error | `INVALID_INPUTS` al trigger time con mensaje explícito (§3.4)

---

## 6. Estrategia de testing

### 6.1 Tests del base (nuevos, en `middlewares/core/tests/`)

Esta carpeta no existe hoy — se crea como parte de esta spec. Motivo: el comportamiento común cross-scraper (selección de transport, manejo de errores HTTP) merece tests propios, no acoplados a cosmetics-design.

Estructura:

```
middlewares/core/tests/
├── __init__.py
├── conftest.py
├── fixtures/
│   ├── v3_trigger_ok.json
│   ├── v3_progress_running.json
│   ├── v3_progress_ready.json
│   ├── v3_snapshot.json
│   ├── dca_trigger_ok.json
│   ├── dca_dataset_building.json
│   └── dca_dataset_ready.json
├── test_transport_v3.py
├── test_transport_dca.py
└── testcore_client.py     ← selección de transport, mapeo de errores
```

Tests mínimos por transport:

- `test_<mode>_trigger_ok` — 200 con body esperado → devuelve el id correcto.
- `test_<mode>_trigger_4xx` → `INVALID_INPUTS` (sin reintento).
- `test_<mode>_trigger_5xx` → `BRIGHTDATA_ERROR` (retriable).
- `test_<mode>_trigger_451` → `SITE_BLOCKED` (solo v3; DCA no documenta 451 pero el mapeo aplica igual).
- `test_<mode>_poll_running` → `{"status": "running"}`.
- `test_<mode>_poll_ready` → `{"status": "ready"}`.
- `test_<mode>_poll_failed` → mapeo a `BRIGHTDATA_ERROR`.
- `test_<mode>_download_array` → rows parseados.
- `test_<mode>_download_wrapped` — v3 acepta `{"data": [...]}`; DCA no lo produce pero mismo guard defensivo.

Tests del base client (`testcore_client.py`):

- `test_transport_selected_by_api_mode` — `API_MODE="dca"` → `_transport is DCATransport`.
- `test_error_mapping_preserves_code` — `_TransportError(BRIGHTDATA_ERROR)` → `ScraperError(BRIGHTDATA_ERROR)` sin re-clasificación.
- `test_resource_id_required_at_trigger_time` — ni env ni override → `INVALID_INPUTS` con mensaje que menciona ambas envs.

Uso de `httpx.MockTransport` para simular respuestas. **Sin mocks de módulos** (no `unittest.mock.patch`) — alineado con la convención "tests sin mocks de BrightData" que el proyecto ya sigue (ver handoff §7).

### 6.2 Tests de integración por scraper (parametrizados)

Los tests live (`@pytest.mark.brightdata`) del scraper se parametrizan por `api_mode` (ver §5.4). Cada combinación se skipea individualmente si la env var correspondiente falta. Esto permite:

- Corridas parciales: si el usuario solo pobló la env DCA → solo pasa el caso DCA.
- Corridas completas: con ambas seteadas corren ambos.

### 6.3 Live tests

Comportamiento para el marker `@pytest.mark.brightdata`:

```
activa si: BRIGHTDATA_API_KEY && (DATASET_ID_<SCRAPER> || COLLECTOR_ID_<SCRAPER>)
```

Antes: requería AND de `API_KEY` y `DATASET_ID`. Después: OR entre los dos resource ids.

### 6.4 Tests de regresión

Criterio no negociable: **antes del merge**, correr el test suite completo de `middlewares/cosmetics_design/tests/` en **modo v3** (con las envs actuales seteadas) y verificar que 19 unit/fixture tests siguen verdes. Cero regresiones. Este es el criterio §8.2.

---

## 7. Rutas y archivos nuevos / modificados

Checklist operativo para el implementador. Cada ítem lleva tag **[NUEVO]**, **[MOD]** o **[DOC]**.

1. **[NUEVO]** `middlewares/core/transports/__init__.py` — re-exporta `BaseTransport`, `V3Transport`, `DCATransport`, `_TransportError`.
2. **[NUEVO]** `middlewares/core/transports/base.py` — ABC `BaseTransport` + `_TransportError` (código + mensaje + details).
3. **[NUEVO]** `middlewares/core/transports/v3.py` — `V3Transport`. Extracción literal de la lógica que hoy vive en `BaseScraperClient._trigger_brightdata` / `_get_progress` / `_fetch_snapshot`. Sin cambios semánticos.
4. **[NUEVO]** `middlewares/core/transports/dca.py` — `DCATransport`. Nueva implementación. Referencia: `scripts/test_connector.py` para el shape real del `/dca/dataset`, y la tabla §4.1.
5. **[MOD]** `middlewares/core/client.py`:
   - Agregar `API_MODE: ClassVar[Literal["v3","dca"]] = "v3"`.
   - Renombrar internamente `self._dataset_id` a `self._resource_id` (el nombre público ya no tiene sentido; `_resource_id` es neutral). **Parámetro del `__init__` existente `dataset_id=` se preserva como alias de `resource_id` para backwards-compat**, deprecado silenciosamente.
   - Agregar `api_mode=None` y `resource_id=None` al `__init__`. Si vienen `None`, mantener comportamiento tolerante actual (no falla al construir).
   - Seleccionar `self._transport` en `__init__` según `API_MODE`.
   - Reescribir `_trigger_brightdata` / `_get_progress` / `_fetch_snapshot` como wrappers que delegan a `self._transport.{trigger,poll,download}` y mapean `_TransportError → ScraperError`.
   - `_ensure_credentials` actualiza el mensaje para citar la env var específica del scraper (no hardcodear `BRIGHTDATA_DATASET_ID_*`, recibir el nombre por la subclass — ver `SOURCE_NAME` + `API_MODE` para construirlo, o mejor: que la subclass lo exponga como `CREDENTIAL_HINT: ClassVar[str]`).
6. **[MOD]** `middlewares/core/errors.py` — ampliar **solo la docstring** de `NORMALIZED_CODES` para documentar que aplica a ambos transports. La tabla de códigos no cambia. Ver §4.3.
7. **[NUEVO]** `middlewares/core/tests/__init__.py`, `conftest.py`, `fixtures/*.json`, `test_transport_v3.py`, `test_transport_dca.py`, `testcore_client.py` — per §6.1.
8. **[MOD]** `middlewares/cosmetics_design/config.py` — agregar `COLLECTOR_ID_ENV_VAR`, `get_collector_id`, `resolve_mode_and_id` (per §3.2 / §5.1).
9. **[MOD]** `middlewares/cosmetics_design/client.py`:
   - Declarar `API_MODE` dinámicamente en `__init__` via `resolve_mode_and_id` (o exponerlo como class attr si es estático por scraper — cosmetics-design elige dinámico porque su modo depende del entorno).
   - Simplificar `get_result` — el switch de BrightData status strings se delega al transport (per §4.2).
   - `_build_brightdata_inputs` y `_build_envelope` sin cambios.
10. **[MOD]** `middlewares/cosmetics_design/tests/conftest.py` — `pytest_collection_modifyitems` considera la env DCA (per §5.3).
11. **[MOD]** `middlewares/cosmetics_design/tests/test_client.py` — parametrizar los tests live, agregar los 4 tests nuevos de selección de modo (per §5.4).
12. **[MOD]** `.env.example`:
    ```diff
    # BrightData — Datasets v3 REST API (usado por middlewares/)
    BRIGHTDATA_API_KEY=your_brightdata_api_key
   +
   +# Dataset id (modo v3 / Scraper Studio). Formato gd_...
   +# Se usa cuando el scraper fue publicado en Scraper Studio (recomendado).
    BRIGHTDATA_DATASET_ID_COSMETICS_DESIGN=your_dataset_id_from_dashboard
   +
   +# Collector id (modo DCA legacy). Formato c_...
   +# Se usa solo si el scraper todavía vive en Data Collectors (API legacy).
   +# Si DATASET_ID_COSMETICS_DESIGN también está seteado, éste se ignora.
   +# BRIGHTDATA_COLLECTOR_ID_COSMETICS_DESIGN=c_...
    ```
13. **[DOC]** `docs/fase3/README.md` — agregar una subsección "Dual-mode (v3 + DCA legacy)" que resume §1.1-§1.3 de este doc y linkea acá. Tabla de scrapers con la columna "modo actual".
14. **[DOC]** `docs/fase3/cosmetics-design-handoff.md`:
    - §3 pasa de "solo Datasets v3" a "dual-mode (default v3, fallback DCA)".
    - §0 se actualiza: el usuario puede poblar **cualquiera** de los dos resource ids.
    - El bloque endpoints de §3 se expande con los DCA.
    - Nota: esto no invalida el handoff ni rompe el "CERRADO 2026-04-22" — se agrega un footer "[ACTUALIZADO YYYY-MM-DD: dual-mode support, ver docs/fase3/middleware-dual-mode.md]".
15. **[DOC]** `middlewares/cosmetics_design/README.md` (si existe; opcional) — mencionar cómo elegir el modo. Si no existe, no crearlo en este cambio (scope creep).

---

## 8. Criterios de aceptación

Copiar al brief del implementador. Cada ítem es observable.

1. **Funcional DCA**: un cliente con `API_MODE="dca"` y `BRIGHTDATA_COLLECTOR_ID_COSMETICS_DESIGN=c_mo8nphfk1olmzmfuin` seteado puede:
   - Ejecutar `trigger(valid_inputs)` y recibir `{"job_id": "j_...", "eta_seconds": int}` real de BrightData.
   - Ejecutar `get_result(job_id)` y recibir secuencia `running → done` (con polling manual desde el caller).
   - Recibir en `status=done` un envelope con la forma exacta definida en `docs/fase3/cosmetics-design-handoff.md` §2.4.

2. **Sin regresión v3**: el test suite completo de `middlewares/cosmetics_design/tests/` pasa sin cambios cuando solo `BRIGHTDATA_DATASET_ID_COSMETICS_DESIGN` está seteado. Los 19 tests verdes previos siguen verdes (19 + los nuevos de §5.4).

3. **Tests dual**: el test suite completo pasa cuando ambas envs están seteadas — los tests live corren en los **dos** modos, el modo efectivo del cliente por default es v3 (por §3.3).

4. **Interfaz pública inalterada**: `grep -rn "from middlewares.cosmetics_design import"` contra un repo cualquiera (agentes o tests) no requiere cambio. Las firmas de `trigger`, `get_result`, `build_envelope_for_rows`, `TOOL_SCHEMA` son idénticas. El shape de los retornos también.

5. **Env example**: `.env.example` declara las dos variantes con comentario que explica cuándo aplica cada una. El `.env` real del usuario sigue válido tal cual está hoy (solo agrega la DCA si quiere usar ese modo).

6. **Catálogo de errores**: `NORMALIZED_CODES` no agrega ni renombra códigos — solo actualiza docstring. Los handoffs ya publicados (cosmetics-design) siguen válidos sin cambios en su tabla de errores.

7. **Mensaje de error útil**: cuando faltan ambas envs, `trigger` retorna `INVALID_INPUTS` con mensaje que cita **las dos** env vars esperadas con sus nombres completos para cosmetics-design.

8. **Smoke test script inalterado**: `scripts/test_connector.py` sigue corriendo usando `BRIGHTDATA_COLLECTOR_ID` (env genérica, sin sufijo) — ese script no se toca en este cambio. Confirmado leyendo el archivo.

9. **Transports son stateless**: dos subclasses distintas (p. ej. `cosmetics_design` + futuro `inpi_ar`) que compartan `API_MODE` reutilizan la misma instancia de `V3Transport` / `DCATransport` sin colisión. Las class-level no guardan estado mutable.

10. **Error mapping completo**: la tabla §4.3 está implementada — cada condición lista surface el código esperado (verificable via `test_transport_<mode>_*` contra `httpx.MockTransport`).

---

## 9. Fuera de alcance

Explicitado para que nadie lo agregue "de paso" durante la implementación:

- **Migrar scrapers de DCA a Studio.** Trabajo en el dashboard de BrightData, no en código. Se hace cuando el usuario decide y al ritmo que quiera. El middleware dual-mode es lo que permite no bloquearse.
- **Tocar `scripts/test_connector.py`.** Smoke test histórico. Sigue usando la env genérica `BRIGHTDATA_COLLECTOR_ID` (sin sufijo) para retrocompat manual. Renombrar o refactorizar ese script es trabajo separado si llega a ser necesario.
- **Retry / cache / webhooks.** Fuera por Regla de oro (`docs/fase3/README.md`): el middleware es stateless y delgado. El repo de agentes maneja retry/cache/TTL. Esta spec no cambia esa división de responsabilidades.
- **Deprecación de `DATASET_ID` como argumento de `__init__`.** Se mantiene como alias silencioso de `resource_id` para no romper código externo. Deprecación real y eliminación del alias es trabajo futuro (requiere búsqueda cross-repo).
- **Otras APIs de BrightData.** Esta spec cubre Datasets v3 + DCA. Web Unlocker, SERP API, Scraping Browser API — no aplican.
- **Migración del test de regresión a CI automatizado.** Hoy los tests se corren local o se skipean en ausencia de envs. La integración con CI con secretos reales es otro track.
- **Cleanup del `DCATransport` cuando todos los scrapers estén en Studio.** Trabajo futuro, no ahora. Hoy el dual-mode es permanente.

---

## Apéndice A — Preguntas abiertas para el usuario

Preguntas cuya respuesta el implementador va a necesitar antes de codear. Si el usuario las contesta acá antes del handoff a `middleware-python`, evitamos roundtrips.

1. **DCA `queue_next=1` por default.** La docs DCA y el comportamiento observable recomiendan setearlo al triggerear. ¿OK poner `queue_next=1` como default del `DCATransport` sin hacerlo configurable en esta iteración? (recomendado: sí; si alguien lo necesita off, puede subclassear).

2. **Nombre del atributo `API_MODE`.** Alternativas consideradas: `TRANSPORT_MODE`, `BRIGHTDATA_API`, `API_FLAVOR`. La spec usa `API_MODE` por brevedad y porque "mode" ya es vocabulario del proyecto (`mode="incremental"` en inputs). ¿Aprobás el nombre?

3. **Alias `dataset_id=` en `__init__`.** ¿Lo mantenemos silencioso (sin DeprecationWarning) o con warning? La spec propone silencioso para no ensuciar los tests existentes; alternativa es emitir `DeprecationWarning` a partir de esta versión.

4. **Manejo de `collection_id` formato.** DCA legacy puede devolver ids que empiezan con `j_...` o con `c_...` según versión del producto. El transport no valida el prefijo — trata al id como opaco. ¿OK? (recomendado: sí, menor acoplamiento).

5. **Cobertura de `test_<mode>_trigger_451` en DCA.** 451 legal block no está documentado en DCA pero el mapeo genérico cubre el caso. ¿Dejamos el test condicionalmente como un `xfail` soft, o lo skippeamos con `reason="DCA does not document 451"`? (recomendado: correrlo igual — defensa en profundidad).

6. **Futuros scrapers en catálogo gob.** Para `inpi-ar`, `impi` y similares, ¿la spec asume que el usuario elige el modo al publicar el scraper en BrightData? ¿O el middleware debe auto-detectar el modo por el prefijo del resource id (`gd_` → v3, `c_`/`j_` → DCA)? La spec actual requiere declaración explícita vía env vars separadas; auto-detección es una simplificación opcional que podría reducir la verbosidad de `.env.example`. Decisión pendiente.
