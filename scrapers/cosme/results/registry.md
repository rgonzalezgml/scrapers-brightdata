# cosme — registry de versiones e iteraciones

Mapa `archivo → versión` del scraper cosme. Una fila por corrida. La versión
más nueva abajo. Versiones anteriores **no se borran**: quedan para A/B y
rollback.

| Versión | Fecha | Modo | Seed / Fixture | Estado | Notas / Gap cerrado |
|--------:|-------|------|---------------|--------|---------------------|
| v0 (vendor) | 2026-04-21 | sc_browser + sc_code | generado por DB AI | archivado | Baseline. No editar nunca. Stage 1 vendor falla con `{"status":"empty"}` cuando la seed cae en `/bestcosme/archive/{current_year}/` — ese path devuelve 404 en el sitio. Ver E6 en `errors.md`. |
| v1 | 2026-04-22 | sc_browser + sc_code | `https://www.cosme.net/bestcosme/archive/{year}/` (middleware default) | **descartada — preview no guardó** | **sc_browser**: fix E6 (archive-root 404 fallback a `/bestcosme/` hub). **sc_code**: copia vendor + fix parcial E7 en breadcrumb Source-1 (array de DOM elements crudos en vez de Cheerio pre-wrapped). El fix E7 es correcto pero no era el bloqueo real del preview; ver E8. Logs de diagnóstico añadidos 2026-04-22 (prefijos `[S1-BROWSER/INT]` y `[S1-BROWSER/PARSE]`, sin cambio semántico). |
| v2 (sc_code only) | 2026-04-22 | sc_code | idem | **pendiente de preview/save** | **sc_code**: fix E8. Interaction code cambia `collect(parse({html, shift_jis_fallback}))` (canal inválido — viola R2 runtime) por `load_html(decoded_html); collect(parse())` (patrón documentado en skill §4/§7). Parser elimina el read de `input.shift_jis_fallback` (nunca llegó por canal válido); la detección de mojibake sigue self-contained vía `$('body').text()`. Fix E7 (breadcrumb array) se mantiene como defence-in-depth. `sc_browser/` no cambia — v1 sigue vigente para Stage 1. Logs de diagnóstico añadidos 2026-04-22 (prefijos `[S2-CODE/INT]` y `[S2-CODE/PARSE]`, sin cambio semántico). |

## Próximo trigger esperado para v1

Llamar al middleware con inputs default (equivalente al JSON que manda al
collector `c_mo7zv65x2914uyi2n4`):

```python
from middlewares.cosme import trigger, get_result

job = await trigger({})             # defaults: award_year = current year
# → seed URL = https://www.cosme.net/bestcosme/archive/2026/ (o el año corriente)

res = await get_result(job["job_id"])
assert res["status"] == "done"
assert res["meta"]["emitted_by_entity"]["product"] > 0
```

Inputs alternativos útiles para smoke-test acotado (no salta el flujo
completo de 60+ categorías):

```python
await trigger({"category": "skincare", "crawl_limit": 2})
await trigger({"award_year": 2024})   # año cerrado, ejercita el branch
                                       # "archive-root 200 OK" sin pasar por
                                       # el fallback E6.
await trigger({"award_year": 2025})   # 404 → fuerza fallback E6 a /bestcosme/.
```

Criterio de éxito para validar v1:

- `meta.rows > 0` y `meta.emitted_by_entity.product > 0`.
- Al menos 1 row con `category_ids` o `rankings` poblados (para confirmar
  que el discovery enganchó el branch `grand` / `hall` / `rookie` /
  `category` al menos una vez).
- Ninguna row con `scraper_flags` conteniendo `blocked_retried` para la
  seed misma (la seed nunca debería contener indicios de bloqueo en JP).
