# BrightData webhook config por scraper

Todo lo necesario para configurar el webhook de cada collector en BrightData.
**Una sección por scraper, todo copy-paste ready.**

---

## Datos compartidos por todos los scrapers

### Token PAT (Authorization header value — pegar tal cual)

```
Snowflake Token="<SNOWFLAKE_PAT_REDACTED>"
```

PAT name: `BRIGHTDATA_WEBHOOK_PAT` (user RGONZALEZA, role DEVELOPER_ROLE, expira 2026-06-10).

### Settings del delivery (iguales para todos)

| Campo | Valor |
|---|---|
| Method | `POST` |
| Format | `JSON` |
| Compression | `Uncompressed` (uncompressed_webhook=true) |
| `flatten_csv` | `false` |
| `delivery_type` | `deliver_results` |
| Send on | `On data ready` / `On run completed` |

### Parámetro `?clean=true` (opcional, por scraper)

El endpoint acepta el query param `?clean=true` en la URL del webhook.
Cuando está presente, el SERVICE borra **toda la tabla** antes de insertar las filas nuevas (replace en lugar de append). Sin el param, el comportamiento es siempre append.

| Scraper | Modo |
|---|---|
| alibaba, indiamart, made_in_china, cosmetics_design, olive_young_new_arrivals, cosme_new_arrivals | append (sin param) |
| **cosme_ranking_products** | **replace** (`?clean=true` — ranking semanal, no acumula) |
| **olive_young** | **replace** (`?clean=true` — ranking best-seller, no acumula) |

---

## 1. alibaba

### URL del webhook

```
https://jsbytg2-qob68501-genommalab.snowflakecomputing.app/webhook/alibaba
```

### Collector ID

```
c_mnypbnxc1u871q7sgb
```

### Inputs que le pasamos HOY (desde `gli_scrapers/alibaba/config.py`)

```python
search_terms      = [
                      "industrial chemicals",
                      "industrial packaging drums barrels",
                      "sodium hydroxide industrial",
                      "hydrochloric acid industrial",
                      "chemical packaging containers",
                    ]
max_pages         = 10
supplier_country  = "CN"
min_price         = 1.0
max_price         = 10000.0
```

### Tabla destino

| Env | Tabla |
|---|---|
| DEV | `DEV_STG.GNM_MEX.SRC_ALIBABA_PROV_HIST` |
| PROD | `PRD_STG.GNM.SRC_ALIBABA_PROV_HIST` |

### ETA aproximada por run

10 minutos.

---

## 2. indiamart

### URL del webhook

```
https://jsbytg2-qob68501-genommalab.snowflakecomputing.app/webhook/indiamart
```

### Collector ID

```
c_mo90ehh42wq2ili8
```

### Inputs que le pasamos HOY

```python
mcat_slugs      = [
                    "caustic-soda",
                    "sodium-hydroxide-pellets",
                    "hydrochloric-acid",
                    "sulphuric-acid",
                    "sodium-carbonate",
                    "acetic-acid",
                    "industrial-drums",
                    "industrial-containers",
                    "plastic-drums",
                    "corrugated-box",
                    "packaging-materials",
                    "stretch-film",
                  ]
industry_hubs   = ["chem", "packaging"]
inr_to_usd      = 0.012
```

### Tabla destino

| Env | Tabla |
|---|---|
| DEV | `DEV_STG.GNM_MEX.SRC_INDIAMART_PROV_HIST` |
| PROD | `PRD_STG.GNM.SRC_INDIAMART_PROV_HIST` |

### ETA aproximada por run

45 minutos.

---

## 3. made_in_china

### URL del webhook

```
https://jsbytg2-qob68501-genommalab.snowflakecomputing.app/webhook/made_in_china
```

### Collector ID

```
c_mo8p01aj1401mhi4sn
```

### Inputs que le pasamos HOY

```python
seed_urls   = [
  "https://www.made-in-china.com/Chemicals-Catalog/Alkali.html",
  "https://www.made-in-china.com/Chemicals-Catalog/Acid.html",
  "https://www.made-in-china.com/Chemicals-Catalog/Organic-Intermediate.html",
  "https://www.made-in-china.com/Chemicals-Catalog/Ester-Derivative.html",
  "https://www.made-in-china.com/Chemicals-Catalog/Essential-Oil-Balsam-Fine-Chemicals.html",
  "https://www.made-in-china.com/Chemicals-Catalog/Surface-Disposal-Agent.html",
  "https://www.made-in-china.com/Chemicals-Catalog/Fungicide-Bactericide.html",
  # (lista completa en gli_scrapers/made_in_china/config.py — DEFAULT_SEED_URLS)
]
max_pages   = 20
```

### Tabla destino

| Env | Tabla |
|---|---|
| DEV | `DEV_STG.GNM_MEX.SRC_MADEINCHINA_PROV_HIST` |
| PROD | `PRD_STG.GNM.SRC_MADEINCHINA_PROV_HIST` |

### ETA aproximada por run

45 minutos.

