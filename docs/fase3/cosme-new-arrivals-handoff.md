# Handoff Fase 3 — cosme-new-arrivals

> **Destino**: `gli_scrapers/cosme_new_arrivals/`
> **Agente**: `middleware-python`
> **Spec**: `docs/specs/scrapers/cosme_new_arrivals.md`

## Contexto

Scraper de I+D que captura el calendario de lanzamiento de nuevos productos
cosméticos en Japón desde cosme.net. Entidad única: `new_product`.
Complementa al scraper `cosme` (rankings) — join por `product_id`.

## Inputs

```python
class CosmeNewArrivalsInputs(BaseModel):
    year:  int  # ej. 2026
    month: int  # 1-12
```

Seed a BrightData: `[{"url": "https://www.cosme.net/calendar/index/year/{year}/month/{month:02d}"}]`

## Shape de data[]

Entidad única `new_product`. Campos (spec §2):

```python
{
  "product_id":   "10260179",      # string, invariante
  "product_url":  "https://www.cosme.net/products/10260179/",
  "product_name": "イドル リップ バターグロウ",   # japonés UTF-8
  "brand_id":     "42",            # string, null si sin link
  "brand_name":   "ランコム",       # japonés
  "brand_url":    "https://www.cosme.net/brands/42/",  # null si sin link
  "release_date": "2026-05-01",    # YYYY-MM-DD
  "shop_url":     "https://www.cosme.com/products/detail.php?product_id=339926",  # null si JS modal
  "scraped_at":   "2026-05-03T18:00:00Z"  # ISO 8601
}
```

## Env vars

- `BRIGHTDATA_API_KEY` — compartida
- `BRIGHTDATA_COLLECTOR_ID_COSME_NEW_ARRIVALS` (DCA legacy `c_...`)
- `BRIGHTDATA_DATASET_ID_COSME_NEW_ARRIVALS` (v3 `gd_...`, gana sobre DCA)

## Tabla destino Snowflake

`SRC_COSME_RANKING_NEWARRIVALS` (DEV: `DEV_STG.GNM_MEX`, PROD: `PRD_STG.GNM`)

## Naming

| Capa | Convención | Valor |
|---|---|---|
| Carpeta BD scraper | hyphen | `bd_scrapers/cosme-new-arrivals/` |
| Paquete Python | underscore | `gli_scrapers/cosme_new_arrivals/` |
| `source` envelope | hyphen | `"cosme-new-arrivals"` |
| Env vars | SCREAMING_SNAKE | `BRIGHTDATA_*_COSME_NEW_ARRIVALS` |
