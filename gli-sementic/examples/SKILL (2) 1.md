---
name: gnm-dt
description: Use when creating or modifying Dynamic Tables, Views, or semantic YAMLs in PRD_CNS_SHD.DATA_GNM. Provides standard column order, naming, comments, and rules.
---

# Estructura de Dynamic Tables y Vistas — PRD_CNS_SHD.DATA_GNM

> **Cómo usar esta skill**: La tabla maestra de cada dominio define simultáneamente el orden de columnas, el comentario canónico (`COMMENT ON COLUMN`) y las notas técnicas de implementación. No duplicar esta información en ningún otro lugar del código.

---

## Orden de bloques

```
KEYS → A) Tiempo → B) Clientes → C) Productos → D) Dominio específico → E) Métricas → F) Tipos de cambio
```

**KEYS aplicables**: `PAISID`, `SEMID` / `TMPID`, `CADID`, `SUCID`, `PROPSTID` — solo los que apliquen al dominio.

---

## Tabla maestra de campos

### KEYS (IDs)

| Campo | Comentario canónico | Notas técnicas |
|-------|---------------------|----------------|
| PAISID | Identificador numerico del pais | JOIN con `VW_DIM_PAIS` |
| PAIS | Nombre del pais | — |
| SEMID | Llave sustituta de la semana del calendario fiscal Genomma (formato YYYYSS) | JOIN con `VW_CATSEMANAS` |
| TMPID | Llave sustituta de tiempo (ANIO×10000 + MES×100 + 1) | JOIN con `TIPO_CAMBIO_X_PAIS` |
| CADID | Identificador numerico de la cadena o formato comercial (ej. Walmart, Farmacias del Ahorro) | JOIN con `VW_ESTRUCTURACLIENTESSEGPTVTOTAL` |
| SUCID | Identificador numerico de la sucursal o punto de venta fisico | JOIN con `VW_ESTRUCTURASUCURSALESTOTAL` |
| PROPSTID | Identificador numerico de la presentacion especifica del producto (SKU) | JOIN con `VW_CATALOGO_PRODUCTOS_INTERNACIONAL` |
| GRPID | Identificador numerico del grupo empresarial o cliente | JOIN con `VW_ESTRUCTURACLIENTESSEGPTVTOTAL` |

---

### A) Tiempo

> `FECHA_INICIO_SEMANA`, `FECHA_FIN_SEMANA` y `FECHA`: tipo `DATE` — usar `::DATE`, sin hora.

| # | Campo | Comentario canónico |
|---|-------|---------------------|
| 1 | ANIO | Anio fiscal del calendario Genomma. Puede diferir del anio calendario segun el inicio del ciclo fiscal de GLI |
| 2 | TRIMESTRE | Trimestre del calendario fiscal Genomma (1-4). Agrupa periodos de 13 semanas |
| 3 | MES | Mes del calendario fiscal Genomma (1-12). Puede no coincidir con el mes calendario |
| 4 | SEMANA | Numero de semana del calendario fiscal Genomma (1-52 o 53). Unidad minima de analisis |
| 5 | FECHA_INICIO_SEMANA | Fecha del lunes que inicia la semana Genomma. Punto de anclaje para rangos y comparativos |
| 6 | FECHA_FIN_SEMANA | Fecha del domingo que cierra la semana Genomma. Cierre del periodo para acumulados e inventarios |
| 7 | FECHA | Fecha exacta del registro a nivel dia |

---

### B) Clientes

> `TIPO_CLIENTE`: usar `VW_ESTRUCTURASUCURSALESTOTAL` si la clave es `SUCID`; usar `VW_ESTRUCTURACLIENTESSEGPTVTOTAL.GRPCLASIFICACION` si la clave es `CADID`. `UPPER()` a todos los textos salvo URLs.

