# Cambios DDL pendientes de aplicar en PROD

> Aplicar en `PRD_STG.GNM` una vez validados en DEV.
> Marcar cada ítem con ✅ fecha cuando se aplique.

---

## SRC_COSME_RANKING_HIST

| Columna | Cambio | Motivo | DEV | PROD |
|---------|--------|--------|-----|------|
| `NU_PUNTOS` | `NUMBER(5,2)` → `NUMBER(38,2)` | Overflow real: valor 1065.8 | ✅ 2026-05-01 | ✅ 2026-05-01 |
| `NU_RANK` | `NUMBER(3,0)` → `NUMBER(10,0)` | Límite arbitrario de 999 | ✅ 2026-05-01 | ✅ 2026-05-01 |
| `NU_RANK_CATEGORIA` | `NUMBER(5,0)` → `NUMBER(10,0)` | Límite arbitrario | ✅ 2026-05-01 | ✅ 2026-05-01 |
| `NU_TOTAL_RANKING` | DROP COLUMN | Comentada en DDL, no se usa | ✅ 2026-05-01 | ✅ 2026-05-01 (ya no existía) |
| `ID_MARCA` | DROP COLUMN | Comentada en DDL, no se usa | ✅ 2026-05-01 | ✅ 2026-05-01 (ya no existía) |

## SRC_OLIVEYOUNG_RANK_HIST

| Columna | Cambio | Motivo | DEV | PROD |
|---------|--------|--------|-----|------|
| `DT_CARGA` | DROP COLUMN | Reemplazada por CREATED_AT | ✅ 2026-05-01 | ✅ 2026-05-01 |
| `ID_JOB` | DROP COLUMN | No se usa en la carga actual | ✅ 2026-05-01 | ✅ 2026-05-01 |
| `NU_RATING` | Mantener como `FLOAT` | Snowflake no permite FLOAT→NUMBER sin recrear; decisión del usuario | — | ✅ 2026-05-01 (se deja FLOAT) |

---

> Todos los cambios pendientes han sido aplicados. Próximos cambios se agregarán aquí.
