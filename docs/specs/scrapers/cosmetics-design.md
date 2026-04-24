# cosmetics-design — spec
https://www.nutraingredients.com/Health-conditions/Beauty-wellness/
Proveedor: William Reed
Categoría: I+D
Función: Noticias de la industria cosmética

## databrightdata

### 1.
Scraper cosmetics-design (I+D, noticias cosmética). Entidad: `article`. Tendencias: formulación, ingredientes, claims, regulación, lanzamientos. Fuente: nutraingredients.com `/Health-conditions/Beauty-wellness/` (sites `cosmeticsdesign.*` cerrados 2026-03). CMS Arc XP Fusion. NO productos/precios/reviews.

### 2.
```json
{"article":["article_id","url","slug","headline","display_date","publish_date","last_updated_date","website","supplier","subtype","author_names","primary_section_path","section_paths","region_tags","topic_tags","body_text","body_word_count","promo_image_url","paywalled","scraped_date"]}
```

### 3.
- `/Health-conditions/Beauty-wellness/` landing (scroll, 50/load)
- `/Article/{YYYY}/{MM}/{DD}/{slug}/` detail
- `/archives/{YYYY}/` (2000+)
- `/arc/outboundfeeds/sitemap/category/Health-conditions/Beauty-wellness/` delta XML
- Disallow `/pf/api/` (Crawl-delay 1)
- Ignorar `/Product-innovations/`, `/Events/` (cross-promo)

## genomma lab

### 1.
Scraper cosmetics-design para investigacion y desarrollo (I+D) cosmetico. Categoria: noticias de la industria cosmetica. Objetivo unico: detectar tendencias relevantes para formulacion, ingredientes, claims, regulacion, sostenibilidad y lanzamientos en belleza y cuidado personal. NO es un scraper de productos, ni precios, ni reviews de consumidor. Lo que buscamos son articulos noticiosos y sus senales: titulares, autor, fechas, secciones y regiones del CMS, tags tematicos nativos, resumen y cuerpo en texto plano. Fuente canonica unica a la fecha de este prompt: la seccion Beauty and wellness de nutraingredients.com bajo la ruta /Health-conditions/Beauty-wellness/. Los sitios cosmeticsdesign.com, cosmeticsdesign-europe.com y cosmeticsdesign-asia.com fueron cerrados por el editor William Reed en marzo de 2026 y redirigidos a nutraingredients. Output esperado: JSON estructurado por articulo. El resto de puntos cubre infraestructura, URLs, campos, parsing y limites.

### 2.
Infraestructura y manejo de acceso. Sitio corre sobre Arc XP Fusion CMS del grupo William Reed, servido en ingles UTF-8. Sin restriccion geografica global, pero presenta consent wall OneTrust GDPR y paywall tipo metered (article_content_type metered) que cuenta pageviews por cookie. Usar BrightData Scraping Browser con JS render activo y sesiones residenciales rotadas (preferentemente US o UK). Entre requests aplicar delay aleatorio 1 a 2 segundos, respetando Crawl-delay 1 de robots.txt. NO llamar endpoints bajo /pf/api/ (Disallow en robots.txt). NO intentar burlar el paywall: si el HTML responde con article_content_type igual a metered y paywall_hit true, flag paywalled true en la fila y seguir. Sesion nueva cada 50 requests o cuando aparezca consent wall sin resolver.

### 3.
Fuentes y URLs canonicas del crawl. Landing de seccion: https://www.nutraingredients.com/Health-conditions/Beauty-wellness/ lista articulos mas recientes (subtypes news_text y news_video). Hay 4 subregiones en la misma seccion que se filtran por taxonomy.sections del propio articulo, no por URL aparte: North-America, Europe, Asia-Pacific, Latin-America. Archivo por ano disponible en /archives/{YYYY}/ desde 2000. Sitemap Google News por seccion en /arc/outboundfeeds/sitemap/category/Health-conditions/Beauty-wellness/ devuelve XML con lastmod (util como delta incremental). Todo articulo individual vive en /Article/YYYY/MM/DD/slug/. NO existen URLs /Product-innovations/ ni /Events/ dentro del scope: son cross-promo de otros sites y se ignoran.