| # | Campo | Comentario canónico |
|---|-------|---------------------|
| 1 | TIPO_CLIENTE | Clasificacion del cliente (Monitoreado / No Monitoreado). Determina disponibilidad de datos de sellout e inventario |
| 2 | CANAL | Tipo de canal de venta o formato de establecimiento (ej. Autoservicios, Cadenas de Farmacias, Canal Tradicional, E-commerce) |
| 3 | NOMBRE_CLIENTE | Nombre comercial del grupo empresarial al que pertenece la cadena (ej. Walmart de Mexico, FEMSA Comercio) |
| 4 | CODIGO_CLIENTE_ERP | Codigo alfanumerico del cliente en SAP. Permite conciliar sellout con facturacion y cuentas por cobrar |
| 5 | NOMBRE_FORMATO_TIENDA | Nombre del banner o formato comercial que agrupa sucursales (ej. Bodega Aurrera, Walmart Supercenter, Sam's Club) |
| 6 | NOMBRE_SUCURSAL | Nombre del punto de venta tal como lo registra el retailer en sus sistemas |
| 7 | CODIGO_SUCURSAL | Codigo interno del punto de venta en el sistema del retailer. Puede diferir del codigo ERP de Genomma |
| 8 | ESTADO | Estado de la Republica Mexicana donde se ubica la sucursal. Base para segmentacion geografica y regional |
| 9 | MUNICIPIO | Municipio o alcaldia de la sucursal. Permite granularidad sub-estatal para analisis de plaza y cobertura |
| 10 | CODIGO_POSTAL | Codigo postal de la sucursal. Facilita georreferenciacion y cruce con variables socioeconomicas externas |
| 11 | DIRECCION | Direccion completa de la sucursal (calle, numero, colonia, municipio). Uso en reportes operativos y rutas de promocion |
| 12 | FLAG_ES_CEDIS | Indicador booleano. `true` si el punto es un Centro de Distribucion (CEDIS) del cliente — el inventario en CEDIS no representa venta al consumidor final |

---

### C) Productos

> Agrupadores obligatorios al incluir `MARCA`: ver Regla 10. `AGRUPACION_PAUTA` requiere `COLLATE 'en_ci_as'` cuando la fuente tiene collation sensible. Equivalencias con vista legada: `MRCCATEGORIA`→`UNIDAD_NEGOCIO`, `MRCNOMBRE`→`MARCA`, `MRCLIDERMARCA`→`BRAND_LIDER`, `LINNOMBRE`→`LINEA`, `AGPPAUTANOMBRE`→`AGRUPACION_PAUTA`, `PRONOMBRE`→`PRODUCTO_BASE`, `PROPSTNOMBRE`→`NOMBRE_PRESENTACION`, `PROPSTCODBARRAS`→`CODIGO_BARRAS`, `PROPSTSHORTID`→`CODIGO_PRODUCTO_ERP`.

| # | Campo | Comentario canónico |
|---|-------|---------------------|
| 1 | UNIDAD_NEGOCIO | Unidad de negocio o categoria comercial de la marca (ej. OTC, Personal Care, Baby Care) |
| 2 | MARCA | Nombre comercial de la marca (ej. Tio Nacho, Cicatricure, Nikzon). Nivel principal de agrupacion para reportes |
| 3 | BRAND_LIDER | Nombre del Brand Leader responsable de la estrategia comercial y de marketing de la marca en GLI |
| 4 | LIDER_EMAIL | Correo corporativo del Brand Leader. Usado en alertas automaticas, reportes y flujos de aprobacion |
| 5 | LIDER_PHONE | Telefono corporativo del Brand Leader. Referencia para notificaciones operativas y escalamientos |
| 6 | BRAND_OWNER | Nombre del Brand Owner, responsable ejecutivo del P&L y estrategia global de la marca en GLI |
| 7 | OWNER_EMAIL | Correo corporativo del Brand Owner. Usado para reportes ejecutivos y alertas de negocio |
| 8 | LINEA | Linea de producto dentro de la marca. Agrupa SKUs con formulacion, uso o segmento objetivo comun (ej. Tio Nacho Anti-edad) |
| 9 | AGRUPACION_PAUTA | Clasificacion del producto segun la pauta de medios TV. Llave de cruce entre datos de audiencia IBOPE (GRPs) y ventas en punto de venta (sellout) |
| 10 | PRODUCTO_BASE | Nombre del producto base que agrupa distintas presentaciones bajo un mismo concepto (ej. Cicatricure Gel) |
| 11 | NOMBRE_PRESENTACION | Nombre completo del SKU incluyendo variante, contenido y unidad (ej. Cicatricure Gel 30g) |
| 12 | CODIGO_BARRAS | Codigo de barras EAN-13 o UPC-12 de la presentacion. Identificador universal para conciliacion con datos del retailer |
| 13 | CODIGO_PRODUCTO_ERP | Codigo del material en SAP. Llave de cruce para facturacion, inventarios y cadena de suministro |

---

### E) Métricas

#### Sellout

> `ZEROIFNULL()` en todos los campos numericos de esta sección.

| Campo | Comentario canónico |
|-------|---------------------|
| UNIDADES_SELLOUT | Unidades vendidas al consumidor final en el punto de venta durante la semana. Refleja la demanda real del mercado |
| MONTO_SELLOUT_NETO | Monto neto en moneda local de las unidades vendidas al consumidor final (precio factura Genomma, neto de descuentos) |
| MONTO_SELLOUT_BRUTO | Monto bruto en moneda local de las unidades vendidas, sin descontar bonificaciones ni reservas (precio de lista Genomma × unidades) |
| MONTO_VENTA_CLIENTE | Monto de venta al consumidor final al precio de retail (PVP). Refleja el valor de mercado generado en el punto de venta |
| PRECIO_VENTA_PUBLICO | Precio de venta al publico promedio del SKU en la semana. Calculado como `MONTO_VENTA_CLIENTE / UNIDADES_SELLOUT` |

#### Inventario

Los campos de inventario siempre vienen en trío `UNIDADES_X` / `MONTO_X_NETO` / `MONTO_X_BRUTO`. Todos al cierre de la semana. `ZEROIFNULL()` en todos los montos.

| Campo | Comentario canónico | Ubicacion / alcance |
|-------|---------------------|---------------------|
| UNIDADES_INVENTARIO_TIENDA | Unidades en anaquel o bodega de tienda al cierre de semana | Solo tienda — excluye CEDIS y transito |
| MONTO_INVENTARIO_TIENDA_NETO | Monto neto del inventario en tienda al cierre de semana (unidades × precio factura Genomma neto) | Solo tienda — excluye CEDIS y transito |
| MONTO_INVENTARIO_TIENDA_BRUTO | Monto bruto del inventario en tienda al cierre de semana (unidades × precio de lista Genomma, sin descuentos) | Solo tienda — excluye CEDIS y transito |
| UNIDADES_INVENTARIO_CEDIS | Unidades en el CEDIS del cliente al cierre de semana. Stock en transicion, aun no disponible en anaquel | Solo CEDIS |
| MONTO_INVENTARIO_CEDIS_NETO | Monto neto del inventario en CEDIS del cliente al cierre de semana | Solo CEDIS |
| MONTO_INVENTARIO_CEDIS_BRUTO | Monto bruto del inventario en CEDIS del cliente al cierre de semana | Solo CEDIS |
| UNIDADES_TRANSITO | Unidades en transito entre CEDIS y tiendas al cierre de semana. Stock en movimiento aun no recibido en destino | Solo transito |
| MONTO_TRANSITO_NETO | Monto neto de productos en transito al cierre de semana | Solo transito |
| MONTO_TRANSITO_BRUTO | Monto bruto de productos en transito al cierre de semana | Solo transito |
| UNIDADES_INVENTARIO_TOTAL | Inventario total consolidado al cierre de semana (CEDIS + Transito + Tienda) | Total cadena del cliente |
| MONTO_INVENTARIO_TOTAL_NETO | Monto neto total del inventario consolidado al cierre de semana (CEDIS + Transito + Tienda) | Total cadena del cliente |
| MONTO_INVENTARIO_TOTAL_BRUTO | Monto bruto total del inventario consolidado al cierre de semana (CEDIS + Transito + Tienda) | Total cadena del cliente |

#### Sellin (Facturacion)

> `ZEROIFNULL()` en todos los campos numericos de esta sección.

| Campo | Comentario canónico |
|-------|---------------------|
| UNIDADES_FACTURADAS | Unidades facturadas por Genomma al cliente en la semana (Facturacion Bruta + Refacturas + Rechazos). Flujo de producto Genomma → canal |
| MONTO_FACTURACION_BRUTA | Monto bruto en moneda local facturado al cliente (Facturacion Bruta + Refacturas + Rechazos), antes de reservas o descuentos |
| MONTO_FACTURACION_NETA | Monto neto en moneda local de la facturacion al cliente, despues de todas las reservas y descuentos (precio real de transferencia al canal) |

#### Forecast

> `ZEROIFNULL()` en todos los campos numericos de esta sección. Para DTs con datos futuros: usar `COALESCE(TC_mes, TC_mas_reciente)` en `MONTO_FORECAST_SELLOUT_NETO` para meses >= mes actual.

| Campo | Comentario canónico |
|-------|---------------------|
| UNIDADES_FORECAST | Unidades proyectadas de venta al consumidor final (forecast sellout). Base para planeacion de produccion, abasto y presupuesto comercial |
| MONTO_FORECAST_SELLOUT_BRUTO | Monto bruto del forecast en moneda local (unidades proyectadas × precio base de lista Genomma) |
| MONTO_FORECAST_SELLOUT_NETO | Monto neto del forecast en moneda local (monto bruto ajustado por Factor BN segun tipo de cliente y semana) |

#### Reservas

Todas las reservas son montos en moneda local. Convención: `ZEROIFNULL()` en todos.

| Campo | Comentario canónico | Naturaleza |
|-------|---------------------|------------|
| MONTO_RESERVAS_DEVOLUCION | Provision por devoluciones esperadas del canal hacia Genomma | Variable |
| MONTO_RESERVAS_VARIABLES | Total de reservas variables del periodo (condicionadas a volumen, cumplimiento o acuerdos comerciales) | **Total variable** |
| MONTO_RESERVA_CORPORATIVAS | Reserva por lineamientos corporativos de Genomma, independiente de negociaciones individuales | Variable |
| MONTO_RESERVA_JBP | Reserva del Joint Business Plan (JBP): acuerdo de colaboracion estrategica entre Genomma y el retailer | Variable |
| MONTO_RESERVA_MIX | Reserva por variacion en la mezcla de productos vendidos respecto al mix planificado | Variable |
| MONTO_RESERVA_TRADE | Reserva para actividades de trade marketing (exhibiciones, promociones en PDV, material POP) | Variable |
| MONTO_RESERVA_DIST_DIRECTA | Reserva para clientes con distribucion directa a tienda, fuera del flujo centralizado de CEDIS | Variable |
| MONTO_RESERVA_FFS | Fee for Service: compensacion al retailer por servicios logisticos o comerciales prestados a Genomma | Variable |
| MONTO_RESERVA_MAP | Minimum Advertised Price: provision para proteger el precio minimo de anuncio acordado con el canal | Variable |
| MONTO_RESERVA_PRONTO_PAGO | Descuento o bonificacion por liquidar facturas antes del vencimiento acordado | Variable |
| MONTO_RESERVAS_FIJAS | Total de reservas fijas del periodo, pactadas independientemente del volumen de ventas | **Total fija** |
| MONTO_RESERVA_FIJAS_COMPLEMENTO | Componente complementario de reservas fijas no clasificado en logistica ni financiero | Fija |
| MONTO_RESERVA_FIJAS_LOGISTICAS | Reservas fijas por costos logisticos del canal (manejo, almacenaje, cross-docking) | Fija |
| MONTO_RESERVA_FIJAS_FINANCIERAS | Reservas fijas de naturaleza financiera (costos de capital, financiamiento al canal, plazos extendidos) | Fija |

#### Medios TV

> `ZEROIFNULL()` en todos los campos numericos de esta sección. Fuente: IBOPE/Ingeenius.

| Campo | Comentario canónico |
|-------|---------------------|
| GRPS | GRP del spot: porcentaje de audiencia de hogares con TV alcanzado por el spot en la transmision. Formula: cobertura (%) × frecuencia media. No elimina duplicaciones |
| COSTO | Tarifa CPP (Costo Por Punto de rating) negociada para el network o canal en el trimestre, en moneda local. Base del calculo de inversion |
| INVERSION | Inversion publicitaria del spot en moneda local (GRPs × Costo). Valor monetario de la presion publicitaria del spot |
| TOTAL_GRPS | GRPs totales de la semana para la marca o agrupacion, sumando todos los canales y programas pautados. Indicador de presion publicitaria semanal agregada |
| TOTAL_INVERSION_ML | Inversion total en medios TV en moneda local en la semana. Comparable con sellout para calcular ROI publicitario |
| CPP_ML | Costo Por Punto de rating en moneda local (CPP = Inversion / GRPs). Indica cuanto cuesta impactar al 1% del universo de hogares con TV. Metrica de eficiencia entre canales o periodos |
| NUM_VERSIONES | Numero de versiones creativas distintas de spots pautados en la semana para la marca o agrupacion |
| NUM_CAMPANIAS | Numero de campanas publicitarias activas en la semana. Una campana puede contener multiples versiones y canales |

#### Digital

> `ZEROIFNULL()` en todos los campos numericos de esta sección.

| Campo | Comentario canónico |
|-------|---------------------|
| MTO_SPEND | Inversion publicitaria digital en moneda local (redes sociales, search, programatica, etc.) |
| CNT_IMPRESSIONS | Numero de impresiones del anuncio digital. Veces que fue mostrado al usuario, independientemente de interaccion |
| CNT_CLICKS | Numero de clics en el anuncio digital. Nivel de interaccion directa del usuario con el contenido publicitario |
| CNT_CONVERSIONS | Numero de conversiones atribuidas al anuncio en la semana (compras, registros u otras acciones objetivo de la campana) |

---

### F) Tipos de cambio

> Siempre en par `ML_USD` / `USD_MXN` por regimen. Fuente: `TIPO_CAMBIO_X_PAIS`.

| # | Campo | Régimen | Comentario canónico |
|---|-------|---------|---------------------|
| 1 | ML_USD | Actual | TC de moneda local a USD del mes de la transaccion. Resultados reales |
| 2 | USD_MXN | Actual | TC de USD a MXN del mes de la transaccion. Resultados reales |
| 3 | ML_USD_CTE | Corriente (Budget) | TC de moneda local a USD fijo del presupuesto anual. Comparar resultados vs plan sin efecto cambiario |
| 4 | USD_MXN_CTE | Corriente (Budget) | TC de USD a MXN fijo del presupuesto anual. Comparar resultados vs plan sin efecto cambiario |
| 5 | ML_USD_LFL | Like-for-like | TC de moneda local a USD del mismo periodo del anio anterior. Analisis de crecimiento comparable YoY |
| 6 | USD_MXN_LFL | Like-for-like | TC de USD a MXN del mismo periodo del anio anterior. Analisis de crecimiento comparable YoY |

---

## Reglas generales

1. **UPPER**: Aplicar `UPPER()` a todos los campos de texto sin excepción, SALVO URLs y campos que el usuario indique explicitamente. Los emails (`LIDER_EMAIL`, `OWNER_EMAIL`) también reciben `UPPER()`.
2. **NULLs en texto**: `COALESCE(campo, 'SIN CLASIFICACION')` o variante contextual (`'SIN MARCA'`, `'SIN LINEA'`, etc.).
3. **NULLs en montos**: `NVL(campo, 0)` o `ZEROIFNULL(campo)`.
4. **TC futuros**: Si la DT contiene forecast, usar `COALESCE(TC_mes, TC_mas_reciente)` para meses >= mes actual.
5. **Permisos**: Al crear cualquier DT o vista, agregar siempre:
   ```sql
   GRANT SELECT ON <objeto> TO ROLE CORTEX_ANALYST_ROLE;
   GRANT SELECT ON <objeto> TO ROLE ANALYST_MX_ROLE;
   ```
6. **Catalogo de productos**: Usar `PRD_CNS_SHD.DATA_GNM.VW_CATALOGO_PRODUCTOS_INTERNACIONAL`. **No usar** `VW_ESTRUCTURAPRODUCTOSTOTALPAISES`. Verificar nombres reales con `DESCRIBE VIEW` antes de usar. Mapeo de columnas en nota introductoria de C).
7. **Catalogo de pais**: `PRD_CNS_MX.CATALOGOS.VW_DIM_PAIS` con `CROSS JOIN ... WHERE PA.PAISID = 1`.
8. **Clustering**: Para tablas > 50M filas usar `CLUSTER BY LINEAR(ANIO, SEMANA, MARCA)` y forzar recluster post-creacion.
9. **Agrupadores obligatorios de marca**: Siempre que se incluya `MARCA`, incluir tambien `UNIDAD_NEGOCIO`, `BRAND_LIDER` y `BRAND_OWNER`. Si la fuente solo tiene `MARCA`, completar con:
   ```sql
   LEFT JOIN (
       SELECT DISTINCT UNIDAD_NEGOCIO, BRAND_LIDER, BRAND_OWNER, MARCA
       FROM PRD_CNS_SHD.DATA_GNM.VW_CATALOGO_PRODUCTOS_INTERNACIONAL
       WHERE PAISID = 1
   ) AS MRC ON MRC.MARCA = <alias_fuente>.MARCA
   ```

