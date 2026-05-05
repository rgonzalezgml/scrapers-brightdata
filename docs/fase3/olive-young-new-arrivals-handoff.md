# Handoff Fase 3 — olive-young-new-arrivals

> **Destino**: `gli_scrapers/olive_young_new_arrivals/`
> **Agente**: `middleware-python`
> **Spec**: `docs/specs/scrapers/olive_young_new_arrivals.md`

## Contexto

Scraper de I+D que captura productos de nueva llegada de Olive Young Global.
Entidad única: `new_arrival`. Complementa al scraper `olive-young` (rankings) —
join por `prdt_no`.

## Inputs

```python
class OliveYoungNewArrivalsInputs(BaseModel):
    # Sin inputs requeridos — el scraper toma el catálogo completo
    pass
```

Seed a BrightData: `[{"url": "https://global.oliveyoung.com/display/page/new-arrivals"}]`

## Shape de data[]

Entidad única `new_arrival`. Campos (spec §2):

```python
{
  "prdt_no":          "GA260338924",      # string, invariante
  "product_url":      "https://global.oliveyoung.com/product/detail?prdtNo=GA260338924",
  "product_name_en":  "...",              # null si vacío
  "product_name_kr":  "...",              # invariante
  "brand_no":         "B00051",
  "brand_name_en":    "...",
  "brand_name_kr":    "...",
  "sale_amt":         15000,              # int KRW, null si no numérico
  "nrml_amt":         18000,              # int KRW
  "image_url":        "https://cdn-image.oliveyoung.com/...",
  "is_soldout":       False,
  "is_new":           True,
  "is_best":          False,
  "is_flash":         False,
  "has_coupon":       False,
  "has_gift":         False,
  "promo_name":       None,
  "corner_name":      "New K-Beauty Essentials",
  "scraped_date":     "2026-05-03"        # YYYY-MM-DD
}
```

## Env vars

- `BRIGHTDATA_API_KEY` — compartida
- `BRIGHTDATA_COLLECTOR_ID_OLIVE_YOUNG_NEW_ARRIVALS` (DCA legacy `c_...`)
- `BRIGHTDATA_DATASET_ID_OLIVE_YOUNG_NEW_ARRIVALS` (v3 `gd_...`, gana sobre DCA)

## Tabla destino Snowflake

`SRC_OLIVEYOUNG_NEWARRIVALS` (DEV: `DEV_STG.GNM_MEX`, PROD: `PRD_STG.GNM`)

## Naming

| Capa | Convención | Valor |
|---|---|---|
| Carpeta BD scraper | hyphen | `bd_scrapers/olive-young-new-arrivals/` |
| Paquete Python | underscore | `gli_scrapers/olive_young_new_arrivals/` |
| `source` envelope | hyphen | `"olive-young-new-arrivals"` |
| Env vars | SCREAMING_SNAKE | `BRIGHTDATA_*_OLIVE_YOUNG_NEW_ARRIVALS` |
