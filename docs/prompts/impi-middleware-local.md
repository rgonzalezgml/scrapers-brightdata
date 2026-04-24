# Prompt — crear middleware local para IMPI México

> Copiá este prompt y pegalo en ChatGPT / Claude / Cursor / Copilot Chat.
> El prompt es autocontenido: el LLM receptor tiene todo el contexto para
> generar el código sin preguntas adicionales.

---

## PROMPT PARA EL LLM

Actúa como un ingeniero Python senior. Tu tarea es crear un **middleware
local en Python** que replique el flujo del script JavaScript que pego
abajo. El middleware debe pegarle directo al portal del IMPI (Instituto
Mexicano de la Propiedad Industrial) desde una máquina local — **sin
usar BrightData, sin proxies** — y devolver las marcas registradas que
pertenezcan a un titular y que estén próximas a vencer en una ventana
temporal dada.

### Contexto de negocio

El portal IMPI México `https://marcia.impi.gob.mx/` permite buscar
marcas registradas. Queremos consultar las marcas del titular
`"Genomma"` que van a vencer en los próximos 90 días, para anticipar
renovaciones. El API interno del portal es público (no requiere login),
pero usa un token CSRF que se extrae de una cookie.

### Blueprint funcional (script JavaScript que CORRE en la consola del navegador)

```javascript
// Extractor de marcas IMPI — marcia.impi.gob.mx
const BASE_URL = "https://marcia.impi.gob.mx";
const TITULAR  = "Genomma";

function http(method, url, body, headers) {
  return new Promise(function(resolve, reject) {
    var xhr = new XMLHttpRequest();
    xhr.open(method, url, true);
    xhr.withCredentials = true;
    if (headers) Object.keys(headers).forEach(function(k) { xhr.setRequestHeader(k, headers[k]); });
    xhr.onload = function() {
      if (xhr.status >= 200 && xhr.status < 300) {
        try { resolve(JSON.parse(xhr.responseText)); } catch(e) { resolve(xhr.responseText); }
      } else { reject(new Error("HTTP " + xhr.status)); }
    };
    xhr.onerror = function() { reject(new Error("Network error: " + url)); };
    xhr.send(body ? JSON.stringify(body) : null);
  });
}
function get(url, headers)        { return http("GET",  url, null,  headers); }
function post(url, body, headers) { return http("POST", url, body, headers); }
function getCookie(name) {
  var match = document.cookie.match(new RegExp("(?:^|; )" + name + "=([^;]*)"));
  return match ? decodeURIComponent(match[1]) : "";
}
function getDateRange(days) {
  days = days || 90;
  var fmt = function(d) { return d.toISOString().split("T")[0]; };
  var today = new Date(), future = new Date();
  future.setDate(today.getDate() + days);
  return { from: fmt(today), to: fmt(future) };
}
function buildPayload(titular, days) {
  var dates = getDateRange(days);
  return {
    _type: "Search$Structured",
    query: {
      number: null, classes: null, codes: null,
      title: null, titleOption: null, goodsAndServices: null,
      name:       { types: ["OWNERS"], name: titular },
      date:       { types: ["DATE_EXPIRY"], date: { from: dates.from, to: dates.to } },
      indicators: null,
      status:     ["REGISTRADO"],
      markType:   null,
      appType:    ["REGISTRO DE MARCA"],
      wordSet:    null,
    },
    images: [],
  };
}
(async function() {
  await get(BASE_URL + "/marcas/search/quick");
  var xsrf = getCookie("XSRF-TOKEN");
  var headers = {
    "Content-Type":     "application/json;charset=UTF-8",
    "X-XSRF-TOKEN":     xsrf,
    "X-Requested-With": "XMLHttpRequest",
  };
  var payload    = buildPayload(TITULAR, 90);
  var searchData = await post(BASE_URL + "/marcas/search/internal/record", payload, headers);
  var searchId   = searchData.id || searchData.searchId;
  var resultData = await post(BASE_URL + "/marcas/search/internal/result",
                              { searchId: searchId, page: 0, size: 50 }, headers);
  var content    = (resultData && resultData.resultPage) ? resultData.resultPage : [];
  content.forEach(function(item) {
    collect({
      denominacion:      item.title || null,
      expediente:        item.applicationNumber || null,
      registro:          item.registrationNumber || null,
      titular:           (item.owners && item.owners[0]) ? item.owners[0] : null,
      fecha_terminacion: (item.dates && item.dates.expiry)       ? item.dates.expiry       : null,
      fecha_cancelacion: (item.dates && item.dates.cancellation) ? item.dates.cancellation : null,
      fecha_solicitud:   (item.dates && item.dates.application)  ? item.dates.application  : null,
      imagen:            item.images || null,
    });
  });
})();
```

### Entregable

Un paquete Python standalone que se pueda ejecutar localmente con
`python -m impi_scraper` y también importar como librería.

#### Estructura de carpetas

