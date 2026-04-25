# impi_scraper_mx

Middleware Python standalone para descargar marcas del portal del IMPI México
(`https://marcia.impi.gob.mx`).

Usa el API interno del SPA del portal — el mismo que consume el buscador web
cuando navegás manualmente. No hay BrightData, proxies ni browser: `httpx`
síncrono + `ThreadPoolExecutor` para paralelizar la bajada del detalle.

**Por qué standalone y no `middlewares/impi/`**: BrightData no ejecuta scrapers
contra dominios `.gob.*`. Esta es la variante local (sufijo `_mx`).

---

## Qué descarga

Dado un titular (substring, p.ej. `"GENOMMA LAB"`), trae:

1. **Listado completo** paginado del buscador público — una fila por marca
   con `denominación`, `expediente`, `registro`, `estatus`
   (`REGISTRADO` / `EN TRÁMITE`), `tipo_solicitud`, `titular`, fechas e imagen.
2. **Detalle de expediente** (opcional, `--with-details`) — por cada marca
   trae `/view/{id}` con Clase de Niza + Productos y Servicios, Código de
   Viena, datos del titular (Nombre, Dirección, País) y el historial de
   trámite completo (oficios y promociones anidados).

Ejemplo concreto: `owner="GENOMMA LAB"` devuelve hoy 1,231 marcas (1,027
REGISTRADO + 204 EN TRÁMITE) con 4,890 registros de trámite en total.
Tarda ~43 s.

---

## Instalación

```bash
cd /workspace/impi_scraper_mx
pip install -r requirements.txt
# o editable:
pip install -e .
```

Python 3.11+.

---

## Uso CLI

### Comando mínimo (listado completo, sin detalle, rápido)

```bash
python -m impi_scraper_mx --owner "GENOMMA LAB" --output marcas.json
```

### Con detalle (objetivo completo — expediente, Niza, Viena, historial)

```bash
python -m impi_scraper_mx \
    --owner "GENOMMA LAB" \
    --with-details \
    --concurrency 8 \
    --output marcas_full.json
```

### Prototipar con pocas marcas

```bash
python -m impi_scraper_mx --owner "GENOMMA LAB" --max-marks 50 --with-details
```

### Flags disponibles

| Flag | Default | Descripción |
|---|---|---|
| `--owner STR` | `GENOMMA LAB` | Titular (substring, case-insensitive) |
| `--days INT` | (sin filtro) | Filtra por `DATE_EXPIRY` en `[hoy, hoy+N]` |
| `--page-size INT` | `100` | Tamaño de página del listado (máx ~200) |
| `--max-marks INT` | (sin corte) | Corta el listado tras N filas. Útil para pruebas |
| `--with-details` | off | GET `/view/{id}` por cada marca |
| `--concurrency INT` | `8` | Hilos paralelos para traer detalles (máx 16) |
| `--output PATH` | stdout | Archivo JSON de salida |
| `--timeout FLOAT` | `30.0` | Timeout HTTP por request |
| `-v`, `--verbose` | off | Logs `DEBUG` |

### Shape del JSON de salida

```jsonc
{
  "search_id": "18f2f10d-...",
  "total": 1231,              // lo que reporta el portal
  "fetched": 1231,            // lo que realmente trajimos (puede ser menor con --max-marks)
  "pages": 13,
  "scraped_date": "2026-04-22",
  "owner": "GENOMMA LAB",
  "expires_within_days": null,
  "with_details": true,
  "rows": [
    {
      "id": "RM201001116679",
      "denominacion": "FUNDACIÓN GENOMMA LAB.",
      "expediente": "1116679",
      "registro": "1188893",
      "estatus": "REGISTRADO",
      "tipo_solicitud": "REGISTRO DE MARCA",
      "titular": "FUNDACION GENOMMA LAB, A.C.",
      "clases": [],                        // viene poblado en `detalle.products_and_services`
      "productos_servicios": null,         // idem
      "fecha_solicitud": "2/9/2010",
      "fecha_terminacion": "02/09/2030",
      "fecha_cancelacion": "02/09/2030",
      "imagen": "https://prod.impi.static.tmv.io/...",
      "detalle": {                         // presente solo si --with-details
        "general_information": { "title", "applicationNumber", "registrationNumber",
                                 "applicationDate", "registrationDate", "expiryDate", "appType" },
        "products_and_services": [ { "classes": 41, "goodsAndServices": "EDUCACION; ..." } ],
        "vienna_codes": "26.01.14, 26.01.18, ...",
        "trademark_image": "https://...",
        "owner_information": { "owners": [ { "Name": [...], "Addr": [...], "Cry": [...] } ] },
        "prioridad": [],
        "history_records": [ /* Folio, Año, Descripción, Fechas, + officios/promociones */ ]
      },
      "scraped_date": "2026-04-22",
      "scraper_flags": []
    }
  ]
}
```

Las datas en el detalle son passthrough desde IMPI: los nombres de campo
siguen el shape nativo del portal (camelCase inglés en general, algunos con
tildes españolas dentro de `history_records[].details.officios` y
`.promociones` — p.ej. `"descripciónDeLaPromoción"`).

