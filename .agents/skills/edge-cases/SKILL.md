---
name: edge-cases
description: "Analyze a feature or scraper spec for edge cases, failure modes, and scenarios that might be missed. Use after describing a new scraper or feature to strengthen the spec before implementation. Triggers on: analyze edge cases, find edge cases, what could go wrong, edge case analysis."
---

# Edge Case Analysis

Systematically analyze a feature or scraper description to identify edge cases, failure modes, and scenarios that might be overlooked during implementation.

---

## The Job

1. Read the provided spec or feature description thoroughly
2. Analyze each requirement against the categories below
3. Rate each edge case by severity
4. Propose additions to the spec: new backlog items, new acceptance criteria, or design notes

**Output:** List of edge cases with severity and recommended spec update.

---

## Edge Case Categories

### 1. Network & Proxy Edge Cases (scraper-specific)
- **Proxy ban / IP block:** Target site blocks the BrightData IP — what happens?
- **CAPTCHA triggered:** Site presents a CAPTCHA mid-session
- **Proxy timeout:** BrightData connection times out before response
- **Rate limiting:** Site returns 429 Too Many Requests
- **SSL errors:** Site has invalid or self-signed certificate
- **Redirect chains:** Site redirects multiple times before reaching content

### 2. DOM / Data Structure Edge Cases
- **Missing fields:** Expected CSS selector or JSON key is absent from the response
- **Empty values:** Field exists but is empty string, null, or whitespace-only
- **Schema change:** Site redesigns — selectors no longer match
- **Lazy-loaded content:** Data only appears after scroll or user interaction (JS rendering)
- **Paginated results:** Data spans multiple pages — last page has fewer items or no "next" link
- **Duplicate records:** Same item appears multiple times across pages or runs

### 3. Data Quality Edge Cases
- **Encoding issues:** Non-UTF-8 characters, emoji, RTL text in scraped fields
- **Type mismatches:** Field expected as number contains "N/A", "—", or formatted string like "1,234"
- **Date format variations:** Same field uses different date formats across records
- **Boundary values:** Price = 0, quantity = negative, date in the future or very old
- **Large payloads:** Page has 10,000 items instead of 100 — memory and timeout impact

### 4. State & Execution Edge Cases
- **Partial run failure:** Scraper fails halfway through — is partial data saved or discarded?
- **Concurrent runs:** Two executions run at the same time — data collision or duplication?
- **Stale session:** BrightData session expires mid-scrape
- **Idempotency:** Running the scraper twice — does it produce duplicate records or overwrite cleanly?

### 5. Error Handling Edge Cases
- **HTTP 4xx responses:** 403 Forbidden, 404 Not Found, 410 Gone — are they handled differently?
- **HTTP 5xx responses:** Server errors — retry logic? Give up after N attempts?
- **Malformed HTML/JSON:** Response is truncated, garbled, or returns an error page as 200 OK
- **BrightData API errors:** WebSocket disconnect in Scraping Browser mode

### 6. Security Edge Cases
- **Prompt injection in scraped content:** Scraped text contains instructions aimed at Claude
- **Path traversal:** Scraped filename used in file operations — sanitize before use
- **Credential leakage:** Error messages or logs expose proxy password or session token
- **Untrusted data execution:** Scraped JS or HTML content must never be `eval()`-ed

### 7. Output & Delivery Edge Cases
- **Empty result set:** No items match the criteria — is an empty file/dataset valid output?
- **Output file already exists:** Overwrite, append, or error?
- **Destination unavailable:** Snowflake / S3 / target system is down when scraper finishes

---

## Analysis Process

For each requirement in the spec or feature description:

1. **Apply category checklist** — which categories apply?
2. **Rate severity:**
   - **Critical:** Data loss, credential leak, silent incorrect data, or system crash
   - **High:** Scraper silently produces wrong or incomplete data, or fails without alerting
   - **Medium:** Scraper fails with a clear error, retry handles it eventually
   - **Low:** Minor annoyance, cosmetic, or extremely unlikely scenario
3. **Propose spec update:**
   - **Backlog item** — for items that need to be addressed but not immediately
   - **Acceptance criterion** — for items that must be verified before the scraper ships
   - **Design note** — for architectural decisions that the spec should document

---

## Output Format

```markdown
# Edge Case Analysis for {Scraper/Feature Name}

## Summary
- Total edge cases identified: X
- Critical: X | High: X | Medium: X | Low: X

## Edge Cases

| Edge Case | Category | Severity | Recommended Action |
|-----------|----------|----------|--------------------|
| Proxy gets banned mid-run | Network & Proxy | High | Add retry with exponential backoff; add to backlog |
| Price field returns "N/A" | Data Quality | High | Add acceptance criterion: price field must handle non-numeric gracefully |
| Scraper runs twice simultaneously | State & Execution | Medium | Add design note: document idempotency strategy |

## Recommended Spec Additions

### Backlog Items
- [ ] Implement retry logic with exponential backoff for 429 and proxy ban responses — severity: High
- [ ] Handle concurrent runs (idempotency strategy) — severity: Medium

### Acceptance Criteria to Add
- Price field parser must return `None` (not raise) for non-numeric values like "N/A"
- Scraper must log a clear error and exit cleanly on HTTP 403 (no partial output)

### Design Notes to Add
- Document chosen idempotency strategy: overwrite vs. append vs. deduplication key
```

---

## Integration with Module Specs

Edge cases identified here do not get discarded — they feed the spec lifecycle:

1. **Critical and High edge cases → spec Backlog** — add as backlog items in `docs/specs/{modulo}-spec.md`.
2. **Backlog items without tests = explicit technical debt** — the `analista-de-scrapers` agent will see them and document them as pending test coverage.
3. **For existing scrapers** — read the current spec's Backlog before analyzing. Do not duplicate existing items; reference them.

```
Feature / new scraper description
    ↓ edge-cases (this skill)
Edge cases identified
    ↓
Spec Backlog (docs/specs/{modulo}-spec.md)
    ↓ module-specs
Tests derived from spec
```
