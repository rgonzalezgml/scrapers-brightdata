# made-in-china.com — spec
https://www.made-in-china.com/
Proveedor: Focus Technology
Categoría: Precios
Función: Precios alternativos de materiales China

## databrightdata

### 1.
MIC B2B precios (vs alibaba). product+supplier. Specs JSON-LD.

### 2.
```json
{"product":["product_id","sku","site_code","product_url","product_name_original","product_name_clean","type","category_mic","category_path","price_raw","price_currency","price_min_usd","price_max_usd","price_unit","price_normalized_per_kg","moq_quantity","moq_unit","image_primary","cas_no","grade","appearance","formula","einecs","origin_country","supplier_name_raw","rating_avg","supplier_id","scraped_date","scraper_flags"],"supplier":["supplier_id","supplier_url","supplier_name","supplier_country","business_type","main_products","year_established","employees_raw","member_level","member_since_year","audited_supplier","management_certifications","scraped_date","scraper_flags"]}
```

### 3.
- `/products-search/hot-china-products/{KW}.html` (`-{N}`)
- `/{Chem|Packaging-Printing}-Catalog/{Cat}.html`;`/catalog/item{ID}/{Cat}-{N}.html`
- `{slug}.en.made-in-china.com/product/{PID}/` + `/`
- Disallow `/*.do$`. `max_pages`=-1(all)

## genomma lab

### 1.
Scraper de made-in-china.com para area de Precios B2B China. Proposito: precios alternativos de materiales chinos (quimicos industriales y empaque) como segunda fuente comparable contra alibaba. NO es un scraper de I+D: ignoramos reviews en texto libre, chat con supplier, formularios RFQ, galeria completa de imagenes, logistica detallada, catalogos de video. Buscamos senales comparables producto-a-producto: precio unitario con rango si existe, moneda, unidad, MOQ con unidad, supplier con pais y nivel de verificacion, categoria nativa MIC y specs tecnicas estructuradas (CAS, grade, appearance). Output estructurado, campos alineados con alibaba (supplier_name, supplier_country, price_min_usd, price_max_usd, price_unit, moq_quantity, moq_unit, product_name_clean, product_url, scraped_date) para que downstream compare ambos sin mapeos. Campo site fijo made-in-china. Los detalles por area vienen en los puntos siguientes.