---

## Fuentes de catálogos

| Catalogo | Objeto | Clave de JOIN |
|----------|--------|---------------|
| Productos Internacional | `PRD_CNS_SHD.DATA_GNM.VW_CATALOGO_PRODUCTOS_INTERNACIONAL` | `PROPSTID`, `PAISID=1` si solo Mexico |
| Clientes Internacional | `PRD_CNS_MX.CATALOGOS.VW_ESTRUCTURACLIENTESSEGPTVTOTAL` | `GRP_ID`, `CAD_ID`, `PAISID=1` si solo Mexico |
| Sucursales | `PRD_CNS_MX.CATALOGOS.VW_ESTRUCTURASUCURSALESTOTAL` | `SUCID`, `SUC_ID`, `PAISID=1` si solo Mexico |
| Tiempo (semanas) | `PRD_CNS_MX.CATALOGOS.VW_CATSEMANAS` | `SEMID` |
| Pais | `PRD_CNS_MX.CATALOGOS.VW_DIM_PAIS` | `PAISID` |
| Tipo de cambio | `PRD_CNS_MX.DM.TIPO_CAMBIO_X_PAIS` | `TMPID = (ANIO*10000 + MES*100 + 1)`, `PAISID=1` si solo Mexico |
| Factor BN | `PRD_STG.GNM_CT.FACTORBN` | `SEMID`, `PAISID=1`, `TIPOCLIENTE=1` (0=No Monitoreado, 1=Monitoreado) |
| Precios | `PRD_CNS_MX.PRECIOS.GNMPRECIOSXCADENAHIST` | `CADID`, `PROPSTID`, `IDSEMANA` |
