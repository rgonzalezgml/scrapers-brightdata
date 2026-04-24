# impi — spec
https://marcia.impi.gob.mx
Proveedor: IMPI México
Categoría: I+D
Función: registros por marcas

## databrightdata

### 1.
IMPI México I+D. Entidad `marca` (titular inline). Consulta pública del portal MARCIA por titular. Señales: denominación, expediente, registro, estatus, tipo de solicitud, titular, clases, productos/servicios, fechas, imagen y detalle opcional. No usa BrightData.

### 2.
```json
{"marca":["id","denominacion","expediente","registro","estatus","tipo_solicitud","titular","clases","productos_servicios","fecha_solicitud","fecha_terminacion","fecha_cancelacion","imagen","detalle","scraped_date","scraper_flags"]}
```

### 3.
- Home público: `https://marcia.impi.gob.mx/marcas/search/quick`
- Crear búsqueda: `POST /marcas/search/internal/record`
- Leer resultados: `POST /marcas/search/internal/result`
- Detalle opcional: `GET /marcas/search/internal/view/{id}`
- Middleware local Python `impi_scraper_mx`; no BrightData, no proxy, no credentials.

## genomma lab

### 1.
Scraper IMPI México para Investigación y Desarrollo (I+D) de Genomma Lab, categoría registros por marcas. Propósito: consultar el portal público MARCIA del Instituto Mexicano de la Propiedad Industrial para monitorear marcas asociadas a titulares del grupo Genomma y ventanas de vencimiento próximas. El output es una fila por marca devuelta por el portal.

### 2.
Modo de conexión. Este módulo es atípico frente al resto de `middlewares/`: no ejecuta un collector BrightData. El middleware `middlewares/impi` adapta el paquete local `impi_scraper_mx`, que usa `httpx` contra el API interno del portal público. `trigger()` ejecuta la búsqueda completa de forma síncrona en un worker thread, guarda el envelope en memoria y devuelve `eta_seconds=0`; `get_result()` solo consulta esa caché por `job_id`. No requiere `BRIGHTDATA_API_KEY`, `DATASET_ID` ni `COLLECTOR_ID`.

### 3.
Inputs públicos aceptados por el middleware: `owner` string no vacío, default `Genomma`; `expires_within_days` entero 1..3650, default 90; `page_size` entero 1..200, default 50; `mode` enum `incremental` o `full-refresh`, default `incremental`. `mode` es solo hint de caché del harness y no cambia el comportamiento del portal.

### 4.
Pipeline. El cliente obtiene cookie XSRF desde `/marcas/search/quick`, crea la búsqueda con `/record`, pagina resultados con `/result` y mapea cada item a `Marca`. Si `fetch_details` se usa desde el paquete standalone, enriquece filas con `/view/{id}` en paralelo. El middleware de agentes usa el listado con los inputs públicos actuales.

### 5.
Campos de salida. `id`, `denominacion`, `expediente`, `registro`, `estatus`, `tipo_solicitud`, `titular`, `fecha_solicitud`, `fecha_terminacion`, `fecha_cancelacion` e `imagen` vienen del listado del portal. `clases` es lista de enteros cuando el portal la expone. `productos_servicios` viene del listado si existe. `detalle` es passthrough del detalle opcional y puede ser null. `scraped_date` es fecha UTC de corrida. `scraper_flags` es lista; flags conocidos: `owner_mismatch`, `detail_http_{status_code}`, `detail_error`.

### 6.
Errores. Fallas del portal o del paquete local (`IMPIError` y subclases) se exponen como `BRIGHTDATA_ERROR` para mantener el contrato común del harness, aunque BrightData no participe. Inputs inválidos se exponen como `INVALID_INPUTS` sin llamar al portal. No se deben loggear cookies ni tokens XSRF.

### 7.
Backlog.
- Documentar fixtures reales de Genomma Lab con fecha de observación y conteos por estatus.
- Decidir si el middleware público debe exponer `fetch_details`, `max_marks` y `detail_concurrency` como inputs agent-facing.
- Alinear `source` del envelope (`impi`) con un nombre explícito `impi_mx` si se agregan otros países IMPI/INPI.
