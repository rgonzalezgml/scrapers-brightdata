# Deuda técnica — middlewares de brightdata-scrapers

> Parking lot de deuda técnica acumulada. Cada entry con: qué, dónde, cómo se arregla, costo estimado, si bloquea algo.
> Ningún item acá es urgente — todos son refactors diferibles hasta que tengamos ancho de banda o se justifiquen.
> Fecha de apertura: 2026-04-23. Revisar cada 30 días y re-priorizar.

---

## Decisión de arquitectura 2026-04-23

**Mantenemos nuestros middlewares en nuestro estilo (patrón 3 — cliente Python importable con estructura de paquete `middlewares/<name>/{client,config,models,tool_schema}.py`).** Los middlewares del repo consumidor `GenommaAI/shared/middleware/` se mantienen en SU estilo (mix patrón 1/2/3 según doc interna). NO se alinean entre sí.

Consecuencia: NO hay refactor a FastAPI standalone, NO hay renaming a `{name}_main.py`, NO hay merge a `shared/middleware/`, NO hay traslado de credentials a `.env.global` de GenommaAI. Cualquier item que antes apareciera en esta deuda técnica como "alinear con convención GenommaAI" queda descartado.

Lo que **sí** sigue siendo deuda técnica:
1. Cómo el agente Python de GenommaAI consume nuestros middlewares cross-repo (distribución/packaging — sección 1 abajo).
2. Deudas internas del código indiamart (sección 2).
3. Deudas transversales que no dependen del estilo (sección 3).

Si en el futuro el equipo cambia de opinión y quiere alinear estilos, abrir un archivo nuevo `deuda_migration.md` con scope específico — NO mezclar acá.

---

## 1. Distribución / packaging cross-repo (única pieza que cruza mundos)

**Qué**: nuestros middlewares viven en `/workspace/brightdata-scrapers/middlewares/<name>/`. Los agentes Python del repo GenommaAI (`/workspace/GeommaAI/agents/*/`) necesitan importarlos. Hoy ese puente **no está formalizado**.

Hay 3 maneras de resolverlo sin forzar cambios de estilo:

**Opción A (más simple): `pip install -e` local**  
Agregar al `requirements.txt` de cada agente que use scrapers:
```
-e file:///workspace/brightdata-scrapers
```
Requiere un `setup.py` / `pyproject.toml` en nuestro repo con el paquete `middlewares` exportado.

**Opción B (mejor long-term): paquete publicado en registry privado**  
Publicar como `genomma-scrapers-middlewares` en PyPI privado o Artifact Registry. Cada release versionado. GenommaAI lo agrega como dep normal `genomma-scrapers-middlewares==0.1.0`.

**Opción C (dev-fast, no-prod): `sys.path` insert**  
Cada agente hace `sys.path.insert(0, "/workspace/brightdata-scrapers")` al arranque. Funciona en dev, frágil en prod (path-dependency).

**Dónde**: todavía no existe. Hoy un agente de GenommaAI que quiera usar `middlewares.indiamart` no lo puede hacer sin una de estas 3 soluciones.

**Cómo se arregla**:
- Opción A: crear `pyproject.toml` en raíz del repo brightdata-scrapers declarando el paquete `middlewares` + `middlewares.core`. ~20 líneas. Costo: 1h.
- Opción B: configurar CI + publicación + versionado. ~4-6h primera vez.
- Opción C: documentar el snippet en CLAUDE.md. 10 min.

**Prerequisito**: decisión del equipo devops sobre si hay registry interno disponible.

**Bloquea**: el consumo real end-to-end desde GenommaAI está hoy sin camino claro. Cuando un agente termine de necesitar el scraper, se va a chocar con esto.

**Recomendación**: arrancar con **Opción A** (pyproject.toml) ahora — desbloquea el flujo, no compromete nada, migrable a B después si se justifica.

---

## 2. Deudas específicas del middleware `indiamart`

### 2.1 Spec §2 violada por key naming del parser v3

**Qué**: spec §2 (schema wire canónico) dice:
```json
{"product": ["product_id", "url", "name_clean", ...]}
```

