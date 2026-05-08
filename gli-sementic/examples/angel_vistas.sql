-- PRD_CNS_SHD.DATA_GNM.VW_COSME_RANKING_HIST source

create or replace view PRD_CNS_SHD.DATA_GNM.VW_COSME_RANKING_HIST(
	RANKING COMMENT 'Posicion en el ranking semanal de @cosme (1-100)',
	RANK_CAMBIO COMMENT 'Indicador de movimiento en el ranking (UP, DOWN, HOT, NEW, STAY)',
	ID_PRODUCTO COMMENT 'Identificador unico del producto en @cosme',
	NOMBRE_PRODUCTO COMMENT 'Nombre del producto en japones',
	URL_IMG_PRINCIPAL COMMENT 'URL de la imagen principal del producto',
	MARCA COMMENT 'Nombre de la marca en japones',
	URL_MARCA COMMENT 'URL del perfil de la marca en @cosme',
	NOMBRE_CATEGORIA COMMENT 'Nombre de la categoria del producto en japones',
	URL_CATEGORIA COMMENT 'URL de la categoria en @cosme',
	PRECIO_YEN COMMENT 'Precio numerico del producto en yenes japoneses',
	TALLA COMMENT 'Tamano o presentacion del producto (ej. ml, g)',
	FLAG_PRECIO_ABIERTO COMMENT 'Indicador de precio abierto (sin precio fijo de venta)',
	FLAG_INCLUYE_IVA COMMENT 'Indicador si el precio incluye impuesto al consumo (IVA japones)',
	RATING COMMENT 'Calificacion promedio del producto en @cosme (escala 0-7)',
	RESENIAS COMMENT 'Numero total de resenas del producto',
	FECHA_LANZAMIENTO COMMENT 'Fecha de lanzamiento del producto en texto',
	FLAG_BEST_COSME COMMENT 'Indicador de premio Best Cosme Award',
	ES_PRODUCTO_NUEVO COMMENT 'Indicador de producto nuevo en el ranking',
	DESCRIPCION COMMENT 'Descripcion del producto en japones',
	INGREDIENTES COMMENT 'Lista de ingredientes del producto',
	DS_IMAGENES COMMENT 'Array JSON con URLs de imagenes adicionales del producto',
	URL_TIENDA COMMENT 'URL de la pagina del producto en @cosme',
	DT_PERIODO_INICIO COMMENT 'Fecha de inicio del periodo semanal del ranking',
	DT_PERIODO_FIN COMMENT 'Fecha de fin del periodo semanal del ranking',
	FUENTE COMMENT 'Identificador de la fuente de datos (cosme_ranking_products)',
	FECHA_CONSULTA COMMENT 'Fecha en que se realizo la consulta/extraccion del dato'
) COMMENT='Vista de ranking semanal de productos de belleza @cosme (plataforma japonesa). Top 100 por periodo semanal con precios en yenes, ratings, categorias. Fuente: PRD_STG.GNM.SRC_COSME_RANKING_HIST'
 as
SELECT
    NU_RANK                             AS RANKING,
    UPPER(TX_RANK_CAMBIO)               AS RANK_CAMBIO,
    UPPER(ID_PRODUCTO)                  AS ID_PRODUCTO,
    UPPER(NM_PRODUCTO)                  AS NOMBRE_PRODUCTO,
    URL_IMG_PRINCIPAL,
    UPPER(NM_MARCA)                     AS MARCA,
    URL_MARCA,
    UPPER(NM_CATEGORIA)                 AS NOMBRE_CATEGORIA,
    URL_CATEGORIA,
    NU_PRECIO_YEN                       AS PRECIO_YEN,
    UPPER(TX_TALLA)                     AS TALLA,
    FL_PRECIO_ABIERTO                   AS FLAG_PRECIO_ABIERTO,
    FL_INCLUYE_IVA                      AS FLAG_INCLUYE_IVA,
    NU_RATING                           AS RATING,
    NU_RESENAS                          AS RESENIAS,
    UPPER(TX_FECHA_LANZAMIENTO)         AS FECHA_LANZAMIENTO,
    FL_BEST_COSME                       AS FLAG_BEST_COSME,
    FL_NUEVO                            AS ES_PRODUCTO_NUEVO,
    UPPER(TX_DESCRIPCION)               AS DESCRIPCION,
    UPPER(TX_INGREDIENTES)              AS INGREDIENTES,
    DS_IMAGENES,
    URL_TIENDA,
    DT_PERIODO_INICIO,
    DT_PERIODO_FIN,
    FT_FUENTE                           AS FUENTE,
    CREATED_AT::DATE                    AS FECHA_CONSULTA
FROM PRD_STG.GNM.SRC_COSME_RANKING_HIST;



-- PRD_CNS_SHD.DATA_GNM.VW_COSMETIC_DESIGN_ARTICULOS source

create or replace view PRD_CNS_SHD.DATA_GNM.VW_COSMETIC_DESIGN_ARTICULOS(
	TITULO COMMENT 'Titulo del articulo tal como aparece en la publicacion',
	URL_ARTICULO COMMENT 'URL canonica del articulo en cosmeticdesign.com',
	FECHA_PUBLICACION COMMENT 'Fecha de publicacion del articulo',
	RESUMEN COMMENT 'Resumen o bajada del articulo',
	CONTENIDO COMMENT 'Contenido completo del articulo (vacio si requiere suscripcion)',
	FLAG_PAYWALL COMMENT 'Indica si el articulo requiere suscripcion de pago para acceder al contenido completo',
	URL_IMAGEN COMMENT 'URL de la imagen principal del articulo',
	PIE_IMAGEN COMMENT 'Pie de foto o leyenda de la imagen principal',
	TEMAS COMMENT 'Temas y etiquetas editoriales del articulo como array JSON',
	FUENTE COMMENT 'Identificador de la fuente de datos (cosmetics_design)',
	FECHA_CONSULTA COMMENT 'Fecha en que se realizo la extraccion del articulo'
) COMMENT='Vista de articulos publicados en Cosmetic Design / NutraIngredients. Contiene noticias y analisis de la industria de belleza, cuidado personal y nutricion. Fuente: PRD_STG.GNM.SRC_COSMETICDESIGN_ART_HIST'
 as
SELECT
    UPPER(TX_TITULO)                    AS TITULO,
    URL_ARTICULO,
    DT_PUBLICACION::DATE                AS FECHA_PUBLICACION,
    UPPER(TX_RESUMEN)                   AS RESUMEN,
    UPPER(TX_CONTENIDO)                 AS CONTENIDO,
    FL_PAYWALL                          AS FLAG_PAYWALL,
    URL_IMAGEN,
    UPPER(TX_PIE_IMAGEN)                AS PIE_IMAGEN,
    DS_TEMAS                            AS TEMAS,
    UPPER(FT_FUENTE)                    AS FUENTE,
    CREATED_AT::DATE                    AS FECHA_CONSULTA
FROM PRD_STG.GNM.SRC_COSMETICDESIGN_ART_HIST;