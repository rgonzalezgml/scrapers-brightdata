# Fixtures — cosme middleware

## `cosme_snapshot_s_demo01.json`

**Hand-crafted, NOT captured from a real BrightData run.** The snapshot id
suffix `s_demo01` is a placeholder.

WHY hand-crafted rather than real:

- No BrightData snapshot of the cosme dataset has been captured yet (the
  handoff has not been written and the scraper has not been triggered in
  production). The task order was inverted by user request: middleware first,
  then handoff.
- The closest real artifacts live in `/workspace/tests/cosme/fixtures/*.html`
  (raw cached HTML for fixture product ids) and
  `/workspace/scrapers/cosme/results/` (empty). Neither gives us a row the
  shape of the BrightData snapshot.

The hand-crafted rows mirror EXACTLY the dictionaries returned by the
`scrapers/cosme/vendor/sc_code/parser_code.js` (and anticipated v1 onwards) —
every key listed in §2 of `docs/specs/scrapers/cosme.md`, plus the §4 and §5
additional keys. Each row covers a scenario:

| row # | entity  | scenario covered                                                  |
|-------|---------|-------------------------------------------------------------------|
| 1     | product | fixture obligatorio spec §8 — product_id=10248076 (コスメデコルテ / ルース パウダー) |
| 2     | product | SK-II Genoptics — multi-variant, regulation=quasi_drug           |
| 3     | product | blocked / extraction-failed — `rate_limit_blocked` flag           |
| 4     | ranking | bestcosme grand 2025 rank 1 (→ product 10264676)                  |
| 5     | ranking | bestcosme category (slug=serum) rank 3 (→ product 10248076)       |
| 6     | brand   | SK-II brand page (brand_id=73) w/ product+review totals           |

### Cosme emission naming vs spec §2 naming

The scraper's JS parser emits qualified names (`product_url`,
`product_name_raw`, `brand_name`, ...) so the multi-entity output is
unambiguous on the scraper side. Spec §2 uses short names (`url`,
`name_raw`, `name`, ...). The middleware renames on the way out via
`PRODUCT_ALIASES` / `RANKING_ALIASES` / `BRAND_ALIASES` in `models.py`.

The fixture uses the **scraper-native** names (pre-rename). That way the
tests exercise the alias code path end-to-end.

### Deriving the shape

Row 1 mirrors the fixture obligatorio of spec §8: "product_id 10248076 debe
devolver product_name_raw ルース パウダー y brand_name コスメデコルテ".

Rows 1-3 (products) reproduce the exact return dict of
`scrapers/cosme/vendor/sc_code/parser_code.js` lines 665-698 — 31 keys
including debug fields `has_mojibake` and `_name_source`.

Rows 4-5 (rankings) follow spec §4:

    {source_type, award_year, award_group, award_category_slug, category_id,
     rank, product_id, product_url, product_name_raw, product_name_clean,
     brand_name_raw, ai_highlights, scraped_date}

Row 6 (brand) follows spec §5:

    {brand_id, brand_name, brand_url, brand_total_products,
     brand_total_reviews, brand_official_site, brand_country, scraped_date}

## TODO — replace with a real snapshot

Once BrightData runs the cosme scraper for real (one of
`BRIGHTDATA_DATASET_ID_COSME` or `BRIGHTDATA_COLLECTOR_ID_COSME` populated,
scraper visible in the dashboard), capture the snapshot via:

```
curl -H "Authorization: Bearer $BRIGHTDATA_API_KEY" \
  "https://api.brightdata.com/datasets/v3/snapshot/<snapshot_id>?format=json" \
  > cosme_snapshot_<snapshot_id>.json
```

Then update `conftest.py::SNAPSHOT_FIXTURE` to point at the new file and
delete this hand-crafted fixture.
