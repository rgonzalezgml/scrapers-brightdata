# Fixtures — alibaba middleware

## `alibaba_snapshot_s_demo01.json`

**Hand-crafted, NOT captured from a real BrightData run.** The snapshot id
suffix `s_demo01` is a placeholder.

WHY hand-crafted rather than real:

- No BrightData snapshot of the alibaba dataset has been captured yet. The
  task order was inverted by user request: middleware first, then the fase 3
  handoff — no live run has executed against the Studio or DCA endpoints
  declared in `docs/specs/scrapers/alibaba.md` §2/§3.
- The closest real artifacts live in `scrapers/alibaba/vendor/sc_*/` (the
  DB AI-generated parsers) and `scrapers/alibaba-old/` (legacy Python
  scraper). Neither gives us a row the shape of a BrightData snapshot; we
  would have to trigger the collector to produce one.

The hand-crafted rows mirror the shape the v1+ JS parser WILL emit once the
vendor gap is closed, per `docs/specs/scrapers/alibaba.md`:

- §2 strict keys (16) — every row carries all of them.
- §5 reputation keys (3 — `supplier_rating`, `supplier_reviews_count`,
  `supplier_response_rate`) — present where applicable, null otherwise.
- Free-text supplier countries ("China", "United States", "Narnia") so the
  middleware's ISO-2 normalization path is exercised in both the mapped and
  unmapped cases.

### Row scenario map

| row # | scenario covered                                                  |
|-------|-------------------------------------------------------------------|
| 1     | Canonical product (spec §11): Glycerin Industrial Grade Liquid, Shandong supplier, full price range, rating present. Tests alias rename (`cleaned_product_name` → `product_name_clean`), ISO-2 passthrough. |
| 2     | Packaging product (Packaging_Drum), US supplier identified by long-form country label ("United States") → ISO-2 mapping exercised. |
| 3     | Minimum-viable product: only `product_url` + `product_name_clean`; every other §2 key missing → null / [] defaults exercised. |
| 4     | Blocked row: `rate_limit_blocked` in scraper_flags → feeds BLOCK_SATURATION counter. |
| 5     | Missing-price row: price_raw present but `price_min_usd` is null (RFQ-gated supplier) → feeds PRICE_MISSING_SATURATION counter. |
| 6     | Unmapped country: `supplier_country="Narnia"` → middleware emits null + `country_unmapped` flag. |

### Deriving the shape

Row 1 mirrors the shape documented in spec §11 ("Shape canonico (ejemplo
fixture)"), row-by-row. Row 2 adapts it for a packaging SKU. Rows 3-6
cover the null / degraded / edge cases that the skip-rules and
saturation-checks depend on.

### Vendor-native vs spec-§2 names

The current vendor `parser_code.js` emits *different* keys than spec §2:

    cleaned_product_name  →  product_name_clean
    minimum_order_quantity → moq_quantity

The fixture intentionally mixes both so the tests exercise the alias code
path end-to-end. Rows 1-2 use the vendor keys; rows 3-6 use spec §2 keys
directly.

## TODO — replace with a real snapshot

Once BrightData runs the alibaba scraper for real (one of
`BRIGHTDATA_DATASET_ID_ALIBABA` or `BRIGHTDATA_COLLECTOR_ID_ALIBABA`
populated, scraper visible in the dashboard), capture the snapshot via:

```
curl -H "Authorization: Bearer $BRIGHTDATA_API_KEY" \
  "https://api.brightdata.com/datasets/v3/snapshot/<snapshot_id>?format=json" \
  > alibaba_snapshot_<snapshot_id>.json
```

Then update `conftest.py::SNAPSHOT_FIXTURE` to point at the new file and
delete this hand-crafted fixture.
