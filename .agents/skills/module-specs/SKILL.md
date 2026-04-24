---
name: module-specs
description: >
  Protocolo canónico para leer, aplicar y mantener los specs de módulo del proyecto brightdata-scrapers.
  Usada por todos los agentes antes de implementar o documentar cambios en un scraper.
  Cubre: índice de specs, qué contiene cada spec, protocolo de lectura previa,
  protocolo de actualización, y relación spec→tests.
---

# SKILL: module-specs

Los specs en `docs/specs/` son la fuente de verdad de la lógica de negocio de cada scraper.
Antes de implementar cualquier cambio en un módulo, el agente **debe** leer su spec.
Si el cambio modifica comportamiento documentado, el spec se actualiza en el mismo commit.

---

## 1. Índice de specs disponibles

| Módulo | Archivo | Cubre |
|--------|---------|-------|
| _(se llena a medida que se crean scrapers)_ | | |

Ruta base: `/workspace/docs/specs/`

---

## 2. Qué contiene cada spec (y qué NO)

**Contiene:**

- Propósito del scraper y fuente de datos (URL base, tipo de sitio)
- Campos extraídos: nombre, tipo, origen en el DOM/JSON, transformaciones aplicadas
- Reglas de negocio: validaciones, filtros, deduplicación, condiciones de rechazo
- Modo de conexión BrightData: proxy HTTP o Scraping Browser, y por qué se eligió ese modo
- Pipeline de procesamiento paso a paso
- Frecuencia / trigger de ejecución esperado
- Formato y destino de entrega de datos (CSV, JSON, Snowflake, etc.)
- Decisiones de diseño con rationale
- Backlog: ítems pendientes y deuda técnica conocida

**NO contiene:**

- Código de implementación
- Schemas JSON de request/response detallados (esos van en docstrings o en la propia clase Pydantic)
- Credenciales ni valores de variables de entorno

---

## 3. Protocolo de uso antes de implementar

Ejecutar estos pasos en orden antes de escribir cualquier línea de código:

1. Identifica el módulo que vas a tocar (ver índice sección 1)
2. Lee el spec completo: `Read /workspace/docs/specs/{modulo}-spec.md`
3. Revisa la sección **Backlog** — puede haber deuda técnica que afecte tu implementación
4. Revisa los **Campos extraídos** — no agregues campos que no estén en el spec sin actualizar el spec primero
5. Revisa el **Modo de conexión** — usa el cliente BrightData que el spec especifica
6. Si el spec tiene algo inconsistente con el código real → prevalece el código; actualiza el spec antes de continuar

Si el módulo no tiene spec todavía → no implementes → notifica al orquestador para que el `analyst` lo cree primero.

---

## 4. Protocolo de actualización del spec

Cuando un cambio modifica comportamiento documentado en el spec, el spec se actualiza **en el mismo commit** que el código.

Reglas de actualización:

- Actualiza la sección relevante (campos, reglas, pipeline, modo de conexión) con el nuevo comportamiento
- Si resuelves un ítem del backlog, márcalo con `[RESUELTO vX.Y.Z — YYYY-MM-DD]` y deja el texto original visible
- No borres el historial de decisiones — agrega una nota `> Actualizado en vX.Y.Z: [razón]` debajo de la decisión previa
- Si agregas campos nuevos, agrégalos a la tabla de campos del spec

---

## 5. Relación spec → tests

Los casos de prueba se derivan directamente del spec.

| Qué documenta el spec | Test requerido |
|-----------------------|----------------|
| Campo extraído | Test que valida que el parser devuelve ese campo con el tipo correcto |
| Regla de validación | Test positivo (dato válido pasa) + test negativo (dato inválido es rechazado o filtrado) |
| Condición de rechazo | Test que verifica que el ítem es descartado cuando se cumple la condición |
| Transformación de dato | Test que verifica la transformación con input/output conocidos |
| Ítem del backlog | Registrar como edge case pendiente (no bloquea, pero es deuda explícita) |

---

## 6. Reglas generales

- **Spec antes de código:** nunca implementes lógica de un scraper sin leer su spec primero.
- **Spec como contrato:** si spec y código difieren, investiga antes de asumir cuál tiene razón.
- **Spec vivo:** se mantiene sincronizado con el código en cada commit que toca el módulo.
- **No duplicar modelos Pydantic:** los tipos y campos van en el spec (descripción) y en los modelos (implementación). No repitas schemas detallados en el spec.
- **No hardcodear credenciales en specs:** los specs nunca contienen valores reales de variables de entorno.
- **Specs son Markdown:** nunca en `.docx`. Los specs de módulo viven en `docs/specs/` como archivos `.md`.
