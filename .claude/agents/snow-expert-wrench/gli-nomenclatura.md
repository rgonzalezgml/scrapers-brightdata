# Nomenclatura GLI — Manual Oficial v1.1.0 (Abr 2025)
# Autor: Angel Téllez — Dirección de Ciencia de Datos

## REGLA DE ORO
Todo en MAYÚSCULAS. Sin acentos, sin Ñ, sin caracteres especiales. Separar con guión bajo (_).
Este manual es la fuente de verdad para nombrar objetos en Snowflake de Genomma Lab Internacional.

---

## 1. AMBIENTES

| Prefijo | Descripción |
|---------|-------------|
| `DEV_`  | Ambiente de Desarrollo |
| `QA_`   | Ambiente de Validación |
| `PRD_`  | Ambiente Productivo |

---

## 2. FUENTES DE DATOS (sufijos en capa LND)

| Sufijo         | Descripción |
|----------------|-------------|
| `_SQL`         | SQL Server u otras bases relacionales |
| `_SAP` / `_ERP` | Sistema ERP (SAP u otro) |
| `_FLE`         | Archivos (CSV, Excel, JSON, etc.) |
| `_SRV`         | Servicios web, APIs o aplicaciones |
| `_CT`          | Catálogos o datos maestros |
| `_CF`          | Configuración de procesos o tareas ETL |

---

## 3. CAPAS DE ARQUITECTURA (Medallion)

| Capa      | Descripción |
|-----------|-------------|
| `LND`     | Landing — capa de aterrizaje, sin transformación |
| `STG`     | Staging — preparación, transformación y estandarización |
| `CNS`     | Consumo — capa final para análisis y reportes |
| `TRK`     | Tracking — raw data histórica (máx. 2 años) |
| `SANDBOX` | Estructuras experimentales para modelos ML/IA |

---

## 4. BASES DE DATOS — `{AMBIENTE}_{CAPA}_{PAIS}` (máx. 30 chars)

```
DEV_LND           -- Landing dev (única para todos los procesos, segmentación en schema)
DEV_STG           -- Staging dev (única para todos los procesos, segmentación en schema)
DEV_CNS_MX        -- Consumo México en desarrollo
PRD_CNS_ARG       -- Consumo Argentina en producción
PRD_CNS_APPS      -- Aplicaciones Streamlit en producción
```

---

## 5. SCHEMAS — `{DOMINIO}_{TIPO}_{PAIS}` (máx. 30 chars)

```
VENTAS            -- Dominio de ventas
FINANZAS          -- Dominio financiero
LOGISTICA         -- Logística y distribución
GNM_CT            -- Datos maestros y catálogos generales
GNM_CF            -- Configuración de procesos ETL|ELT
GNM_CT_CHI        -- Catálogos exclusivos de Chile
```

---

## 6. TABLAS — `{PREFIJO}_{NOMBRE}_{TIPO}` (máx. 50 chars)

**Prefijos por dominio:**
| Prefijo | Dominio |
|---------|---------|
| `VTA`   | Ventas |
| `FIN`   | Finanzas |
| `LOG`   | Logística |
| `RRHH`  | Recursos Humanos |
| `PROD`  | Productos |
| `INV`   | Inventarios |
| `CTE`   | Clientes |
| `PROV`  | Proveedores |
| `MKT`   | Marketing |
| `SRC`   | Fuentes externas / scrapers (datos crudos de origen) |

**Sufijos de tipo:**
```
_CT    -- Catálogos / datos maestros
_CF    -- Configuración de procesos
_HIST  -- Datos históricos
_TMP   -- Tablas temporales
_BKP   -- Respaldos temporales
```

```
VTA_PEDIDO                -- Tabla de pedidos
VTA_PEDIDO_DETALLE        -- Detalle de pedidos
INV_MOVIMIENTO_HIST       -- Histórico de movimientos de inventario
FIN_CUENTA_CONTABLE_CT    -- Catálogo de cuentas contables
```

---

## 7. VISTAS — `VW_{PREFIJO}_{NOMBRE}` (máx. 60 chars)

```
VW_VTA_PEDIDOS            -- Pedidos consolidados
VW_BO_FACTURACION         -- Facturación para reporte BackOrder
VW_CTE_VENTAS_ANUALES     -- Ventas anuales por cliente
VW_FIN_BALANCE_MENSUAL    -- Balance financiero mensual
VW_INV_EN_TIENDA          -- Existencias en tienda
```

---

## 8. STORED PROCEDURES — `SP_{ACCION}_{OBJETO}_{COMPLEMENTO}` (máx. 60 chars)

