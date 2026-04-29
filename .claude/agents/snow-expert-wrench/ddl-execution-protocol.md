# DDL Execution Protocol (Obligatorio)

**NUNCA ejecutar DDL silenciosamente.** Antes de cualquier CREATE, ALTER o DROP en Snowflake, seguir este protocolo sin excepción.

> **ALERTA DROP/DELETE/TRUNCATE**: Operaciones destructivas requieren una confirmación
> adicional e independiente del plan general, incluso si el plan ya fue aprobado.
> Ver sección "Restricciones absolutas".

---

## Paso 1 — Plan de ejecución

Construir y presentar al usuario:

```
PLAN DE EJECUCION
=================
Ambiente   : DEV  (PRD requiere confirmacion adicional)
Usuario    : <SNOWFLAKE_USER desde .env>
Rol        : SYSADMIN
Warehouse  : <SNOWFLAKE_WAREHOUSE desde .env>

DROP (n objetos):
  1. DEV_STG.GNM_MEX.SP_WMS_CARGA_XXX_LND_STG(VARCHAR)  -- eliminar overload anterior

CREATE / REPLACE (n objetos):
  1. DEV_STG.GNM_MEX.SP_WMS_CARGA_XXX_LND_STG(VARCHAR, VARCHAR)  -- nueva firma con P_MODO_CARGA

ALTER (n objetos):
  1. DEV_LND._SRV_MEX.WMS_YYY  ADD COLUMN _CHANGE_TYPE VARCHAR(30)

Impacto estimado : <describir blast radius>
Reversible?      : Si / No  (Time Travel disponible X dias)
```

---

## Paso 2 — Esperar aprobacion explícita

Presentar el plan y preguntar: **"Procedo con la ejecucion en DEV? (si/no)"**

- NO proceder hasta recibir respuesta afirmativa.
- Si el usuario pide ejecutar en PRD → segunda confirmacion obligatoria para PRD.
- Si el usuario pide ejecutar en ambos ambientes → confirmar DEV primero, luego PRD.

---

## Paso 3 — Ejecutar y reportar

Ejecutar sentencia a sentencia (NO `execute_string()`). Reportar resultado por objeto:

```
RESULTADO DE EJECUCION
======================
[OK]  DROP   DEV_STG.GNM_MEX.SP_WMS_CARGA_XXX_LND_STG(VARCHAR)
[OK]  CREATE DEV_STG.GNM_MEX.SP_WMS_CARGA_XXX_LND_STG(VARCHAR, VARCHAR)
[ERR] ALTER  DEV_LND._SRV_MEX.WMS_YYY — Column already exists (non-fatal, ignorado)

Resumen: 2 OK, 0 ERR  |  Duracion: 3.2s
```

---

## Paso 4 — Actualizar inventario

Tras ejecucion exitosa, actualizar `.claude/agents/snow-expert-wrench/snowflake-object-inventory.md` del proyecto activo:
- Mover objetos nuevos a la seccion **Activos**.
- Mover objetos eliminados/deprecados a la seccion **Deprecados / A Eliminar**.
- Registrar fecha, rol y script DDL en el changelog.

---

## Restricciones absolutas

- NUNCA crear usuarios (`CREATE USER`)
- NUNCA crear roles (`CREATE ROLE`)
- NUNCA modificar resource monitors sin aprobacion DBA
- NUNCA hacer `--force` o saltarse confirmaciones
- PRD siempre requiere confirmacion independiente de DEV
- **DROP / TRUNCATE / DELETE con usuario ATELLEZ**: mostrar al usuario el objeto exacto,
  la base de datos, y advertir que la operacion es irreversible (salvo Time Travel).
  Esperar confirmacion explícita **separada** antes de conectarse y ejecutar.
  Formato obligatorio:

  ```
  ⚠️  OPERACION DESTRUCTIVA — CONFIRMACION REQUERIDA
  ===================================================
  Operacion  : DROP TABLE
  Objeto     : DEV_STG.GNM_MEX.TABLA_XYZ
  Usuario    : ATELLEZ (SYSADMIN)
  Reversible : Si — Time Travel disponible 1 dia
               No — si ya fue purgado o es PRD sin TT activo

  Escribe "CONFIRMO DROP" para proceder, o "cancelar".
  ```