### 4.
Entidad article (unica entidad del scraper). Campos siempre presentes: article_id string (tomar _id del JSON Fusion), article_url string, slug string (ultimo segmento de la URL), headline string, display_date ISO 8601 UTC, publish_date ISO, first_publish_date ISO, last_updated_date ISO, website string fijo nutraingredients-v2, supplier string proveniente del input `supplier` del scraper (default "William Reed", tomado del literal de la columna Proveedor del xlsx fila #48; configurable por si el editor consolida o re-segmenta propiedades), subtype string (news_text, news_video u otro observado), scraped_date YYYY-MM-DD. Campos frecuentes con null explicito si faltan: subheadline string, description string, author_names lista de strings, author_slugs lista de strings, primary_section_path string, section_paths lista de strings, region_tags lista derivada (North-America, Europe, Asia-Pacific, Latin-America), topic_tags lista derivada (subset de section_paths tipo news), body_text string, body_word_count entero, promo_image_url string, promo_image_caption string, paywalled bool, scraper_flags lista de strings.

### 5.
Reglas de extraccion y derivacion. Fuente primaria de datos por articulo: bloque JS window.Fusion.globalContent dentro del HTML (JSON embebido). Parsear con conteo de llaves para recortar el objeto completo. De ahi se leen headlines.basic para headline, subheadlines.basic para subheadline, description.basic para description, credits.by[] para author_names y author_slugs, taxonomy.primary_section.path para primary_section_path, taxonomy.sections[].path para section_paths, promo_items.basic.url y caption para imagen. El cuerpo se arma concatenando content_elements cuyo type es text, separando con doble salto de linea; elementos header se incluyen como lineas propias; elementos image, divider, video, list se omiten del body_text pero se cuentan aparte en un contador para diagnostico. Quitar etiquetas HTML residuales (em, b, i, a) del texto final. Word count calculado split por whitespace.

### 6.
Derivacion de region_tags y topic_tags. Desde section_paths filtrar los que empiezan con /Regions/ y mapearlos a region_tags quitando el prefijo (ej /Regions/North-America da North-America). Desde section_paths filtrar los que pertenecen a navigation.type news en el CMS y mapearlos a topic_tags preservando el ultimo segmento en forma slug (ej /News/Research da Research, /Health-conditions/Beauty-wellness da Beauty-wellness). Si un articulo no tiene ningun /Regions/ asignar region_tags lista vacia y agregar flag region_missing. Fechas: display_date es la fuente de verdad para ordenamiento; si display_date es futura respecto a scraped_date emitir tal cual pero flaggear date_future. Un articulo sin headline ni body_text se descarta (skip, no emitir fila).

### 7.
Limites de crawl por corrida. Seed primario: listado /Health-conditions/Beauty-wellness/ paginado por scroll (cada carga trae 50 items a partir del primero). El cap de paginas de listado se configura via el input `max_pages` del scraper: entero; `-1` = sin limite (recorrer todas las paginas disponibles); default `-1`. Recomendacion operativa para el primer boot o smoke tests: `max_pages=20` (aprox 1000 articulos). Este cap NO reemplaza al hard cap global definido al final de este punto: el hard cap de 5000 requests o 90 minutos wall time sigue aplicando siempre, independientemente de `max_pages`. Seed secundario opcional: sitemap /arc/outboundfeeds/sitemap/category/Health-conditions/Beauty-wellness/ para modo incremental por lastmod. Ventana temporal default de la corrida: ultimos 180 dias calculados sobre display_date; articulos fuera de ventana se cuentan pero no se emiten salvo modo full-refresh. Dedupe estricto por article_id dentro de la corrida. Cache local 24 horas por article_id para no reabrir el mismo articulo dos veces el mismo dia. Hard cap global: cortar al primero de 5000 requests o 90 minutos wall time.

### 8.
Output y reglas finales. Emitir un array JSON articles_{YYYYMMDD}.json y un resumen run_{YYYYMMDD}.json con started_at, ended_at, requests, blocked, paywalled, errors, emitted, skipped_by_reason. Todo en UTF-8, fechas ISO 8601, numeros siempre numericos nunca strings, todas las claves presentes con null explicito cuando falten. Claves lista que no aplican se emiten como lista vacia, nunca null. SKIP sin emitir cuando: HTTP 404 o 410, article_id no resuelto, Fusion.globalContent ausente, headline y body_text ambos vacios. Flags validos en scraper_flags: paywalled, date_future, region_missing, body_fallback_html, fusion_parse_fallback, consent_wall_retried. Prohibido inventar campos fuera de los definidos en los puntos 4 y 6. No extraer reviews, precios, productos individuales ni comentarios de usuarios aunque aparezcan embebidos.

### 9.
URLs reales observadas al 2026-04-20, fixtures para validar parsers antes del crawl completo.

Landing: https://www.nutraingredients.com/Health-conditions/Beauty-wellness/

Sitemap incremental: https://www.nutraingredients.com/arc/outboundfeeds/sitemap/category/Health-conditions/Beauty-wellness/

Articulo news_text taxonomia rica: https://www.nutraingredients.com/Article/2026/04/20/could-specific-shifts-in-oral-bacteria-negatively-impact-menopausal-women/

Articulo tendencias nutricosmetics: https://www.nutraingredients.com/Article/2026/03/23/nutricosmetics-trends-2026-what-brands-need-to-know/

Articulo lanzamiento de marca: https://www.nutraingredients.com/Article/2026/02/13/lancome-launches-topical-longevity-skincare-with-timeline/

Articulo news_video (body desde transcripcion): https://www.nutraingredients.com/Article/2026/04/03/editor-to-editor-key-takeaways-from-expo-west-2026/

Archivo anual: https://www.nutraingredients.com/archives/2025/

### 10.
Inputs runtime del scraper. Ambos inputs son parametros del job configurables desde fuera del runtime (BrightData Scraper Studio input panel / trigger payload), NO hardcodes del codigo.

- `max_pages` (entero, default `-1`): cap de paginas del listado `/Health-conditions/Beauty-wellness/` a recorrer via scroll. `-1` = sin limite (todas las paginas que el listado exponga hasta agotarse). Sobrescribe cualquier cap histórico mencionado en prosa previa (el viejo "20 paginas" queda como recomendacion operativa para primer boot o smoke test, no como limite duro). El hard cap global del §7 (5000 requests / 90 min wall time) sigue aplicando siempre y gana sobre `max_pages`.
- `supplier` (string, default `"William Reed"`): identificador del proveedor editorial que se emite en el campo `supplier` de cada fila de output (ver §4). Default = literal de la columna `Proveedor` del xlsx `docs/specs/source-scrapers.xlsx`, hoja `scrapers`, fila #48 (`"William Reed"`). El input existe para permitir sobrescribir el valor si el editor consolida, re-segmenta o cambia de razon social sin que haga falta modificar codigo.

Ambos valores se leen al arranque del scraper y se propagan: `max_pages` al loop de paginacion del listado; `supplier` se embebe en cada objeto `article` emitido. Si el runtime no recibe el input, aplica el default documentado arriba.