### 2.
Infraestructura, encoding y bloqueos. Sitio UTF-8 servido en ingles en www.made-in-china.com y subdominios {slug}.en.made-in-china.com. HTTP 200 estable a curl con User-Agent Chrome y Accept-Language en-US. No dispara Cloudflare challenge observable; no requiere cookie. BrightData: proxy HTTP simple es suficiente para listing y detail (SSR entrega tarjetas sin ejecutar JS). Scraping Browser solo si una ruta devuelve body menor a 50 KB con title que contenga Access Denied o la cadena wafCloudflare. Delay 2-3 segundos entre requests por host. robots.txt del sitio: Disallow explicito a /multi-search/, /ai-search/, /price-search/, /company-search/, /advanced-search/, /sendInquiry/, /member/, /browsing-history/, /img-search/, /*.do$, /*.action$ y varios patrones mas; revisar punto 3 para rutas permitidas. Si ruta cae en Disallow emitir flag route_disallowed y skip.

### 3.
Fuentes y URLs canonicas. Tres rutas de descubrimiento permitidas. Via 1 busqueda por keyword SSR: https://www.made-in-china.com/products-search/hot-china-products/{Keyword_Underscored}.html; paginacion con sufijo _N antes de .html (ej _2, _3 hasta N). Via 2 catalogo canonico: https://www.made-in-china.com/Chemicals-Catalog/{SubCat}.html y https://www.made-in-china.com/Packaging-Printing-Catalog/{SubCat}.html; paginacion migra a https://www.made-in-china.com/catalog/item{CAT_ID}/{SubCat}-{N}.html (N desde 2) con CAT_ID extraido del href en la propia pagina de cat 1. Via 3 ficha detail: subdominio del supplier https://{slug}.en.made-in-china.com/product/{PRODUCT_ID}/{product-slug}.html; PRODUCT_ID hash alfanumerico 12 chars. Supplier home: https://{slug}.en.made-in-china.com/. Ignorar /multi-search/, /productdirectory.do, /company-search/ y shortlinks /price/prodetail_*.

### 4.
Entidad product, una fila por (product_id, scraped_date). Fuente autoritaria: JSON-LD Product embebido en el detail (script type application/ld+json @type Product). Campos siempre presentes: product_id string del path /product/{id}/; sku igual a product_id si JSON-LD trae sku; site_code fijo made-in-china; product_url canonical URL; product_name_original de Product.name del JSON-LD; product_name_clean derivado segun punto 7; type enum chemical empaque other segun breadcrumb; category_mic string del ultimo ListItem del BreadcrumbList; category_path lista de item.name del breadcrumb sin Home; price_raw del DOM clase only-one-priceNum-tr (ej US$800.00-2,000.00); price_currency ISO desde offers.priceCurrency; price_min_usd y price_max_usd numericos; price_unit enum; moq_quantity entero; moq_unit enum; image_primary primera url de Product.image; scraped_date YYYY-MM-DD; scraper_flags lista.

### 5.
Entidad product continuacion. Campos tecnicos derivados de JSON-LD additionalProperty lista de PropertyValue: cas_no string si name es CAS No; grade string si name es Quality o Grade (Industrial, Food, Cosmetic, Pharma); appearance string (Liquid, Powder, Solid); formula string; einecs string; origin_country string. Campo price_normalized_per_kg derivado igual que alibaba: si price_unit es kg entonces price_min_usd; si ton o mt dividir price_min_usd por 1000; para L piece set bag drum retornar null. Campo supplier_name_raw tomado de Product.brand.name. Campo rating_avg tomado de Product.review.reviewRating.ratingValue si existe, null si no (MIC pone en promedio 5 o rating ficticio; flag rating_synthetic cuando ratingValue es 5 y author es MIC_BUYER). Todos los campos se emiten con null explicito cuando faltan, nunca se omite la clave.

### 6.
Entidad supplier, una fila por (supplier_id, scraped_date). supplier_id derivado como slug del subdominio (ej whjindo desde whjindo.en.made-in-china.com). Fuente: supplier home. Campos: supplier_id string PK, supplier_url string canonico, supplier_name string del tag title o del header, supplier_country fijo CN cuando el subdominio termina en .en.made-in-china.com y el address del profile dice China; pais ISO-2 derivado del texto de address (ej Shandong China da CN, Ho Chi Minh Vietnam daria VN), business_type string del profile (Manufacturer Factory, Trading Company, o combinacion), main_products string, year_established entero de Year of Establishment, employees_raw string de Number of Employees, member_level enum (Diamond, Gold, Silver, Free) y member_since_year entero extraidos del bloque ob-member-info, audited_supplier bool true si aparece literal Audited Supplier, management_certifications lista de strings (ISO9001, ISO14001, etc), scraped_date, scraper_flags.

### 7.
Reglas de parsing. product_name_clean sobre product_name_original: colapsar whitespace; quitar marketing case-insensitive high quality, best price, factory direct, hot sale, free sample, top quality, OEM ODM customized wholesale bulk, best selling, China Manufacturer, Supplier Direct; quitar certs ISO\d+ CE GMP FDA REACH RoHS Kosher Halal Certified Approved; quitar ciudades CN Shandong Hebei Guangzhou Shanghai Beijing Weihai Wuhan; quitar paren largos \([^)]{20,}\); colapsar pipe slash ampersand a espacio; max 80 chars cortando en ultimo espacio; si vacio fallback a raw y flag name_clean_fallback. price_raw parse: extraer \d{1,3}(?:,\d{3})*(?:\.\d+)? tratando coma como miles; min es price_min, max price_max (igual si un solo numero); detectar unidad tras slash o tras numero (Ton, Kg, Piece, Bag, Drum, L, Set); moneda default USD si offers.priceCurrency USD. moq_quantity moq_unit parsear de 1 Ton (MOQ) con (\d+(?:[,.]\d+)?)\s*([A-Za-z]+).

### 8.
Reglas de clasificacion y tipo. type derivado del breadcrumb primario: si category_path[0] es Chemicals entonces type=chemical; si category_path[0] es Packaging o Packaging-Printing entonces type=empaque; resto other. category_mic se conserva tal cual (ej Alkali, Organic Intermediate, Packaging Materials, Stretch Film) porque es taxonomia nativa del sitio y sirve para cross-reference. SKIP sin emitir fila cuando: HTTP 404 o 410 en detail, JSON-LD Product ausente, product_id no extraible, price_raw ausente (sin precio), titulo solo en caracteres no latinos (ni A-Z ni digitos ni espacio), breadcrumb vacio o sin Chemicals ni Packaging en category_path (producto fuera de scope). FLAG no skip cuando: ratingValue sintetico 5 con MIC_BUYER (flag rating_synthetic), price_currency distinto a USD (flag price_fx_needed), price_unit no mapeable (flag price_unit_unknown), supplier profile 404 (flag supplier_profile_missing).

### 9.
Limites de crawl, output y flags. Modo primario v6: via-2 catalog con las 12 subcategorias explicitas listadas abajo. Modo secundario/opcional: via-1 keyword search (5 keywords base: industrial chemicals, packaging, sodium hydroxide industrial, hydrochloric acid industrial, packaging materials). El campo `max_pages` es configurable en runtime (ver Input schema mas abajo); el default historico de "3 paginas c/u" sigue siendo el valor inicial pero DEBE ser sobrerideable sin tocar codigo.

**12 subcategorias seed v6 — Genomma Lab (alineadas con alibaba e indiamart):**

Quimicos industriales (8):
- `Alkali` — https://www.made-in-china.com/Chemicals-Catalog/Alkali.html (familia: Alkali — NaOH, KOH)
- `Acid` — https://www.made-in-china.com/Chemicals-Catalog/Acid.html (familia: Acid — HCl, H2SO4, acido acetico)
- `Organic-Intermediate` — https://www.made-in-china.com/Chemicals-Catalog/Organic-Intermediate.html (familia: Solvent — esteres, solventes organicos; category_mic del fixture §11)
- `Ester-Derivative` — https://www.made-in-china.com/Chemicals-Catalog/Ester-Derivative.html (familia: Glycol — glicoles, esteres de glicol, propylene glycol)
- `Essential-Oil-Balsam-Fine-Chemicals` — https://www.made-in-china.com/Chemicals-Catalog/Essential-Oil-Balsam-Fine-Chemicals.html (familia: Fragrance — aceites esenciales, fragancias)
- `Surface-Disposal-Agent` — https://www.made-in-china.com/Chemicals-Catalog/Surface-Disposal-Agent.html (familia: Surfactant — agentes de superficie, tensioactivos)
- `Fungicide-Bactericide` — https://www.made-in-china.com/Chemicals-Catalog/Fungicide-Bactericide.html (familia: Preservative — fungicidas, biocidas, conservantes)
- `Inorganic-Chemicals` — https://www.made-in-china.com/Chemicals-Catalog/Inorganic-Chemicals.html (quimicos inorganicos generales — carbonatos, sulfatos, cloruros)

Empaque industrial (4):
- `Packaging-Materials` — https://www.made-in-china.com/Packaging-Printing-Catalog/Packaging-Materials.html (familia: Packaging Materials — materiales de empaque general; fixture §10)
- `Stretch-Film` — https://www.made-in-china.com/Packaging-Printing-Catalog/Stretch-Film.html (familia: Stretch Film — film estirable; fixture §10)
- `Packaging-Barrels-Buckets` — https://www.made-in-china.com/Packaging-Printing-Catalog/Packaging-Barrels-Buckets.html (familia: Drums — barriles, tambores, cubetas industriales)
- `Woven-Bag` — https://www.made-in-china.com/Packaging-Printing-Catalog/Woven-Bag.html (familia: Bags — sacos tejidos de polipropileno industriales)

Limites: hasta 800 unique PRODUCT_ID detail; hasta 200 supplier home. Dedupe product por product_id, supplier por supplier_id. Cache 24h por product_id. Hard caps: 2000 requests o 90 minutos. Output: mic_products_{YYYYMMDD}.json, mic_suppliers_{YYYYMMDD}.json, mic_run_{YYYYMMDD}.json (summary started_at, ended_at, requests, blocked, errors, emitted_by_entity, skipped_by_reason). UTF-8, fechas ISO, numeros no strings, claves siempre con null explicito, listas vacias nunca null. Flags permitidos: route_disallowed, rating_synthetic, price_fx_needed, price_unit_unknown, supplier_profile_missing, name_clean_fallback, jsonld_parse_fallback, last_updated_missing.

**Input schema del collector (sc_browser).** El collector acepta los siguientes campos de entrada, que se propagan via rerun:

- `url` (string, required): URL seed de listing, detail o supplier home.
- `max_pages` (number, optional, default `-1`): cuantas paginas de listing procesar a partir de la seed. **`-1` (default) = procesar hasta `total_pages`** (lo que indique el widget `.page-total` del listing). `N > 0` = procesar `min(N, total_pages)`. `0` se normaliza a `-1` y emite flag `max_pages_invalid` a nivel run.
- `current_page` (number, optional, default `1`): se conserva por compatibilidad con v2/v4 pero **ya no se propaga** en v5 porque todas las paginas 2..cap se encolan en paralelo desde la pagina 1 (no hay cadena secuencial). El parser puede seguir reportandolo para debug del numero de pagina derivado de `.page-current`.
- `is_rerun` (bool, optional, default `false`): `false` = pagina 1 (raiz), dispara el fan-out paralelo; `true` = pagina N>=2 encolada por el fan-out, solo extrae product_urls/supplier_urls y emite `next_stage` sin re-encolar mas reruns.

**Logica de paginacion paralela v5** (aplica SOLO a URLs de listing: via-1 search, via-2 catalog root y via-3 catalog paginado `catalog/item{CAT_ID}/...`; NO aplica a URLs de detail ni a supplier home, que no paginan):

1. **Mecanismo total_pages**: el parser de listing extrae `total_pages` del selector `span.page-total` del widget de paginacion (HTML real observado: `<span class="page-current J-page-current">1</span>/<span class="page-total">10</span>`). Devuelve `total_pages` como nuevo campo del output del parser. Si el selector no existe (listing de una sola pagina), `total_pages = 1`.
2. **Pagina 1 (`input.is_rerun === false`, raiz)**: el interaction calcula el cap con `cap = max_pages === -1 ? total_pages : Math.min(max_pages, total_pages)`. Para cada `N in 2..cap` construye la URL de pagina N y ejecuta `rerun_stage({url: urlN, is_rerun: true, max_pages})`. Todas las paginas 2..cap se encolan en paralelo (fan-out). En paralelo, procesa los product_urls/supplier_urls de la propia pagina 1 via `next_stage`.
3. **Reruns (`input.is_rerun === true`, paginas 2..cap)**: solo extraer product_urls/supplier_urls y emitir `next_stage`. **NO re-encolar** mas reruns de listing (evita explosion exponencial: si cada rerun re-encolara su propio fan-out se duplicaria la cola).
4. **Construccion de URL de pagina N**: sustitucion numerica sobre el patron `-{N}.html` del path base que devuelve `next_page_url` del parser (o, si el parser solo reporta pagina 1, derivar el patron del url propio de pagina 1 agregando el sufijo `-N` antes de `.html` para via-1 search o respetando el path `catalog/item{CAT_ID}/{SubCat}-{N}.html` para via-2 paginado). El `next_page_url` del parser sigue siendo la fuente canonica para el formato del URL base; v5 toma ese URL y le reemplaza el `{N}`.

El contrato no introduce nuevos campos de output del producto/supplier ni nuevas entidades: `total_pages` es solo un campo interno del output del parser consumido por el interaction. Es solo control de alcance del crawl, ahora ejecutado en paralelo en vez de secuencial.

### 10.
URLs reales observadas 2026-04-21, fixtures para listing y catalog.

Keyword via-1 industrial chemicals p1: https://www.made-in-china.com/products-search/hot-china-products/Industrial_Chemicals.html

Keyword via-1 industrial chemicals p2 (formato real observado, path migra a `find-china-products/0b0nolimit/` con sufijo `-{N}` antes de `.html`, guion no underscore): https://www.made-in-china.com/products-search/find-china-products/0b0nolimit/Industrial_Chemicals-2.html

Keyword via-1 industrial chemicals pN generico: https://www.made-in-china.com/products-search/find-china-products/0b0nolimit/Industrial_Chemicals-{N}.html

Keyword via-1 packaging p1: https://www.made-in-china.com/products-search/hot-china-products/Packaging.html

Widget de paginacion real en p1 (verificado con curl 2026-04-21): `<span class="page-current J-page-current">1</span>/<span class="page-total">10</span>` — el parser lee `span.page-total` para `total_pages` y dispara el fan-out paralelo del punto 9.

Catalogo root Chemicals: https://www.made-in-china.com/products/catlist/listsubcat/114/00/mic/Chemicals.html

Subcat Alkali p1: https://www.made-in-china.com/Chemicals-Catalog/Alkali.html

Subcat Alkali p2 (nota la migracion de path): https://www.made-in-china.com/catalog/item999i132/Alkali-2.html

Subcat Packaging-Materials: https://www.made-in-china.com/Packaging-Printing-Catalog/Packaging-Materials.html

Subcat Stretch-Film: https://www.made-in-china.com/Packaging-Printing-Catalog/Stretch-Film.html

Seeds v6 adicionales verificadas con curl 2026-04-24 (HTTP 200 confirmado):

Subcat Acid: https://www.made-in-china.com/Chemicals-Catalog/Acid.html

Subcat Organic-Intermediate: https://www.made-in-china.com/Chemicals-Catalog/Organic-Intermediate.html

Subcat Ester-Derivative: https://www.made-in-china.com/Chemicals-Catalog/Ester-Derivative.html

Subcat Essential-Oil-Balsam-Fine-Chemicals: https://www.made-in-china.com/Chemicals-Catalog/Essential-Oil-Balsam-Fine-Chemicals.html

Subcat Surface-Disposal-Agent: https://www.made-in-china.com/Chemicals-Catalog/Surface-Disposal-Agent.html

Subcat Fungicide-Bactericide: https://www.made-in-china.com/Chemicals-Catalog/Fungicide-Bactericide.html

Subcat Inorganic-Chemicals: https://www.made-in-china.com/Chemicals-Catalog/Inorganic-Chemicals.html

Subcat Packaging-Barrels-Buckets: https://www.made-in-china.com/Packaging-Printing-Catalog/Packaging-Barrels-Buckets.html

Subcat Woven-Bag: https://www.made-in-china.com/Packaging-Printing-Catalog/Woven-Bag.html

### 11.
URLs reales 2026-04-21, fixtures para detail y supplier.

Detail product_id IEFUtrGOCdRZ (N-Butyl Acetate CAS 123-86-4, price US$800.00-2,000.00/Ton, supplier WEIHAI JINDO): https://whjindo.en.made-in-china.com/product/IEFUtrGOCdRZ/China-CAS-No-123-86-4-High-Purity-N-Butyl-Acetate-Solvent-Industrial-Grade-Ester-Chemical-Coating-Thinner-Printing-Ink-Formulation.html

Detail product_id NpqUjCFoPvVI (Phenoxanol CAS 55066-48-3, supplier SUNWISE CHEM): https://sunwisechem.en.made-in-china.com/product/NpqUjCFoPvVI/China-Daily-Chemicals-Phenoxanol-for-Perfume-Use-CAS-55066-48-3.html

Supplier home whjindo: https://whjindo.en.made-in-china.com/

Fixture regresion obligatoria: product_id IEFUtrGOCdRZ debe emitir product_name_original exacto del JSON-LD Product.name, price_min_usd=800.0, price_max_usd=2000.0, price_unit=Ton, moq_quantity=1, moq_unit=Ton, cas_no=123-86-4, grade=Industrial, supplier_id=whjindo, supplier_country=CN, type=chemical, category_mic=Organic Intermediate.

### 12.
v6 — seeds optimizados Genomma Lab.

**Objetivo.** Reemplazar la seleccion vaga de "8 subcat chem + 4 subcat packaging" por una lista fija y verificada de 12 URLs seed canonicas. Estas seeds son el input primario del collector en v6; via-1 keyword search se mantiene como modo secundario/opcional para ampliar cobertura puntual.

**Rationale.** Las tres fuentes de precios B2B del proyecto (alibaba, indiamart, made-in-china) deben cubrir exactamente las mismas familias de materiales para que downstream pueda comparar precios cross-source sin gaps. Las familias definidas en alibaba §9 (Alkali, Acid, Solvent, Surfactant, Preservative, Fragrance, Glycol, Packaging_Drum, Packaging_Bag, Packaging_Container, Other) y en indiamart §9 (caustic-soda, hydrochloric-acid, sulphuric-acid, acetic-acid, sodium-carbonate, industrial-drums, packaging-materials, stretch-film, y variantes) son la referencia. Cada URL seed de MIC mapea a una de esas familias usando los slugs nativos del catalogo de MIC verificados con HTTP 200 el 2026-04-24.

**Las 12 URLs seed definitivas:**

Quimicos industriales (8):

| Familia cross-source | Slug MIC | URL seed |
|----------------------|----------|----------|
| Alkali (NaOH, KOH) | `Alkali` | https://www.made-in-china.com/Chemicals-Catalog/Alkali.html |
| Acid (HCl, H2SO4, acetico) | `Acid` | https://www.made-in-china.com/Chemicals-Catalog/Acid.html |
| Solvent (esteres, solventes organicos) | `Organic-Intermediate` | https://www.made-in-china.com/Chemicals-Catalog/Organic-Intermediate.html |
| Glycol (glicoles, propylene glycol) | `Ester-Derivative` | https://www.made-in-china.com/Chemicals-Catalog/Ester-Derivative.html |
| Fragrance (aceites esenciales, fragancias) | `Essential-Oil-Balsam-Fine-Chemicals` | https://www.made-in-china.com/Chemicals-Catalog/Essential-Oil-Balsam-Fine-Chemicals.html |
| Surfactant (tensioactivos, agentes superficie) | `Surface-Disposal-Agent` | https://www.made-in-china.com/Chemicals-Catalog/Surface-Disposal-Agent.html |
| Preservative (fungicidas, biocidas, conservantes) | `Fungicide-Bactericide` | https://www.made-in-china.com/Chemicals-Catalog/Fungicide-Bactericide.html |
| Inorganic general (carbonatos, sulfatos, cloruros) | `Inorganic-Chemicals` | https://www.made-in-china.com/Chemicals-Catalog/Inorganic-Chemicals.html |

Empaque industrial (4):

| Familia cross-source | Slug MIC | URL seed |
|----------------------|----------|----------|
| Packaging Materials (empaque general) | `Packaging-Materials` | https://www.made-in-china.com/Packaging-Printing-Catalog/Packaging-Materials.html |
| Stretch Film (film estirable) | `Stretch-Film` | https://www.made-in-china.com/Packaging-Printing-Catalog/Stretch-Film.html |
| Drums (barriles, tambores, cubetas industriales) | `Packaging-Barrels-Buckets` | https://www.made-in-china.com/Packaging-Printing-Catalog/Packaging-Barrels-Buckets.html |
| Bags (sacos tejidos de polipropileno industriales) | `Woven-Bag` | https://www.made-in-china.com/Packaging-Printing-Catalog/Woven-Bag.html |

**Modo de uso — como alimentar estas URLs al collector.**

Cada URL seed se pasa como input `url` al collector (sc_browser) con `is_rerun=false` y el `max_pages` deseado. El collector inicia el fan-out paralelo desde la pagina 1 de cada seed segun la logica de paginacion paralela v5 descrita en §9. Ejemplo de inputs para una corrida completa v6:

```json
[
  {"url": "https://www.made-in-china.com/Chemicals-Catalog/Alkali.html", "max_pages": 3},
  {"url": "https://www.made-in-china.com/Chemicals-Catalog/Acid.html", "max_pages": 3},
  {"url": "https://www.made-in-china.com/Chemicals-Catalog/Organic-Intermediate.html", "max_pages": 3},
  {"url": "https://www.made-in-china.com/Chemicals-Catalog/Ester-Derivative.html", "max_pages": 3},
  {"url": "https://www.made-in-china.com/Chemicals-Catalog/Essential-Oil-Balsam-Fine-Chemicals.html", "max_pages": 3},
  {"url": "https://www.made-in-china.com/Chemicals-Catalog/Surface-Disposal-Agent.html", "max_pages": 3},
  {"url": "https://www.made-in-china.com/Chemicals-Catalog/Fungicide-Bactericide.html", "max_pages": 3},
  {"url": "https://www.made-in-china.com/Chemicals-Catalog/Inorganic-Chemicals.html", "max_pages": 3},
  {"url": "https://www.made-in-china.com/Packaging-Printing-Catalog/Packaging-Materials.html", "max_pages": 3},
  {"url": "https://www.made-in-china.com/Packaging-Printing-Catalog/Stretch-Film.html", "max_pages": 3},
  {"url": "https://www.made-in-china.com/Packaging-Printing-Catalog/Packaging-Barrels-Buckets.html", "max_pages": 3},
  {"url": "https://www.made-in-china.com/Packaging-Printing-Catalog/Woven-Bag.html", "max_pages": 3}
]
```

`max_pages` es override-able en runtime. El valor 3 es el default historico del proyecto; -1 procesa hasta el total de paginas del listing.
