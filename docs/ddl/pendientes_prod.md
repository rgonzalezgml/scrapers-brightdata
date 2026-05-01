# Cambios DDL pendientes de aplicar en PROD

> Aplicar en `PRD_STG.GNM` una vez validados en DEV.
> Marcar cada ítem con ✅ fecha cuando se aplique.

---

## SRC_COSME_RANKING_HIST

| Columna | Cambio | Motivo | DEV | PROD |
|---------|--------|--------|-----|------|
| `NU_PUNTOS` | `NUMBER(5,2)` → `NUMBER(38,2)` | Overflow real: valor 1065.8 | ✅ 2026-05-01 | ⏳ pendiente |
| `NU_RANK` | `NUMBER(3,0)` → `NUMBER(10,0)` | Límite arbitrario de 999 | ✅ 2026-05-01 | ⏳ pendiente |
| `NU_RANK_CATEGORIA` | `NUMBER(5,0)` → `NUMBER(10,0)` | Límite arbitrario | ✅ 2026-05-01 | ⏳ pendiente |
| `NU_TOTAL_RANKING` | DROP COLUMN | Comentada en DDL, no se usa | ✅ 2026-05-01 | ⏳ pendiente |
| `ID_MARCA` | DROP COLUMN | Comentada en DDL, no se usa | ✅ 2026-05-01 | ⏳ pendiente |

SQL para aplicar en PROD:

```sql
ALTER TABLE PRD_STG.GNM.SRC_COSME_RANKING_HIST
  MODIFY COLUMN NU_PUNTOS NUMBER(38,2);

ALTER TABLE PRD_STG.GNM.SRC_COSME_RANKING_HIST
  MODIFY COLUMN NU_RANK NUMBER(10,0);

ALTER TABLE PRD_STG.GNM.SRC_COSME_RANKING_HIST
  MODIFY COLUMN NU_RANK_CATEGORIA NUMBER(10,0);

ALTER TABLE PRD_STG.GNM.SRC_COSME_RANKING_HIST
  DROP COLUMN NU_TOTAL_RANKING;

ALTER TABLE PRD_STG.GNM.SRC_COSME_RANKING_HIST
  DROP COLUMN ID_MARCA;
```
