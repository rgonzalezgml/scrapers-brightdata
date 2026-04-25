# impi — registry

Mapa de iteraciones del scraper: archivo versionado → JSON producido → notas.

Spec canónico: _pendiente de redacción formal_ (el `analyst` la produce
post-facto a partir del mini-spec inline entregado en la tarea de v1).
Blueprint funcional: XHR script del compañero (browser console) que
traducimos al DSL de BrightData Scraper Studio.

Vendor (v0, READ-ONLY): `/workspace/scrapers/impi/vendor/` — **vacío**.
IMPI fue bootstrapeado directamente a v1 sin pasar por DB AI (no hay entrega
previa). Si a futuro DB AI genera un andamiaje v0, dejarlo en `vendor/` y
mantener v1 como referencia alternativa.

## Versiones

| Versión | Modo       | Archivos                                                                                 | Fecha       | Result JSON        | Notas |
|---------|------------|------------------------------------------------------------------------------------------|-------------|--------------------|-------|
| v1      | sc_code    | `sc_code/interaction_code_v1.js`, `sc_code/parser_code_v1.js`                            | 2026-04-21  | _pendiente de run_ | Traducción directa del blueprint XHR al DSL. HTTP puro (3 hops: GET init + POST record + POST result). XSRF extraído de `response_headers()['set-cookie']`. Parser stub (payload es JSON, no HTML). |
| v1      | sc_browser | `sc_browser/interaction_code_v1.js`, `sc_browser/parser_code_v1.js`                      | 2026-04-21  | _pendiente de run_ | Mismo flujo que sc_code pero con Browser worker. Fallback cuando el WAF/anti-bot bloquea HTTP puro. Mismo schema §2 de output. |

## Changelog por versión

### v1 (2026-04-21)

Fuente: blueprint funcional del compañero (XHR desde la consola del browser)
+ mini-spec inline entregado en la tarea.

Cambios aplicados (no hay vendor previo del que partir):

- **`sc_code/interaction_code_v1.js`**: implementación completa.
  - Inputs runtime con defaults del mini-spec: `owner` ("Genomma"),
    `expires_within_days` (90), `page_size` (50).
  - Validación temprana con `bad_input()` para inputs malformados (no retry).
  - Hop 1: `navigate(BASE + "/marcas/search/quick")` para que el server setee
    cookie `XSRF-TOKEN`.
  - XSRF extraído del header `Set-Cookie` en `response_headers()` (parser
    defensivo: acepta string único o array, `set-cookie` o `Set-Cookie`).
  - `blocked('xsrf_token_not_in_set_cookie')` si no hay token → la plataforma
    retira con nueva peer session.
  - Hop 2: `request(POST /marcas/search/internal/record)` con headers
    `X-XSRF-TOKEN` + `Cookie: XSRF-TOKEN=...` + `Referer` + `Origin`.
  - Hop 3: `request(POST /marcas/search/internal/result)` con `searchId`.
  - `collect()` directo en interaction_code (no parse()) emitiendo 10 campos
    del schema §2 por fila: `denominacion`, `expediente`, `registro`,
    `titular`, `fecha_terminacion`, `fecha_cancelacion`, `fecha_solicitud`,
    `imagen`, `scraped_date`, `scraper_flags`.
  - Flags posibles: `xsrf_missing`, `record_no_search_id`,
    `result_page_empty`, `paginated`, `owner_mismatch`, `no_results`.
  - Si `resultPage` viene vacío, emite una fila diagnóstica con todos los
    campos null + flag `no_results` para que el pipeline sepa que corrió.
- **`sc_code/parser_code_v1.js`**: stub `return {}`. El flujo JSON no requiere
  parser; el archivo queda por convención del módulo.
- **`sc_browser/interaction_code_v1.js`**: idéntico al sc_code pero con
  `wait()` adicional después del `navigate()` para esperar render del SPA
  (multi-selector 1-trip: `app-root, body, main, #app, .search-container`).
  Sirve como fallback cuando el WAF o anti-bot bloquea el Code worker.
- **`sc_browser/parser_code_v1.js`**: stub idéntico al sc_code.

Reglas del skill aplicadas:
- R1: `navigate()` top-level, no wrappers async.
- R2: multi-selector `wait('a, b, c')` — 1 trip.
- R5: `wait()` default 30s (ni 60s ni 120s).
- R7/R11/R12: no aplican a este scraper porque no hay parser_code HTML (el
  payload es JSON nativo; usamos `?.` y `??` en interaction_code igual).
- R9: `parse()` no se llama.

Pendiente de confirmar con run:
- Shape de `response_headers()['set-cookie']` (string vs array). Parser
  defensivo cubre ambas variantes — documentado en E1.
- Shape de retorno de `request()` (body como string JSON vs objeto
  parseado). Parser defensivo cubre ambas variantes — documentado en E2.
- Paginación desactivada en v1: si `totalElements > page_size` marca flag
  `paginated` pero no trae páginas extras. v2 candidato con `rerun_stage`
  paralelo si aplica (documentado en E3).
- Shape de `item.images`: v1 lo emite 1:1 como llega, pendiente de decidir
  normalización (E4).
- Filtrado client-side de titulares falsos: v1 flaggea pero no descarta (E5).
