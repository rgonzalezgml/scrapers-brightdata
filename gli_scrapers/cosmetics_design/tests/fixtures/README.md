# Fixtures — cosmetics-design middleware

## `cosmetics_design_snapshot_s_demo01.json`

**Hand-crafted, NOT captured from a real BrightData run.** The snapshot id
suffix `s_demo01` is a placeholder.

WHY hand-crafted rather than real:

- This middleware is the Fase 3 POC (handoff cerrado 2026-04-22). No real
  BrightData snapshot of the cosmetics-design dataset has been captured yet
  via the Datasets v3 API.
- The closest real artifact lives in
  `scrapers/cosmetics-design/results/j_mo8omwb11xys1f1359.json`, but it was
  produced by an older parser version whose row shape (`description_basic`,
  `authors`, `word_count`, ...) does NOT match the current
  `parser_code_v1.js` contract (spec §2 + §4). Using it as a fixture would
  validate the wrong shape.

The hand-crafted rows mirror EXACTLY the dictionary returned by
`scrapers/cosmetics-design/sc_code/parser_code_v1.js` — the same 20 strict
keys (§2) plus the 6 additional §4 keys. Each row tests a different scenario:

| article_id                  | scenario covered                              |
|-----------------------------|-----------------------------------------------|
| `FAKE_ID_alpha_1234567890`  | clean Europe article, recent date             |
| `FAKE_ID_beta_9876543210`   | North-America, multi-author, no subheadline   |
| `FAKE_ID_gamma_paywalled`   | paywalled news_video, body_text null          |
| `FAKE_ID_delta_no_region`   | out-of-window date + empty region_tags        |

## TODO — replace with a real snapshot

Once we run the BrightData scraper for real (DATASET_ID populated, scraper
visible in dashboard), capture the snapshot via:

```
curl -H "Authorization: Bearer $BRIGHTDATA_API_KEY" \
  "https://api.brightdata.com/datasets/v3/snapshot/<snapshot_id>?format=json" \
  > cosmetics_design_snapshot_<snapshot_id>.json
```

Then update `conftest.py::SNAPSHOT_FIXTURE` to point at the new file and
delete this hand-crafted fixture.
