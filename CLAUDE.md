# Claude Code — Project Context

> Shared project policy lives in `AGENTS.md`. This file adds Claude-specific context on top of it.

---

## Project Vision

**brightdata-scrapers** es una plataforma de scraping modular de Genomma Lab. Cada scraper es un módulo independiente bajo `bd_scrapers/` con su propia lógica de extracción, transformación y entrega de datos. Los scrapers usan BrightData como infraestructura de proxy y Scraping Browser para sitios con renderizado JavaScript.

**Repo consumidor (downstream)**: los middlewares de este repo se importan desde el repo `GeommaAI` (Genesis), una plataforma de 12 agentes IA + meta-agente de Genomma Lab. Stack: Python (FastAPI) backend + Next.js frontend. Ver `docs/guias/genommaai-ecosystem.md` para arquitectura, patrones de middleware (registry singleton vs FastAPI standalone vs cliente importable), convenciones de agente y mapeo presunto scraper→agente.

---

## Project Structure

```
/workspace
├── bd_scrapers/                         → módulos de scraping JS (BrightData Scraper Studio)
├── gli_scrapers/                      → paquetes Python que envuelven cada scraper y lo exponen al repo de agentes
│   └── <name>/                       → cliente Python stateless (httpx + pydantic)
├── tests/                            → tests de cada módulo
├── docs/
│   ├── guias/                        → guías narrativas del proyecto
│   ├── fase3/                        → handoffs de integración scraper → agente
│   └── specs/
│       ├── memory.md                 → memoria persistente del proyecto
│       ├── source-scrapers.xlsx      → catálogo oficial de scrapers (hoja `scrapers`)
│       └── bd_scrapers/
│           ├── <name>.md             → spec por scraper (databrightdata + genomma lab)
│           └── ...
├── .claude/agents/                   → subagentes de Claude Code
├── .agents/skills/                   → skills (fuente de verdad, cross-tool)
├── .claude/skills/                   → symlink a .agents/skills/
├── requirements.txt
└── AGENTS.md                         → política compartida para todos los agentes
```

---

## Memoria persistente del proyecto

`/workspace/docs/specs/memory.md` es la memoria canónica del proyecto. **Leerla siempre** antes de crear o modificar un spec. Define:

- Estructura fija de `<name>.md` (header + `databrightdata` + `genomma lab`).
- Regla dura: `databrightdata` (§1+§2+§3 prosa) **≤ 1000 caracteres**.
- Tres etapas del trabajo de un scraper: **análisis**, **implementación JS** (BrightData Scraper Studio) y **middleware Python** (paquete stateless en `gli_scrapers/<name>/`).
- Cómo obtener material: prior work → MCP brightdata → fallback curl.

> **No usar la memoria per-container** (`~/.claude/projects/-workspace/memory/`) para conocimiento del proyecto: no sobrevive al reset del contenedor. Toda memoria duradera vive en el repo.

---

## Rol de Claude: Orquestador

Claude **no implementa**. Solo orquesta: decide qué agente actúa y cuándo.

1. **Verificar** que exista spec antes de delegar cualquier cambio no trivial.
2. **Actualizar el spec** (vía `analyst`) si la tarea requiere crearlo o modificarlo.
3. **Delegar** al agente especializado una vez que el spec cubre el caso.
4. **Integrar** los resultados y comunicarlos al usuario.

### Cuándo usar el agente `analyst`

Solo cuando hay que **crear o actualizar un spec**:
- Nuevo scraper sin spec
- Cambio de comportamiento que no está cubierto por el spec actual
- Solicitud de documentación formal

### Cuándo ir directo al agente especializado

Cuando el spec **ya existe y cubre el caso**: Claude lee el spec, verifica cobertura, delega directamente al `analista-de-scrapers`.

### Cuándo actúa Claude directamente (sin delegar)

Solo para tareas que **no son implementación**:
- `CLAUDE.md`, `AGENTS.md`, archivos de configuración raíz
- Typos, texto, traducciones
- Variables de entorno, `.env.example`
- Comandos de administración one-liners

### Regla: no implementar sin spec

Ningún cambio no trivial en `bd_scrapers/` debe implementarse sin que el spec del módulo lo respalde.
Si el spec no menciona el caso → el spec está incompleto → actualizar primero.

---

## Available Agents (`.claude/agents/`)

| Agent | Dominio — delegar SIEMPRE que la tarea caiga aquí |
|-------|---------------------------------------------------|
| `analyst` | Crear o actualizar specs. Punto de entrada para features nuevas, cambios de comportamiento, o cuando hay que documentar antes de implementar. |
| `analista-de-scrapers` | Todo cambio en `bd_scrapers/<name>/sc_browser/` y `sc_code/`: interaction code, parser code, selectores, paginación, entrega de datos. JS runtime de BrightData Scraper Studio, no Python. |
| `middleware-python` | Todo cambio en `gli_scrapers/<name>/`: cliente Python stateless (httpx + pydantic v2) que envuelve un scraper de BrightData y expone `trigger` / `get_result` / `TOOL_SCHEMA`. Requiere handoff en `docs/fase3/<name>-handoff.md`. |
| `snow-expert-wrench` | Todo lo relacionado con Snowflake: DDL, SPs, Dynamic Tables, Cortex AI, roles, warehouse sizing, nomenclatura GLI. Lee archivos de referencia desde `~/.claude/agents/snow-expert-wrench/`. |

---

## Available Skills (`.agents/skills/`)

| Skill | Use for |
|-------|---------|
| `scraper-spec-analysis` | **Etapa 1**: producir `docs/specs/bd_scrapers/<name>.md` (databrightdata ≤1000 chars + genomma lab) |
| `scraper-implementation` | **Etapa 2**: iterar `v1 → v2 → vN` del scraper. Cubre DSL completa de BrightData Scraper Studio, Browser vs Code worker, best practices, patrones |
| `find-skills` | Descubrir e instalar skills desde skills.sh con `npx skills` |
| `module-specs` | (legacy — usar `scraper-spec-analysis`) |
| `edge-cases` | Analizar features para identificar casos borde, modos de fallo y escenarios de error |