Pero `scrapers/indiamart/sc_code/parser_code_v3.js:492` emite `product_url` y `product_name_clean` (con prefijo `product_`). El middleware Python compensa con `PRODUCT_ALIASES`. Funciona, pero hay 3 copias del mismo contrato con nombres distintos.

**Dónde**:
- `docs/specs/scrapers/indiamart.md` §2 dice `name_clean` + `url`.
- `scrapers/indiamart/sc_code/parser_code_v3.js:492` emite `product_name_clean` + `product_url`.
- `middlewares/indiamart/models.py` `PRODUCT_ALIASES` renombra.

**Cómo se arregla**:
- **Opción A**: parser v3 emite directo `url` + `name_clean` → elimina la necesidad de aliases. Alinea con §2.
- **Opción B**: actualizar spec §2 para aceptar `product_url` + `product_name_clean` como canónico → elimina drift.

Opción A más limpia. Costo: editar parser + spec §11 fixture + remover aliases del middleware. ~1h.

**Bloquea**: nada hoy. Pero foot-gun — un implementer futuro puede agregar un fix al parser con el nombre equivocado por inercia.

### 2.2 `.toArray()` en Code worker (refactor preventivo)

**Qué**: `sc_code/parser_code_v3.js` usa `.toArray()` en 4 lugares (líneas 87, 208, 210, 225). Funciona porque Code worker de BrightData tiene cheerio real. Pero Browser worker rompe con `.toArray()` (bug observado 2026-04-23, fix en `sc_browser/parser_code_v2.js` a `.map((_, el) => ...).get()`). Si BrightData unifica runtimes o cambia el wrapper del Code worker, estos 4 rompen igual.

**Dónde**: `scrapers/indiamart/sc_code/parser_code_v3.js:87,208,210,225`.

**Cómo se arregla**: refactor preventivo a `.map((_, el) => ...).get()`. Compatible con ambos runtimes. ~10 líneas.

**Costo**: 15 min + validar en preview del Code worker.

**Bloquea**: nada hoy.

### 2.3 Bugs legacy del vendor remanentes (backlog §12 spec)

**Qué**: el parser v3 cerró los 10 bugs principales del handoff. Pero la spec §12 (backlog) lista deuda remanente no cubierta por v3.

**Dónde**: `docs/specs/scrapers/indiamart.md` §12.

**Cómo se arregla**: revisar §12, priorizar, crear v4 cuando se justifique.

**Costo**: depende de ítems específicos.

**Bloquea**: features avanzados (recursión subcat, sitemaps, etc.).

### 2.4 Stage 3 supplier enrichment no implementado

**Qué**: spec §6 define 20 fields de entidad `supplier`. El parser v3 solo emite 4 como FK embedded en product row (`supplier_id`, `supplier_name`, `supplier_city`, `supplier_country="IN"`). El resto (`business_type`, `year_established`, `annual_turnover`, `gst`, `certifications`, `supplier_state`) se difiere.

**Dónde**: no hay Stage 3. Solo Stage 1 (listing) + Stage 2 (detail).

**Cómo se arregla**: agregar Stage 3 que visite `www.indiamart.com/{supplier-slug}/`. Ver `scrapers/indiamart/dom_map.md` sección supplier home para evidencia recolectada. Se puede entrar por flow normal o vía `export.indiamart.com` (pre-filtra Verified Exporters).

**Costo**: 1 nuevo stage JS (~100 líneas) + actualizar middleware para emitir entidad `supplier` separada. ~4-6h.

**Bloquea**: entidad supplier vacía hoy; downstream no puede hacer queries tipo "verified exporters de Delhi con >20 años".

### 2.5 Cobertura de categorías (12 MCATs de ~100,000)

**Qué**: `middlewares/indiamart/config.py:97` tiene 12 MCAT slugs hardcodeados. IndiaMART tiene ~100,000 MCATs totales (5 sub-sitemaps de ~20k cada uno).

**Dónde**: `middlewares/indiamart/config.py` `DEFAULT_MCAT_SLUGS`.

