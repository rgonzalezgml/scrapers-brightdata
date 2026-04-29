# Inventario de Objetos Snowflake — <PROYECTO> (<PIPELINE>)

**Proyecto**: <nombre-del-proyecto>
**Version**: 1.0
**Fecha**: <YYYY-MM-DD>
**Owner tecnico**: Angel Tellez — angel.tellez@genommalab.com

---

## Resumen ejecutivo

| Tipo de Objeto | DEV | PRD | Total |
|---|---|---|---|
| Tablas LND | 0 | 0 | 0 |
| Tablas STG | 0 | 0 | 0 |
| Tablas CNS | 0 | 0 | 0 |
| Stored Procedures (activos) | 0 | 0 | 0 |
| Tasks | 0 | 0 | 0 |
| **TOTAL ACTIVOS** | **0** | **0** | **0** |

> **Nota**: Agregar aquí cualquier consideración sobre replicación DEV/PRD o scripts base.

---

## Reglas de ubicacion de objetos

| Tipo de Objeto | Esquema DEV | Esquema PRD |
|---|---|---|
| Tablas Landing (raw) | `DEV_LND.<SCHEMA>` | `PRD_LND.<SCHEMA>` |
| Tablas Staging | `DEV_STG.<SCHEMA>` | `PRD_STG.<SCHEMA>` |
| Tablas Consumo | `DEV_CNS_MX.<SCHEMA>` | `PRD_CNS_MX.<SCHEMA>` |
| Stored Procedures | `DEV_STG.<SCHEMA>` | `PRD_STG.<SCHEMA>` |
| Tasks | `DEV_STG.<SCHEMA>` | `PRD_STG.<SCHEMA>` |

---

## Inventario de objetos por flujo

| # | Tabla | Cat | LND | SP Fuente→LND | STG | SP LND→STG | CNS | SP STG→CNS |
|---|-------|-----|:---:|---|:---:|---|:---:|---|
| 1 | `<TABLA_1>` | Hecho | ✅ | `<SP_INGESTA>` | ✅ | `<SP_LND_STG>` | ✅ | `<SP_STG_CNS>` |
| — | `<TABLA_CONTROL>` | Control | — | — | ✅ | — | — | — |

> **Leyenda**: ✅ = objeto existe · — = no aplica para esa capa

---

## Infraestructura

| Objeto | Nombre completo | Ambiente | Proposito |
|---|---|---|---|
| Network Rule | `<DB>.SECRETS.<NETWORK_RULE>` | DEV | |
| Secret | `<DB>.SECRETS.<SECRET>` | DEV | |
| External Access Integration | `<EAI_NAME>` | DEV | |
| Network Rule | `<DB>.SECRETS.<NETWORK_RULE>` | PRD | |
| Secret | `<DB>.SECRETS.<SECRET>` | PRD | |
| External Access Integration | `<EAI_NAME>` | PRD | |

*(Eliminar sección si el pipeline no requiere infraestructura de red externa.)*

---

## Tasks de programacion automatica

| Task | Ambiente | Schedule (UTC) | Hora CST |
|---|---|---|---|
| `DEV_STG.<SCHEMA>.<TASK_DEV>` | DEV | | |
| `PRD_STG.<SCHEMA>.<TASK_PRD>` | PRD | | |

Las Tasks se crean **suspendidas**. Activar solo cuando el pipeline este validado en DEV:

```sql
ALTER TASK DEV_STG.<SCHEMA>.<TASK_DEV> RESUME;
-- PRD solo cuando DEV este estable:
ALTER TASK PRD_STG.<SCHEMA>.<TASK_PRD> RESUME;
```

*(Eliminar sección si el pipeline no usa Tasks.)*

---

## Orden de ejecucion de DDLs

```
1. ddl/<pipeline>/01_objetos.sql          — Tablas LND, STG, CNS
2. ddl/<pipeline>/02_sp_lnd_stg.sql       — SPs transformacion LND→STG
3. ddl/<pipeline>/03_sp_stg_cns.sql       — SPs transformacion STG→CNS
4. ddl/<pipeline>/04_infraestructura.sql  — Network Rules, Secrets, EAIs (si aplica)
5. ddl/<pipeline>/05_rbac.sql             — Roles y grants
```

---

## Roles y permisos

| Rol | Acceso |
|---|---|
| `DEV_APP_SERVICE` | Objetos DEV (SPs, Tasks, Secrets DEV) |
| `PRD_APP_SERVICE` | Objetos PRD (SPs, Tasks, Secrets PRD) |
| `SYSADMIN` | CREATE / ALTER / DROP de todos los objetos |
| `ACCOUNTADMIN` | Requerido para infraestructura de red (Network Rules, EAIs) |

---

## Changelog

| Fecha | Version | Cambio | DDL ejecutado | Ejecutado por |
|---|---|---|---|---|
| <YYYY-MM-DD> | 1.0 | Creacion inicial | `01_objetos.sql` | ATELLEZ |
