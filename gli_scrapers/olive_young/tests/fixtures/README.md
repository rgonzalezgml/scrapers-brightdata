# Fixtures — olive_young middleware

## `olive_young_snapshot_s_demo01.json`

**Hand-crafted, NOT captured from a real BrightData run.** The snapshot id
suffix `s_demo01` is a placeholder.

WHY hand-crafted rather than real:

- No BrightData snapshot of the olive-young dataset has been captured yet.
  The task order was inverted by user request: middleware first, then
  handoff / scraper iteration.
- `scrapers/olive-young/vendor/` is empty (`.gitkeep` only — DB AI has not
  produced the vendor scaffolding for this scraper yet, as of 2026-04-21).
- `scrapers/olive-young/sc_browser/` and `sc_code/` are likewise empty.
- `scrapers/olive-young/results/` only carries an `errors.md` with the
  known site gotchas (E1 `.co.kr` = 403, E2 Cloudflare challenge, E3
  ``region=Global`` rejected, E5 prdt_no pattern, E6 Vue+CSRF).

The hand-crafted rows mirror the exact dictionary shape we expect the JS
parser to emit per `docs/specs/scrapers/olive-young.md`:

### Row layout

| row # | entity  | scenario covered                                                      |
|-------|---------|-----------------------------------------------------------------------|
| 1     | ranking | KR / All / rank 1 — Anua Heartleaf Toner (prdt_no=GA240824996)        |
| 2     | ranking | KR / Skincare / rank 1 — Torriden (prdt_no=GA260338240)                |
| 3     | ranking | USA / All / rank 1 — Anua again (cross-region best_regions signal)    |
| 4     | ranking | KR / Masks / rank 7 — sold_out + cloudflare_challenge (block sample)  |
| 5     | product | Anua Heartleaf — best_regions=[KR,USA], claim_tags=[Vegan,Clean]      |
| 6     | product | Torriden — name_clean strips `(OY-Exclusive)` and `기획` suffix       |
| 7     | product | Sold-out + product_enrich_failed (sparse fallback shape)              |
| 8     | brand   | Anua (B00051) — full brand page                                       |
| 9     | brand   | Torriden (B00089) — brand_page_404 flag, og_image null                |

Totals: 4 ranking + 3 product + 2 brand = 9 rows.

### Emission naming vs spec §2 naming

The scraper's JS parser emits *long qualified* names so the multi-entity
output is unambiguous on the JS side:

- `region_code` / `category_id` / `product_name_en` / `promotion_name` on
  ranking rows.
- `product_url` / `product_name_clean_en` / `product_name_clean_kr` on
  product rows.
- `brand_url` / `brand_name_en` / `brand_name_kr` /
  `brand_total_products_in_rankings` / `brand_avg_rank` on brand rows.

Spec §2 uses the short names (`region`, `cat_id`, `name_en`, `promo`, `url`,
`total_in_rankings`, `avg_rank`). The middleware renames on the way out via
`RANKING_ALIASES` / `PRODUCT_ALIASES` / `BRAND_ALIASES` in `models.py`.

The fixture uses the **scraper-native** (long) names so the tests exercise
the alias code path end-to-end.

### Deriving the shape

- §2 `ranking`: all 11 strict keys present, plus §4 additional fields
  (site_code, category_name, product_url, brand_name_*, has_coupon,
  has_gift, thumbnail_img_url_raw, thumbnail_img_url_full, scraper_flags).
- §2 `product`: all 10 strict keys present, plus §5 additional fields
  (product_name_en / _kr, brand_name_*, rate, is_soldout, thumbnail_*,
  category_names, new_yn / best_yn / flash_yn, scraped_date, scraper_flags).
- §2 `brand`: all 5 strict keys present, plus §6 additional fields
  (brand_name_kr → aliased to name_kr, brand_og_image, scraped_date,
  scraper_flags).

Row 4 exercises the `cloudflare_challenge` flag for the BLOCK_SATURATION
saturation check. Row 7 exercises `product_enrich_failed` — the spec-allowed
flag for a product that appears in 2+ rankings but whose detail-page visit
failed.

## TODO — replace with a real snapshot

Once BrightData runs the olive-young scraper for real (one of
`BRIGHTDATA_DATASET_ID_OLIVE_YOUNG` or `BRIGHTDATA_COLLECTOR_ID_OLIVE_YOUNG`
populated, scraper visible in the dashboard), capture the snapshot via:

```bash
curl -H "Authorization: Bearer $BRIGHTDATA_API_KEY" \
  "https://api.brightdata.com/datasets/v3/snapshot/<snapshot_id>?format=json" \
  > olive_young_snapshot_<snapshot_id>.json
```

Then update `conftest.py::SNAPSHOT_FIXTURE` to point at the new file and
delete this hand-crafted fixture.