---

## Uso desde un script Python

El middleware expone tres piezas: `IMPIClient`, `SearchInputs`, `Marca`.
La idea es que un script de orquestación decida **qué** pedirle al
middleware — p.ej. "traer solo las marcas que aún no están terminadas".

### Ejemplo 1 — descarga completa con detalle

```python
from impi_scraper_mx import IMPIClient, SearchInputs

with IMPIClient(timeout=30.0) as client:
    result = client.search(SearchInputs(
        owner="GENOMMA LAB",
        fetch_details=True,
        detail_concurrency=8,
    ))

print(f"{result.fetched}/{result.total} marcas en {result.pages} páginas")
for m in result.rows[:5]:
    print(f"  {m.id}  {m.denominacion!r:30}  {m.estatus}")
```

### Ejemplo 2 — script de orquestación (traer solo las no terminadas)

Este es el patrón recomendado para uso recurrente: el middleware baja
el listado completo (rápido), y el script pide detalle solo de las
marcas que te interesan. En el caso de GENOMMA LAB son ~204 de 1,231,
ahorrando ~6× en requests vs el full (204 detalles vs 1,231).

El ejemplo de abajo hace el detalle secuencial por simplicidad — tarda
~50 s. Si lo necesitás más rápido, envolvé el loop en un
`ThreadPoolExecutor(max_workers=8)` y baja a ~10 s.

```python
"""scripts/impi_mx/fetch_pending.py

Descarga el detalle completo solo de las marcas EN TRÁMITE.
Uso:  python scripts/impi_mx/fetch_pending.py <owner> <output.json>
"""
import json
import sys
from datetime import datetime, timezone

from impi_scraper_mx import IMPIClient, SearchInputs


def main(owner: str, output_path: str) -> None:
    with IMPIClient() as client:
        # 1. Listado crudo — 13 POSTs, ~2 s.
        listing = client.search(SearchInputs(owner=owner, fetch_details=False))
        print(f"listing: {listing.fetched}/{listing.total} en {listing.pages} páginas")

        # 2. Filtro de negocio — solo las que no están terminadas.
        pending = [m for m in listing.rows if m.estatus != "REGISTRADO"]
        print(f"pending: {len(pending)}")

        # 3. Detalle selectivo — solo las filtradas.
        for m in pending:
            m.detalle = client.shape_detail(client.get_detail(m.id))

    payload = {
        "source": "impi_mx",
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "owner": owner,
        "total": listing.total,
        "pending": len(pending),
        "rows": [m.model_dump() for m in pending],
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"wrote {len(pending)} rows → {output_path}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
```

Ejecutar:

```bash
python scripts/impi_mx/fetch_pending.py "GENOMMA LAB" /tmp/pending.json
```

Otros scripts típicos de esta capa:

- `fetch_expiring_soon.py` — filtrá por `fecha_terminacion` dentro de N días
- `fetch_new_since.py`     — marcas cuyo `fecha_solicitud > YYYY-MM-DD`
- `daily_diff.py`          — diff contra snapshot anterior, detalle solo de los cambios

---

## Modelos (pydantic v2)

```python
class SearchInputs(BaseModel):
    owner: str
    expires_within_days: int | None = None   # filtra DATE_EXPIRY en [hoy, hoy+N]
    page_size: int = 100                     # max ~200
    max_marks: int | None = None             # corta el listado (útil para pruebas)
    fetch_details: bool = False
    detail_concurrency: int = 8

class Marca(BaseModel):
    id: str | None
    denominacion: str | None
    expediente: str | None
    registro: str | None
    estatus: str | None                      # "REGISTRADO" | "EN TRÁMITE" | ...
    tipo_solicitud: str | None               # "REGISTRO DE MARCA", ...
    titular: str | None
    clases: list[int]
    productos_servicios: str | None
    fecha_solicitud: str | None
    fecha_terminacion: str | None
    fecha_cancelacion: str | None
    imagen: Any
    detalle: dict[str, Any] | None           # passthrough de /view/{id}, si fetch_details
    scraped_date: str
    scraper_flags: list[str]

class SearchResult(BaseModel):
    rows: list[Marca]
    total: int                               # lo que reporta el portal
    search_id: str
    fetched: int                             # lo que efectivamente trajimos
    pages: int
```

## Errores

Todos heredan de `IMPIError`:

- `XSRFMissingError` — el portal no emitió la cookie `XSRF-TOKEN`.
- `SearchIdMissingError` — `record` no devolvió `id`/`searchId`.
- `IMPIAPIError(status_code, body, url)` — status HTTP no-2xx.
- `TimeoutError` — wrapper de `httpx.TimeoutException`.

---

## Estado actual

**Prototipo validado end-to-end contra el portal real**. No tiene tests
todavía (decisión explícita: se formalizan cuando se integre al agente).

Performance observada: 1,231 marcas + detalle completo en ~43 s desde una
conexión doméstica.

Ver `ARCHITECTURE.md` para el flujo interno y las decisiones de diseño.