**Verbos de acción:**
| Verbo       | Propósito |
|-------------|-----------|
| `LOAD`      | Carga inicial o completa |
| `INSERT`    | Inserción de nuevos registros |
| `UPDATE`    | Actualización de registros existentes |
| `DELETE`    | Eliminación de registros |
| `MERGE`     | Sincronización insert/update |
| `PROCESS`   | Procesamiento complejo |
| `CALCULATE` | Cálculos y agregaciones |
| `VALIDATE`  | Validación de datos |
| `CLEAN`     | Limpieza de datos |
| `ARCHIVE`   | Archivado de registros |

```
SP_LOAD_VENTAS_DIARIAS    -- Carga diaria de ventas
SP_MERGE_CLIENTES_SAP     -- Sincronización clientes desde SAP
SP_CALCULATE_KPI_MENSUAL  -- Cálculo de KPIs mensuales
SP_PROCESS_FACTURACION    -- Procesamiento de facturación
SP_ARCHIVE_LOG_ANTIGUOS   -- Archivado de logs
```

---

## 9. FUNCIONES — `FN_{ACCION}_{OBJETO}_{TIPO_RETORNO}` (máx. 60 chars)

- Verbos: `GET`, `CALCULATE`, `CONVERT`, `FORMAT`, `VALIDATE`
- `UDF` = escalar (un valor) | `UDTF` = tabular (conjunto de filas)

```
FN_GET_DESCUENTO_CLIENTE  -- Descuento aplicable a un cliente
FN_CALCULATE_IMPUESTO     -- Calcula impuesto de una transacción
FN_CONVERT_MONEDA         -- Convierte montos entre divisas
FN_FORMAT_TELEFONO        -- Formatea números telefónicos
FN_VALIDATE_RFC           -- Valida formato RFC mexicano
FN_GET_DIAS_HABILES       -- Días hábiles entre fechas
```

---

## 10. COLUMNAS — Prefijos por tipo de dato

| Prefijo | Uso |
|---------|-----|
| `ID`    | Identificadores únicos / llaves primarias |
| `FK`    | Llaves foráneas |
| `FLG`   | Banderas booleanas (`BOOLEAN`) |
| `MTO`   | Montos monetarios (`NUMBER(18,4)`) |
| `PCT`   | Porcentajes |
| `CNT`   | Contadores / cantidades enteras |
| `COD`   | Códigos alfanuméricos |
| `DES`   | Descripciones textuales largas |

**Campos de auditoría estándar (obligatorios en TODAS las tablas):**
```sql
CREATED_AT    TIMESTAMP_NTZ(9) DEFAULT CURRENT_TIMESTAMP() COMMENT 'Fecha y hora de creacion del registro',
UPDATED_AT    TIMESTAMP_NTZ(9) DEFAULT CURRENT_TIMESTAMP() COMMENT 'Fecha y hora de ultima actualizacion del registro',
CREATED_USR   VARCHAR(100)     DEFAULT CURRENT_USER()      COMMENT 'Usuario que creo el registro',
UPDATED_USR   VARCHAR(100)     DEFAULT CURRENT_USER()      COMMENT 'Usuario que realizo la ultima actualizacion del registro'
```

**Metadata ETL (adicional en LND/STG):**
```sql
ETL_LOAD_TS   TIMESTAMP_NTZ   DEFAULT CURRENT_TIMESTAMP()  COMMENT 'Timestamp de carga ETL (UTC)',
ETL_UPDATE_TS TIMESTAMP_NTZ                                COMMENT 'Timestamp de última actualización ETL',
ETL_SOURCE    VARCHAR(200)                                 COMMENT 'Sistema o archivo fuente del registro',
IS_ACTIVE     BOOLEAN         DEFAULT TRUE                 COMMENT 'Flag de borrado lógico (FALSE = eliminado)'
```

---

## 11. CHECKLIST DE VALIDACIÓN

Antes de crear cualquier objeto en Snowflake:

- [ ] ¿Está en MAYÚSCULAS?
- [ ] ¿Sin acentos, Ñ ni caracteres especiales?
- [ ] ¿Tiene el prefijo de ambiente correcto? (`DEV_` / `PRD_`)
- [ ] ¿Tiene el prefijo de objeto correcto? (`SP_`, `VW_`, `FN_`)
- [ ] ¿Tiene el prefijo de dominio correcto? (`VTA`, `INV`, `FIN`, etc.)
- [ ] ¿Incluye campos de auditoría? (`CREATED_AT`, `CREATED_USR`, `UPDATED_AT`, `UPDATED_USR`)
- [ ] ¿Cada columna tiene `COMMENT` con descripción de negocio?
- [ ] ¿La tabla tiene `COMMENT ON TABLE` con propósito, fuente y frecuencia de actualización?
- [ ] ¿El nombre es descriptivo sin necesitar documentación adicional?
- [ ] ¿Respeta el límite de caracteres del tipo de objeto?