```
impi_scraper/
├── impi_scraper/
│   ├── __init__.py            # exporta IMPIClient, SearchInputs, Marca
│   ├── client.py              # core: IMPIClient con search()
│   ├── models.py              # pydantic v2: SearchInputs, Marca, SearchResult
│   ├── errors.py              # excepciones del dominio
│   └── cli.py                 # entry point: python -m impi_scraper
├── tests/
│   ├── conftest.py
│   ├── test_client.py
│   └── fixtures/
│       ├── init_home_response.html
│       ├── search_record_response.json
│       └── search_result_response.json
├── requirements.txt
├── README.md
└── pyproject.toml             # opcional, para hacer pip install -e .
```

#### Dependencias

- Python 3.11+
- `httpx` (sync o async, tu preferencia — sync es más simple)
- `pydantic` >= 2.0
- `pytest` + `respx` (para mockear httpx) o `pytest-mock`

#### Contrato del cliente

```python
from impi_scraper import IMPIClient, SearchInputs

client = IMPIClient()
result = client.search(SearchInputs(
    owner="Genomma",
    expires_within_days=90,
    page_size=50,
))

# result.rows  -> list[Marca]
# result.total -> int (total_elements del API)
# result.search_id -> str (el id devuelto por el record endpoint)
# result.paginated -> bool (True si total > page_size)
```

#### Shape de `Marca` (pydantic model)

Estos son los 10 campos **obligatorios y siempre presentes** en cada
row (`null` explícito para ausentes):

| Campo | Tipo | Origen |
|---|---|---|
| `denominacion` | `str \| None` | `item.title` |
| `expediente` | `str \| None` | `item.applicationNumber` |
| `registro` | `str \| None` | `item.registrationNumber` |
| `titular` | `str \| None` | `item.owners[0]` |
| `fecha_terminacion` | `str \| None` (ISO `YYYY-MM-DD`) | `item.dates.expiry` |
| `fecha_cancelacion` | `str \| None` | `item.dates.cancellation` |
| `fecha_solicitud` | `str \| None` | `item.dates.application` |
| `imagen` | `list \| dict \| None` | `item.images` (pasar verbatim) |
| `scraped_date` | `str` (ISO `YYYY-MM-DD`, UTC) | calculado por el cliente |
| `scraper_flags` | `list[str]` | diagnóstico (siempre lista, puede estar vacía) |

`scraper_flags` aceptados:
- `paginated` — hay más resultados que `page_size`.
- `owner_mismatch` — el `titular` no contiene el `owner` como substring case-insensitive.
- `csrf_retried` — hubo que reintentar el XSRF (cookie vacía en primera pasada).

#### CLI

```bash
python -m impi_scraper --owner "Genomma" --days 90 --output marcas.json
```

Flags:
- `--owner STR` — default `"Genomma"`.
- `--days INT` — default `90`.
- `--page-size INT` — default `50`.
- `--output PATH` — archivo JSON de salida. Si no se pasa, imprime a stdout.
- `--verbose` / `-v` — logs DEBUG; por defecto solo WARNING+.
- `--timeout FLOAT` — default `30.0`.

Output JSON (cuando se usa `--output`):
```json
{
  "search_id": "...",
  "total": 23,
  "paginated": false,
  "scraped_date": "2026-04-22",
  "owner": "Genomma",
  "expires_within_days": 90,
  "rows": [ {...Marca}, ... ]
}
```

#### Flujo técnico

1. **Crear sesión HTTP persistente** — `httpx.Client(cookies=httpx.Cookies(), timeout=30)`. La cookie jar debe persistir entre requests.
2. **Hop 1 — GET init**: `GET https://marcia.impi.gob.mx/marcas/search/quick`. Esto setea la cookie `XSRF-TOKEN`. Ignorar el body (HTML). Status esperado 200.
3. **Extraer XSRF-TOKEN** del jar: `client.cookies.get("XSRF-TOKEN")`. Si vacío, reintentar el GET una vez (flag `csrf_retried`). Si sigue vacío → raise `XSRFMissingError`.
4. **Hop 2 — POST record**:
   - URL: `https://marcia.impi.gob.mx/marcas/search/internal/record`.
   - Headers: `Content-Type: application/json;charset=UTF-8`, `X-XSRF-TOKEN: <cookie>`, `X-Requested-With: XMLHttpRequest`, `Accept: application/json`.
   - Body: payload JSON estructurado (copiá la función `buildPayload` del blueprint; usá el mismo shape exacto: `_type`, `query.name.types=["OWNERS"]`, `query.date.types=["DATE_EXPIRY"]`, `query.status=["REGISTRADO"]`, `query.appType=["REGISTRO DE MARCA"]`).
   - Response JSON: extraer `id` o `searchId`. Si ninguno existe → raise `SearchIdMissingError`.