---

## 4. cosmetics_design

### URL del webhook

```
https://jsbytg2-qob68501-genommalab.snowflakecomputing.app/webhook/cosmetics_design
```

### Collector ID

```
c_mo881p3h23z6ctghqw
```

### Inputs que le pasamos HOY

```python
supplier = "William Reed"   # filtro por proveedor de la nota
# El scraper no recibe URLs seed: scrapea cosmeticsdesign.com con su own
# lista interna de URLs (categorías "Markets", "Manufacturers", "R&D").
```

### Tabla destino

| Env | Tabla |
|---|---|
| DEV | `DEV_STG.GNM_MEX.SRC_COSMETICDESIGN_ART_HIST` |
| PROD | `PRD_STG.GNM.SRC_COSMETICDESIGN_ART_HIST` |

### ETA aproximada por run

30 minutos (típicamente ~1000 artículos por run).

---

## 5. cosme_ranking_products

### URL del webhook

```
https://jsbytg2-qob68501-genommalab.snowflakecomputing.app/webhook/cosme_ranking_products?clean=true
```

> `?clean=true` — cada entrega de BrightData borra la tabla completa antes de insertar,
> igual que el runner Python. Sin este param el endpoint hace append.

### Collector ID

```
c_mohk9yhu2b1qsuso67
```

### Inputs que le pasamos HOY

```python
# Sin inputs públicos — el scraper toma siempre el ranking semanal top-100
# de cosme.net (página fija, sin parámetros).
```

### Tabla destino

| Env | Tabla |
|---|---|
| DEV | `DEV_STG.GNM_MEX.SRC_COSME_RANKING_HIST` |
| PROD | `PRD_STG.GNM.SRC_COSME_RANKING_HIST` |

### ETA aproximada por run

15 minutos.

---

## 6. olive_young

### URL del webhook

```
https://jsbytg2-qob68501-genommalab.snowflakecomputing.app/webhook/olive_young?clean=true
```

### Collector ID

```
c_mob060tkv07mp3ft9
```

### Inputs que le pasamos HOY

```python
listing_url           = "https://global.oliveyoung.com/display/page/best-seller?target=pillsTab1Nav2"
max_pages             = 20
max_products_enrich   = 100   # detail-page enrichments por run
max_brand_visits      = 20    # brand-page visits por run
```

### Tabla destino

| Env | Tabla |
|---|---|
| DEV | `DEV_STG.GNM_MEX.SRC_OLIVEYOUNG_RANK_HIST` |
| PROD | `PRD_STG.GNM.SRC_OLIVEYOUNG_RANK_HIST` |

### ETA aproximada por run

25 minutos.

---

## 7. olive_young_new_arrivals

### URL del webhook

```
https://jsbytg2-qob68501-genommalab.snowflakecomputing.app/webhook/olive_young_new_arrivals
```

### Collector ID

```
c_moqkkvdq8xisc0fed
```

### Inputs que le pasamos HOY

```python
max_products = 500
# Listing fijo: new-arrivals top de olive-young (no recibe URL seed).
```

### Tabla destino

| Env | Tabla |
|---|---|
| DEV | `DEV_STG.GNM_MEX.SRC_OLIVEYOUNG_NEWARRIVALS` |
| PROD | `PRD_STG.GNM.SRC_OLIVEYOUNG_NEWARRIVALS` |

### ETA aproximada por run

20 minutos.

---

## 8. cosme_new_arrivals

### URL del webhook

```
https://jsbytg2-qob68501-genommalab.snowflakecomputing.app/webhook/cosme_new_arrivals
```

### Collector ID

```
c_mord1htg2qb2o0uwpy
```

### Inputs que le pasamos HOY

```python
# Sin inputs públicos — toma siempre la página fija de new-arrivals de cosme.net.
```

### Tabla destino

| Env | Tabla |
|---|---|
| DEV | `DEV_STG.GNM_MEX.SRC_COSME_RANKING_NEWARRIVALS` |
| PROD | `PRD_STG.GNM.SRC_COSME_RANKING_NEWARRIVALS` |

### ETA aproximada por run

30 minutos.

---

## Verificación post-envío (genérico)

```bash
# Logs del SERVICE — ver POST entrando, ETL y resumen final
/workspace/scripts/deploy_spcs/webhook_receiver.sh logs 100 \
  | grep -iE 'webhook-raw|inserted|ERROR|done'

# Conteo en la tabla destino (cambiar la tabla según scraper)
snow sql -c genommalab -q "
SELECT COUNT(*) AS rows_last_15min,
       MAX(CREATED_USR) AS sample_user,
       MAX(CREATED_AT)  AS last_load
FROM DEV_STG.GNM_MEX.SRC_COSME_RANKING_HIST
WHERE CREATED_AT > DATEADD(minute, -15, CURRENT_TIMESTAMP());
"

# Test desde el devcontainer sin pasar por BrightData
python3 /workspace/scripts/deploy_spcs/test_webhook.py webhook cosme_ranking_products
```
