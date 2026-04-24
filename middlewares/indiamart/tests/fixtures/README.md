# Fixtures — indiamart middleware

## `indiamart_snapshot_s_demo01.json`

**Hand-crafted, NOT captured from a real BrightData run.** The snapshot id
suffix `s_demo01` is a placeholder.

WHY hand-crafted rather than real:

- No BrightData snapshot of the indiamart dataset has been captured yet
  (the handoff has not been written and the scraper has not been triggered
  in production). The task order was inverted by user request: middleware
  first, then handoff.
- The scraper JS files under `/workspace/scrapers/indiamart/vendor/` are
  still empty placeholders (awaiting DB AI delivery). No real emission
  shape exists beyond what the spec prescribes.

The hand-crafted rows mirror the exact dictionaries
`scrapers/indiamart/sc_code/parser_code_vN.js` is expected to emit per
spec `/workspace/docs/specs/scrapers/indiamart.md` (§4, §5, §6). Every key
listed in §2 is present (`null` / `[]` when not applicable); the verbose
scraper-native names (`product_url`, `supplier_url`, `supplier_name`,
`verified_exporter`) are used so the middleware's alias code path is
exercised end-to-end.

Row layout:

| row # | entity   | scenario covered                                                             |
|-------|----------|------------------------------------------------------------------------------|
| 1     | product  | **fixture obligatorio** spec §11 — product_id=22408594448 (Caustic Soda Flakes, ₹50/kg, MOQ 20000 kg, Vats International New Delhi) |
| 2     | product  | Second caustic-soda seller (Rohan Chemicals, Mumbai) — grade=Pharma, smaller MOQ |
| 3     | product  | Blocked / parse-failed — `blocked` + `jsonld_parse_fallback` scraper_flags   |
| 4     | supplier | Vats International — `supplier_country = "India"` (free text) to exercise ISO-2 coercion; verified + trustseal + certs |
| 5     | supplier | Rohan Chemicals — `supplier_country = "IN"` already ISO-2; unverified exporter, trustseal yes |

### Scraper-native vs spec §2 naming

The scraper's JS parser is expected to emit verbose names
(`product_url`, `supplier_url`, `supplier_name`, `supplier_city`,
`verified_exporter`, ...) so the multi-entity output is unambiguous on the
scraper side. Spec §2 uses short names on the wire (`url`, `name`, `city`,
`verified`, ...). The middleware renames via `PRODUCT_ALIASES` /
`SUPPLIER_ALIASES` in `models.py`.

The fixture uses the **scraper-native** names (pre-rename) so tests
exercise the alias code path end-to-end.

### Fixture obligatorio (spec §11)

Row 1 reproduces the exact expectations spec §11 lists for product_id
22408594448:

    product_name_original = "Caustic Soda Flakes"
    price_currency        = "INR"
    price_value_raw       = "50"
    price_unit            = "kg"
    moq_quantity          = 20000
    moq_unit              = "kg"
    supplier_name         = "Vats International"
    supplier_city         = "New Delhi"
    supplier_state        = "Delhi"
    supplier_country      = "IN"
    type                  = "chemical"
    category_mic          = "Caustic Soda"
    category_path         = ["Industrial Chemicals & Supplies",
                             "Chemical Compound", "Caustic Soda"]
    industry_slug         = "chem"

Tests reference the row by `product_id` so a future real snapshot can swap
in without rewriting assertions.

## TODO — replace with a real snapshot

Once BrightData runs the indiamart scraper for real (one of
`BRIGHTDATA_DATASET_ID_INDIAMART` or `BRIGHTDATA_COLLECTOR_ID_INDIAMART`
populated, scraper visible in the dashboard), capture the snapshot via:

```
curl -H "Authorization: Bearer $BRIGHTDATA_API_KEY" \
  "https://api.brightdata.com/datasets/v3/snapshot/<snapshot_id>?format=json" \
  > indiamart_snapshot_<snapshot_id>.json
```

Then update `conftest.py::SNAPSHOT_FIXTURE` to point at the new file and
delete this hand-crafted fixture.
