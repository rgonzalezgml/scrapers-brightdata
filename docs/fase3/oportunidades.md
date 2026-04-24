# Oportunidades — backlog de mejoras

Observaciones derivadas de la primera corrida end-to-end exitosa del pipeline
fase 3 (agente → middleware → BrightData DCA → envelope → LLM).

- **Fecha de la corrida que originó este documento**: 2026-04-22.
- **Sessions de referencia**: `44a55e43-e4e6-4120-9cea-a717047787e9`,
  `e45d3fc0-c5ff-4d9c-a96a-e58d9e7e5130` (cosmetics-design, mode=incremental,
  window_days=30, region_filter=North-America).
- **Resultado**: envelope con 43 artículos; el LLM compuso resumen de 5
  artículos priorizados con implicaciones para I+D Genomma.

No es un plan cerrado: es un registro de mejoras candidatas para priorizar
cuando haya ancho de banda. Ordenado por impacto percibido.

---

## 1. Contexto de portfolio Genomma en el system prompt

**Qué pasa hoy**: el LLM infiere implicaciones genéricas ("oportunidad
clara en beauty-from-within", "eje gut-skin sigue siendo...") porque no
conoce el portfolio real de Genomma.

**Qué ganaríamos**: implicaciones accionables y conectadas al portfolio
existente ("reformular ASEPXIA con Omega-7", "explorar línea capilar
ingestible bajo Tafirol", "evaluar saffron en línea anti-AGE premium de
X"). Valor de negocio directo para I+D.

**Cómo**: inyectar en `agent_harness/app.py:_SYSTEM_PROMPT` (o en un
archivo externo leído al arrancar) una descripción corta del portfolio
Genomma: categorías, marcas principales, claims ya usados, gaps conocidos.

**Riesgos**: mantener el portfolio sincronizado. Si cambia, el prompt
queda desactualizado. Considerar referenciar un archivo versionado o una
fuente externa en lugar de hardcodear.

---

## 2. Criterio explícito de ranking en el system prompt

**Qué pasa hoy**: el LLM elige "los 5 más relevantes" con criterio
propio no auditable.

**Qué ganaríamos**: resultados consistentes entre corridas y auditables.
Ejemplo de criterio explícito: "priorizar por recencia + presencia en
retail US + tamaño del RCT + relevancia para categorías Genomma".

**Cómo**: agregar al system prompt una sección "Criterios de priorización"
con pesos. O dejar que el agente repregunte al usuario si el criterio no
está claro.

---

## 3. Parser vendor v1 → deploy en el collector DCA

**Qué pasa hoy**: el vendor (v0) tiene dos bugs documentados:
- `paywalled` se marca con heurística DOM laxa que da false positive en
  hasta 47/47 artículos (run variable según proxy residencial).
- `headline` no siempre se atrapa (casos con error HTTP upstream).

El run del 2026-04-22 NO cayó en saturación de paywall por suerte del
proxy, pero el próximo run puede caer.

**Qué ganaríamos**: eliminar la variabilidad del parser. El v1 ya existe
en el repo (`scrapers/cosmetics-design/sc_*/parser_code_v1.js`) y resuelve
ambos bugs según spec §2 + §4.

**Cómo**: acción manual en el dashboard de BrightData. Abrir collector
`c_mo8nphfk1olmzmfuin`, pestaña **Code**, pegar el contenido de los 4
archivos v1 del repo (`sc_browser/{interaction,parser}_code_v1.js` +
`sc_code/{interaction,parser}_code_v1.js`), **Save**. Re-disparar y
validar que `paywalled` sale correcto.

**Riesgos**: si el v1 introduce un bug nuevo, el vendor histórico queda
como fallback. Conservar el vendor en `scrapers/cosmetics-design/vendor/`
como está (read-only por convención memory.md).

---

## 4. Retry automático cuando el scraper devuelve `PAYWALL_SATURATION`

**Qué pasa hoy**: si BrightData asigna un proxy bloqueado, el run sale
con 47/47 paywalled y el envelope falla. El agente responde "el scraper
falló por saturación de paywall" y el usuario tiene que re-triggerear a
mano.

**Qué ganaríamos**: transparencia para el usuario final. El agente
reintenta 1-2 veces automáticamente; si todos los intentos caen en
`PAYWALL_SATURATION`, entonces sí reporta el fallo real.

**Cómo**: en `middlewares/cosmetics_design/client.py` (o en la capa del
`registry` live del harness), wrappear `get_result` con un retry
configurable (ej. max_retries=2, backoff 60s). Solo reintentar para el
código `PAYWALL_SATURATION`, no para otros errores.

**Riesgos**: si el bug se vuelve sistemático (no variable), el retry
infla costos sin mejorar resultado. Limitar retries con un cap duro.
Complementa a (3), no la reemplaza.

---

## 5. Persistencia del envelope para auditoría

**Qué pasa hoy**: el envelope vive en RAM de la sesión del harness. Si
el cliente cierra o uvicorn reinicia, se pierde.

**Qué ganaríamos**: auditoría posterior, re-consulta sin volver a pagar
un trigger, fixtures reales para tests, comparación entre runs.

**Cómo**: escribir el envelope completo a disco cuando el tool
`cosmetics_design_get_result` devuelve `done`. Ubicación sugerida:
`scrapers/cosmetics-design/results/j_<job_id>.json` (convención ya
establecida en memory.md etapa 2).

**Riesgos**: tamaño acumulado si se corren muchos runs. Considerar TTL
o cap en cantidad de archivos.

---

## 6. Limpiar logs verbose del DCA transport cuando ya no hagan falta

**Qué pasa hoy**: `middlewares/core/transports/dca.py` y
`agent_harness/registry.py` tienen prints detallados con prefijos
`[DCA/...]` y `[REGISTRY/live]` para cada request/response/poll.

**Qué ganaríamos**: logs más limpios en producción. Menos ruido en
uvicorn stdout.

**Cómo**: reemplazar los `print(..., flush=True)` por un logger
estructurado (`structlog`, ya en requirements) y bajar el nivel a DEBUG
por default. Re-habilitar con env var `DCA_DEBUG=1` cuando haga falta
diagnosticar.

**Riesgos**: perder visibilidad cuando haya otro bug del transport.
Mitigación: dejar el path DEBUG accesible vía env var.

---

## 7. Commit de los cambios de 2026-04-22

**Qué pasa hoy**: el repo tiene cambios no commiteados:
- `middlewares/core/transports/{base,v3,dca}.py` (dual-mode + workaround
  `requests`).
- `middlewares/core/client.py` (strategy pattern).
- `middlewares/cosmetics_design/{client,config}.py` + tests actualizados.
- `agent_harness/{app,registry}.py` (HTTP async pattern + logs).
- `docs/fase3/middleware-dual-mode.md` (spec).
- `docs/fase3/README.md` + `cosmetics-design-handoff.md` actualizados.
- `.env` + `.env.example` con nuevas env vars.

**Qué ganaríamos**: estado del repo consistente con la realidad. Evitar
perder trabajo si alguien toca el working tree.

**Cómo**: commits atómicos por tema (dual-mode spec, dual-mode impl,
harness async, fix DCA transport, logs). No commitear `.env` real.

---

## Pendientes estratégicos (no solo fase 3)

- **Fase 1 de `inpi-ar`**: bloqueado esperando a Susy con lista de
  marcas Genomma AR + recorrido del sitio. Scope definido en
  `docs/specs/scrapers/inpi-ar.md` (congelado, pendiente de rehacer sobre
  nueva URL `/marcasconsultas/busqueda`).
- **12 scrapers gob restantes** (MX, CO, US, PE, CL, CR, SV, PA, DO, BR,
  UY, PY). Usar AR como piloto para patrón común en `docs/specs/gob-common.md`.
- **Migrar cosmetics-design a Scraper Studio** (Datasets v3 `gd_...`)
  para sacar la deuda técnica de DCA legacy. 15 min en el dashboard.
