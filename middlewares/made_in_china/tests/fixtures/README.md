# Fixtures — made_in_china middleware

## `made_in_china_snapshot_s_demo01.json`

**Hand-crafted, NOT captured from a real BrightData run.** The snapshot id
suffix `s_demo01` is a placeholder.

WHY hand-crafted rather than real:

- No BrightData snapshot of the made-in-china dataset has been captured yet
  (the handoff has not been written and the scraper is still iterating v5 →
  v6). The task order was inverted by user request: middleware first, then
  handoff.
- The closest real artifact lives in `/workspace/scrapers/made-in-china/results/j_mo8omwb11xys1f1359.json`,
  but that JSON is from the cosmetics-design scraper (it was saved under
  this folder by mistake; see `/workspace/scrapers/made-in-china/results/registry.md`).
  It does NOT carry product/supplier rows matching spec §2.

The hand-crafted rows mirror EXACTLY the dictionaries returned by
`scrapers/made-in-china/sc_code/parser_code_v3.js` (the latest product +
supplier parser). Every key listed in §2 of
`docs/specs/scrapers/made-in-china.md` is present per row, plus the `entity`
discriminator that the middleware adds.

## Row layout

| row # | entity   | scenario covered                                                              |
|-------|----------|-------------------------------------------------------------------------------|
| 1     | product  | fixture obligatorio spec §11 — product_id=IEFUtrGOCdRZ (N-Butyl Acetate)      |
| 2     | product  | Phenoxanol CAS 55066-48-3, supplier sunwisechem — different category          |
| 3     | product  | Packaging-Materials with incomplete specs — `price_unit_unknown` flag         |
| 4     | product  | Bot-blocked row — `blocked` + `route_disallowed` flags                        |
| 5     | supplier | WEIHAI JINDO supplier home — supplier_id=whjindo, country=CN                  |
| 6     | supplier | Free-text country "Vietnam" — middleware normalizes to ISO-2                  |

Rows 1-4 target the product entity catalog (§2 + §4 + §5). Rows 5-6 exercise
the supplier entity (§2 + §6) and the ISO-2 country normalization safety net.

## Key aliases (parser-native vs §2 wire)

The v3 parser already emits §2 canonical names directly (`product_url`,
`product_name_original`, `supplier_country`, etc.) — the aliases in
`models.py` exist as safety nets for legacy vendor output. To still exercise
the alias code path, row 3 uses two legacy short forms (`url`, `name_clean`)
that the middleware renames to `product_url` / `product_name_clean`.

## Fixture obligatorio compliance (spec §11)

Row 1 must emit (after middleware normalization):

- `product_id == "IEFUtrGOCdRZ"`
- `product_name_original` exact from JSON-LD `Product.name`
- `price_min_usd == 800.0`, `price_max_usd == 2000.0`
- `price_unit == "Ton"`
- `moq_quantity == 1`, `moq_unit == "Ton"`
- `cas_no == "123-86-4"`, `grade == "Industrial"`
- `supplier_id == "whjindo"`
- `type == "chemical"`, `category_mic == "Organic Intermediate"`

The supplier_country for `whjindo` is not asserted on row 1 (product entity
does not carry it per spec §5); the supplier_country test lives on row 5.

## TODO — replace with a real snapshot

Once BrightData runs the made-in-china scraper in production (one of
`BRIGHTDATA_DATASET_ID_MADE_IN_CHINA` or
`BRIGHTDATA_COLLECTOR_ID_MADE_IN_CHINA` populated, scraper visible in the
dashboard), capture the snapshot via:

```
curl -H "Authorization: Bearer $BRIGHTDATA_API_KEY" \
  "https://api.brightdata.com/datasets/v3/snapshot/<snapshot_id>?format=json" \
  > made_in_china_snapshot_<snapshot_id>.json
```

Then update `conftest.py::SNAPSHOT_FIXTURE` to point at the new file and
delete this hand-crafted fixture.