**Cómo se arregla**: 3 opciones:
- (a) Agregar más slugs manualmente según necesidad Genomma. Bajo costo, case-by-case.
- (b) Implementar discovery automático desde `dir.indiamart.com/industry/{slug}.html` → extraer `a[href*="impcat"]` → auto-expandir. ~30 líneas JS en Stage 1b.
- (c) Discovery desde sitemaps XML (`DirMcatSSL_SM0{1-5}.xml`). Más volumen, requiere filtrado por keyword.

**Costo**: (a) 5 min on-demand; (b) 2-3h; (c) 4-6h.

**Bloquea**: nada — los 12 cubren el caso de uso actual.

---

## 3. Deudas transversales (aplican a todos los middlewares)

### 3.1 Tests end-to-end contra BrightData real

**Qué**: los tests actuales usan fixtures estáticas (`tests/fixtures/*.json`). Ningún test corre un trigger real contra BrightData. Si BrightData cambia algo, no nos enteramos hasta que un usuario dispara un run en producción.

**Dónde**: `middlewares/*/tests/`.

**Cómo se arregla**: agregar tests `@pytest.mark.live` que se corran periódicamente (ej. nightly) contra un snapshot real con credentials live. Marcar como `skip` en CI normal; opt-in cuando se quiera validar.

**Costo**: 2-3h por middleware + infra de CI con secretos.

**Bloquea**: feedback loop de regresiones de BrightData hoy es "usuario reporta". No hay alerta temprana.

### 3.2 Logging estructurado

**Qué**: logging básico con stdlib, sin structured fields ni tracing. Debugging en producción es más difícil de lo necesario.

**Dónde**: todos los middlewares.

**Cómo se arregla**: agregar logger namespaced (`brightdata.scrapers.<name>`) con structured fields (job_id, duration, row_count, error_code). Considerar OTel si hay infra disponible.

**Costo**: 1-2h por middleware.

**Bloquea**: nada crítico.

### 3.3 Middleware `impi` prototipo

**Qué**: `middlewares/impi/` es prototipo standalone Python directo (sin BrightData) para sitios .gob que BrightData bloquea. Estado: beta, sin tests, sin validación en producción (ver memoria `project_impi_scraper_mx.md`).

**Dónde**: `middlewares/impi/*`.

**Cómo se arregla**: validar fundamento primero (¿funciona el scrape directo de .gob con proxy residencial?). Si sí, agregar tests y promover. Si no, descartar.

**Costo**: 2-3h de validación + 2-3h de tests si promueve.

**Bloquea**: uso real de impi.

---

## 4. Orden de ataque sugerido

Cuando se decida encarar:

1. **Urgente-ish** (desbloquea algo): §1 (packaging/distribution) → Opción A (pyproject.toml). 1h. Sin esto, GenommaAI no puede consumir los middlewares formalmente.
2. **Higiene** (elimina foot-guns): §2.1 (key naming parser v3 → spec §2), §2.2 (.toArray preventivo). Los dos juntos ~1.5h.
3. **Observabilidad** (ayuda debugging): §3.1 (tests live) + §3.2 (structured logs). 3-4h por middleware, aplicar cuando haya infra CI.
4. **Features nuevos** (desbloquea downstream): §2.4 (Stage 3 supplier enrichment), §2.5 (cobertura amplia), §2.3 (§12 backlog spec).
5. **Prototipos**: §3.3 (impi) — validar o descartar cuando haya ancho de banda.

---

## 5. Mantenimiento de este archivo

- Agregar entrada nueva cada vez que identifiquemos deuda diferida.
- Formato: {qué, dónde, cómo se arregla, costo estimado, prerequisite, bloqueo}.
- Marcar con `~~tachado~~` los items resueltos + fecha + commit/PR.
- Revisar cada 30 días para re-priorizar.
- Si el equipo cambia la decisión de 2026-04-23 (mantener estilos separados) y decide alinearse con GenommaAI, abrir `deuda_migration.md` con scope específico — NO mezclar acá.
- Última actualización: 2026-04-23 (creación inicial).