5. **Hop 3 — POST result**:
   - URL: `https://marcia.impi.gob.mx/marcas/search/internal/result`.
   - Mismos headers que el hop 2.
   - Body: `{"searchId": <id>, "page": 0, "size": page_size}`.
   - Response JSON: `resultPage: [...]`, `totalElements: int`.
6. **Mapear cada `item`** al modelo `Marca` con los 10 campos. Los `null` explícitos no se omiten.
7. **Post-procesamiento**:
   - `scraped_date` = `datetime.now(timezone.utc).date().isoformat()` en cada row.
   - `paginated = total > page_size` → flag en cada row.
   - Si `titular` no contiene `owner` (case-insensitive substring) → flag `owner_mismatch` en esa row.

#### Errores

Excepciones específicas en `impi_scraper/errors.py`:

```python
class IMPIError(Exception): ...
class XSRFMissingError(IMPIError): ...
class SearchIdMissingError(IMPIError): ...
class IMPIAPIError(IMPIError):
    def __init__(self, status_code: int, body: str, url: str): ...
class TimeoutError(IMPIError): ...  # wrapper de httpx.TimeoutException
```

Mapeo:
- `httpx.HTTPStatusError` con `status != 2xx` → `IMPIAPIError(status, text_preview, url)`.
- `httpx.TimeoutException` → `TimeoutError` con contexto.
- XSRF vacío tras reintento → `XSRFMissingError`.
- `searchData.id` y `searchData.searchId` ambos vacíos → `SearchIdMissingError`.

Nunca `except Exception: pass`. Nunca `except:` bare.

#### Tests

Usar `respx` para mockear httpx sin tocar la red:

- `test_client.py::test_happy_path`: mock de los 3 hops, verifica:
  - La cookie `XSRF-TOKEN` del jar se usa en los headers.
  - El body del POST record contiene `query.name.name == owner`.
  - El body del POST result contiene `searchId` devuelto por record.
  - El shape de `Marca` tiene los 10 campos.
  - `scraped_date` es ISO date válido.
- `test_client.py::test_paginated_flag`: `totalElements=100, page_size=50` → todas las rows tienen flag `paginated`.
- `test_client.py::test_owner_mismatch`: row con `owners=["Genommalab Internacional SA"]` y owner `"Genomma"` → flag porque contiene. Row con `owners=["Otro Titular"]` → flag `owner_mismatch`.
- `test_client.py::test_xsrf_missing_raises`: mock del GET home sin setear cookie → `XSRFMissingError`.
- `test_client.py::test_search_id_missing_raises`: POST record devuelve `{}` → `SearchIdMissingError`.
- `test_client.py::test_5xx_raises`: POST result 503 → `IMPIAPIError`.
- `test_cli.py::test_cli_writes_output`: invoca el módulo con `--output` → archivo JSON válido con el shape del CLI output.

#### README.md

Secciones mínimas:
- **Instalación**: `pip install -r requirements.txt` (o `pip install -e .` si hay pyproject).
- **Uso CLI**: ejemplo con flags.
- **Uso programático**: `from impi_scraper import IMPIClient`.
- **Limitaciones conocidas**:
  - No implementa paginación (solo primera página; `paginated` flag indica cuando hay más).
  - Filtro de titular es substring match del lado servidor; puede traer falsos positivos (flag `owner_mismatch` lo señala pero no los descarta).
  - Sin retry automático en 5xx (el caller decide reintentar).
- **Troubleshooting**: qué hacer si `XSRFMissingError` (usualmente significa que el sitio cambió o hay firewall intermedio).

### Estilo

- Type hints en todos los signatures.
- Docstrings cortas (PEP 257) en funciones públicas.
- Comentarios explican **por qué**, no **qué**.
- Un flow lineal en `client.search()`; funciones pequeñas para cada hop.
- Loggin con `logging` estándar (logger `impi_scraper.client`).
- No dependencias extras (sin Django, sin FastAPI, sin pandas).

### Restricciones

- **No inventes campos** que no estén en el blueprint — si la API devuelve
  más, no los emitas.
- **No uses BrightData** — el objetivo es pegar directo desde local.
- **Respetá las URLs exactas** del blueprint; no las cambies.
- **Sin proxies configurados** salvo que el usuario los pase por env var
  (`HTTPS_PROXY`, que httpx respeta por default).

---

## FIN DEL PROMPT

---

## Notas para el usuario que envía este prompt

1. El LLM receptor debería devolver **todos los archivos** listados en la estructura de carpetas. Si solo devuelve uno o dos, pedí el resto explícitamente.
2. **Probá el resultado con**:
   ```bash
   cd impi_scraper
   pip install -r requirements.txt
   pytest -q
   python -m impi_scraper --owner "Genomma" --days 90 --output out.json
   ```
3. Si `out.json` tiene rows con `denominacion` pobladas → el middleware funciona.
4. Si el sitio responde distinto (nuevos campos, XSRF rotado con más frecuencia, etc.), el LLM debería poder iterarlo pasándole el error observado.
