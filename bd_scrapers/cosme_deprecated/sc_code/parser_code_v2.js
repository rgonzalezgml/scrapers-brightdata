// cosme v2 — parser code (sc_code / Stage 2 FETCH)
//
// Logs de diagnóstico agregados 2026-04-22 para debug de E6/E8. Prefijo
// [S2-CODE/PARSE] en todos los console.log de este archivo. Sin cambios
// semánticos respecto a la revisión previa.
//
// Deltas vs v1 / vendor:
//
//   (E7) — kept from v1. Breadcrumb Source-1 candidate array stores raw
//          DOM elements and re-wraps with `$()` at the point of use,
//          matching the R10/R12 pattern used elsewhere. v1 attributed the
//          preview failure to this pattern; we now know that was a
//          true-but-partial diagnosis (see E8 below). Kept anyway as
//          defence-in-depth — the `.map(el => $(el))` + index shape is
//          fragile on BrightData regardless.
//
//   (E8) — NEW. The interaction code no longer sideloads a
//          shift_jis_fallback flag via `parse({shift_jis_fallback: ...})`
//          because that channel is not a valid `parse()` input on
//          BrightData Scraper Studio. Per runtime rule R2
//          (`docs/specs/brightdata-errors.md`), `parse()` validates its
//          argument against the scraper schema and rejects (or worse,
//          silently mishandles) unknown keys. What actually happened in
//          the v1 preview: `parse({html: decoded_html, ...})` left `$`
//          unbound / bound to garbage, so `$('body')` returned an object
//          without `.text()`, and the Scraper Studio log pointed at
//          line 178 (`const bodyText = $('body').text();`) — the FIRST
//          `.text()` call in the file, nowhere near the breadcrumb block.
//          With the interaction rewritten to use `load_html(decoded_html)`
//          before a bare `parse()`, `$` is now correctly bound to the
//          decoded HTML by the runtime itself, and the parser's own
//          mojibake self-check at `$('body').text()` is the canonical
//          (and only) source of the `shift_jis_fallback` scraper_flag.
//          The old `input.shift_jis_fallback` read is removed — that
//          input key never reached the parser in a valid way under
//          BrightData's schema-validated `parse()` contract.
//
// See `scrapers/cosme/sc_code/interaction_code_v2.js` for the full
// rationale of the decoding pipeline change. Bug E6 remains scoped to
// Stage 1 discovery (sc_browser) and is unaffected by this change.
//
// --- vendor/sc_code/parser_code.js (with E7 fix inlined below) ---
//
// cosme v2 — parser code
//
// What's new vs v1:
//  (1) Decoding precondition: verify the body has JP chars (hiragana/
//      katakana/kanji) AND no U+FFFD. If the check fails, emit flag
//      'shift_jis_fallback' (set by integration) and continue best-effort.
//      If no JP char is present even after fallback, emit flag
//      'name_extract_failed' so downstream knows all 5 name sources will
//      likely null out.
//  (2) 5-source cascade for product_name_raw (see `not_found.md` 2026-04-21):
//        1. Breadcrumb (`#header-sub` or breadcrumb nav) — last text node
//        2. Header anchor `<a href="/products/{product_id}/">...</a>`
//        3. `<title>` tag with suffix-strip regex
//        4. `<meta property="og:title">` content (same regex)
//        5. `<img alt="{name}/{brand} 商品写真 N枚目">` — first segment
//  (3) New output fields wired to schema: is_official, category_names,
//      effect_names, price_text, variants, variations.
//      These are best-effort: price/variants are technically out of the I+D
//      scope but the schema declares them, so we populate when present and
//      leave null/[] otherwise (turno 8: never empty string / 0 placeholder).
//  (4) Allowed flags extended with: 'shift_jis_fallback' (promoted from
//      'shift_jis_mojibake_detected') and 'name_extract_failed'.
//
// Corrections 2026-04-21 (post-MCP-validation against 10248076 / 10243030 /
// 10259468). See `not_found.md` 2026-04-21 (patch note) for the raw evidence.
//  (A) variations[]: previous selectors (`select.variation option`,
//      `.variation-list li`, `ul.color-list li`, `.shade-item`) DO NOT exist
//      in the real DOM. The true and cross-product-stable pattern is
//      `<a href="/variations/{variation_id}/">{label}</a>`. Switched to that
//      and now emit objects `{variation_id, label}` instead of bare strings.
//  (B) price_text / variants[]: the previous DOM selectors were also absent.
//      The reliable signal is the spec row labelled 容量・希望小売価格 (or
//      just 希望小売価格) followed by one `.info-desc` whose text is a
//      ` / `-separated list of `{volume}・{price}円` pairs. price_text now
//      uses the `.info-ttl:contains()` → `.next('.info-desc')` pattern
//      (mirroring launch_date extraction). variants[] is parsed by splitting
//      that same text and applying `^(.*?)・([\d,]+)円`.
//  (C) maker_id: added to output (was schema-absent in v1/v2). Source:
//      `<a href="/maker/maker_id/{id}">` inside `dl.maker dd`.
//  (D) category_chains[]: added as a structured parallel to the flat
//      category_ids/category_names lists. Each `dl.item-category dd` can
//      contain multiple hierarchical chains (observed on 10259468:
//      スキンケア > 化粧水・美容液… > 美容液 AND スキンケア > 美容液 >
//      ブースター・導入液). category_primary_id is now defined as the last
//      id of the FIRST chain (deterministic), not `category_ids.last()`
//      which was ambiguous across chains.

// ---------- Helpers ----------

const hasMojibake = (text) => {
  if (!text) return false;
  return /[��]/.test(text) || /[��]{3,}/.test(text);
};

const hasJPChar = (text) => {
  if (!text) return false;
  return /[ぁ-ヿ一-龯]/.test(text);
};

// Strip the Japanese trailing suffixes that cosme.net appends to <title>
// and og:title, e.g.:
//   "コスメデコルテ / ルース パウダーの公式商品情報"
//   "コスメデコルテ / ルース パウダーの口コミ一覧"
//   "コスメデコルテ / ルース パウダーの口コミ写真・動画一覧"
//   "コスメデコルテ / ルース パウダーのブログ記事"
//   "コスメデコルテ / ルース パウダーの口コミ一覧（30代 混合肌）"
// NOTE: regex is anchored at end-of-string and lists only observed suffixes.
// A greedy `の.*$` fallback would over-strip names that legitimately contain
// `の` (e.g. "オイルの泉 エッセンス"), so we enumerate instead.
const TITLE_SUFFIX_RE = /(?:の公式商品情報|の口コミ写真[・･]動画一覧|の口コミ一覧(?:（[^）]*）)?|のブログ記事|の写真(?:・動画)?一覧|の商品情報|のレビュー|のクチコミ一覧(?:（[^）]*）)?)$/;

const parseTitlePair = (text) => {
  if (!text) return { brand: null, name: null };
  const normalized = text.replace(/\s+/g, ' ').trim();
  const parts = normalized.split(/\s*[／/]\s*/);
  if (parts.length < 2) return { brand: null, name: normalized };
  const brand = parts[0].trim();
  let rest = parts.slice(1).join('/').trim();
  rest = rest.replace(TITLE_SUFFIX_RE, '').trim();
  return { brand: brand || null, name: rest || null };
};

// Trim variation suffix from img[alt] first segment.
// Observed pattern:  "ルース パウダー 001 ピンク"  or  "ルース パウダー 30ml"
// We cut off trailing tokens that are purely digits / ascii latin / unit tokens.
const stripVariationSuffix = (text) => {
  if (!text) return null;
  let out = text.trim();
  // Remove trailing size units: "30ml", "50g", "1枚", "2本", etc.
  out = out.replace(/\s+\d+(?:\.\d+)?\s*(?:ml|mL|g|個|本|枚|ml入り)\s*$/i, '');
  // Remove trailing color/variant codes like " 001 ピンク" or " 01 Rose"
  out = out.replace(/\s+\d{2,3}\s+[\p{L}\p{M}\p{N}\s]+$/u, '');
  // Remove trailing bare 3-digit variant codes like " 001"
  out = out.replace(/\s+\d{2,3}\s*$/u, '');
  return out.trim() || null;
};

const cleanProductName = (raw) => {
  if (!raw) return null;
  let cleaned = raw
    .replace(/【限定】|【数量限定】|【新発売】|【NEW】|【リニューアル】/g, '')
    .replace(/#[^\s#]*/g, '')
    .trim();
  const separatorMatch = cleaned.match(/^([^／|]+)/);
  if (separatorMatch) cleaned = separatorMatch[1].trim();
  cleaned = cleaned.replace(/\s+/g, ' ').trim();
  if (cleaned.length > 100) cleaned = cleaned.substring(0, 100);
  return cleaned || raw;
};

const parseDate = (dateStr) => {
  if (!dateStr) return null;
  const patterns = [
    /(\d{4})\/(\d{1,2})\/(\d{1,2})/,
    /(\d{4})-(\d{1,2})-(\d{1,2})/,
    /(\d{4})年(\d{1,2})月(\d{1,2})日/
  ];
  for (const re of patterns) {
    const m = dateStr.match(re);
    if (m) {
      const y = parseInt(m[1]);
      const mo = String(m[2]).padStart(2, '0');
      const d = String(m[3]).padStart(2, '0');
      const dt = new Date(`${y}-${mo}-${d}`);
      if (dt > new Date()) return null;
      return dt.toISOString().split('T')[0];
    }
  }
  // Year + month only: assume day 01
  const ym = dateStr.match(/(\d{4})年(\d{1,2})月/);
  if (ym) {
    const y = parseInt(ym[1]);
    const mo = String(ym[2]).padStart(2, '0');
    const dt = new Date(`${y}-${mo}-01`);
    if (dt > new Date()) return null;
    return dt.toISOString().split('T')[0];
  }
  return null;
};

// ---------- Decoding validation ----------
//
// Since E8 (see header): the interaction code decodes the body manually
// and then calls `load_html(decoded_html)` before `parse()`, so by the
// time we land here `$` is bound to the DECODED HTML. If mojibake is
// still visible from `$('body').text()`, either:
//   (a) the interaction couldn't decode (request failed → degraded path)
//   (b) the page genuinely contains replacement chars (rare)
// In both cases we record `shift_jis_fallback` as a downstream signal.
// The old `input.shift_jis_fallback` sideload is gone — BrightData's
// schema-validated `parse()` doesn't carry that key.

console.log(`[S2-CODE/PARSE] entry input.url=${input.url}`);

const scraper_flags = [];

const bodyText = $('body').text();
const has_mojibake = hasMojibake(bodyText);
const body_has_jp = hasJPChar(bodyText);

// Block-page signature: cosme.net emits this literal string when the peer
// IP is rate-limited or geo-blocked.
const BLOCK_SIGNATURE = 'ご利用の環境からはアクセスできません';
const has_block_signature = bodyText.indexOf(BLOCK_SIGNATURE) !== -1;

console.log(
  `[S2-CODE/PARSE] body_bytes=${bodyText.length} has_mojibake=${has_mojibake} ` +
  `body_has_jp=${body_has_jp} has_block_signature=${has_block_signature} ` +
  `shift_jis_fallback=${has_mojibake}`
);

if (has_mojibake) {
  scraper_flags.push('shift_jis_fallback');
}

if (!body_has_jp) {
  // Even after decoding, the page has no Japanese. Likely block page or 404.
  scraper_flags.push('name_extract_failed');
}

// ---------- Product ID / URL ----------

const product_id = input.url.match(/\/products\/(\d+)\//)?.[1] || null;
const product_url = $('link[rel="canonical"]').attr('href') || input.url;

console.log(`[S2-CODE/PARSE] product_id=${product_id ?? 'null'}`);

// ---------- Brand ----------

let brand_name = null;
let brand_id = null;

// Source A: LD+JSON BreadcrumbList (most reliable when present)
const ldJsonBreadcrumb = $('script[type="application/ld+json"]').toArray().find(script => {
  const html = $(script).html();
  return html && html.includes('BreadcrumbList');
});

if (ldJsonBreadcrumb) {
  try {
    const data = JSON.parse($(ldJsonBreadcrumb).html());
    if (data.itemListElement && data.itemListElement.length >= 2) {
      const brandItem = data.itemListElement[1];
      const candidateBrand = brandItem.item && brandItem.item.name;
      if (candidateBrand && !hasMojibake(candidateBrand)) {
        brand_name = candidateBrand;
      }
      const brandHref = brandItem.item && brandItem.item['@id'];
      brand_id = brandHref ? (brandHref.match(/\/brands\/(\d+)\//) || [])[1] || null : null;
    }
  } catch (e) {}
}

// Source B: DOM breadcrumb anchor to /brands/{id}/
if (!brand_id || !brand_name) {
  const brandAnchor = $('a[href*="/brands/"]').toArray().find(a => {
    const href = $(a).attr('href') || '';
    return /\/brands\/\d+\/?(\?|$)/.test(href);
  });
  if (brandAnchor) {
    const href = $(brandAnchor).attr('href') || '';
    const m = href.match(/\/brands\/(\d+)\//);
    if (m && !brand_id) brand_id = m[1];
    const txt = $(brandAnchor).text().trim();
    if (txt && !brand_name && !hasMojibake(txt)) brand_name = txt;
  }
}

// Source C: legacy cosme-specific selector (kept from v1)
if (!brand_name) {
  const legacy = $('span.brd-name a.brand').first().text().trim();
  if (legacy && !hasMojibake(legacy)) brand_name = legacy;
  if (!brand_id) {
    const href = $('span.brd-name a.brand').first().attr('href');
    brand_id = href ? (href.match(/\/brands\/(\d+)\//) || [])[1] || null : null;
  }
}

// ---------- Product name — 5-source cascade ----------

let product_name_raw = null;
let name_source = null;

// Source 1: Breadcrumb — last text node after the brand anchor.
// Template: アットコスメ > <a href="/brands/{brand_id}/">{brand}</a> > {name}
try {
  const crumbContainer = $('#header-sub').length
    ? $('#header-sub')
    : $('nav.breadcrumb, .breadcrumb, [class*="breadcrumb"]').first();
  if (crumbContainer && crumbContainer.length) {
    // Strategy: take the last anchor-or-strong text inside the breadcrumb
    // that does NOT link to /brands/ and does NOT equal "アットコスメ".
    // E7: keep raw DOM elements in the array and re-wrap with $() at use
    // time. Do NOT store pre-wrapped Cheerio instances; BrightData's
    // preview trips on `arr[i].text()` in that shape.
    const candidates = crumbContainer.find('strong, span, a').toArray()
      .filter(el => {
        const href = $(el).attr('href') || '';
        const t = $(el).text().trim();
        if (!t) return false;
        if (t === 'アットコスメ' || t === '@cosme') return false;
        if (/\/brands\//.test(href)) return false;
        return hasJPChar(t) || /[A-Za-z]/.test(t);
      });
    if (candidates.length) {
      const cand = $(candidates[candidates.length - 1]).text().trim();
      if (cand && !hasMojibake(cand)) {
        product_name_raw = cand;
        name_source = 'breadcrumb';
      }
    }
  }
} catch (e) {}
console.log(
  `[S2-CODE/PARSE] F1 breadcrumb: ` +
  `${name_source === 'breadcrumb' ? 'WON' : 'skipped (no candidate / mojibake / no container)'}`
);

// Source 2: Header anchor `<a href="/products/{product_id}/">{name}</a>`
if (!product_name_raw && product_id) {
  try {
    const selfAnchors = $(`a[href*="/products/${product_id}/"]`).toArray();
    for (const a of selfAnchors) {
      const href = $(a).attr('href') || '';
      // Require strict match of /products/{product_id}/ at end or with querystring
      if (!new RegExp(`/products/${product_id}/?(?:\\?|$)`).test(href)) continue;
      const txt = $(a).text().trim();
      if (!txt) continue;
      if (hasMojibake(txt)) continue;
      // Reject anchors whose text is pure digits or nav labels
      if (/^\d+$/.test(txt)) continue;
      if (/^(商品情報|口コミ|ブログ|写真|動画)/.test(txt)) continue;
      product_name_raw = txt;
      name_source = 'header_anchor';
      break;
    }
  } catch (e) {}
}
console.log(
  `[S2-CODE/PARSE] F2 header_anchor: ` +
  `${name_source === 'header_anchor' ? 'WON' : (product_name_raw ? 'not_tried (F1 won)' : 'skipped (no valid anchor)')}`
);

// Source 3: <title> tag with suffix strip
if (!product_name_raw) {
  const titleText = $('title').first().text().trim();
  if (titleText && !hasMojibake(titleText)) {
    const parsed = parseTitlePair(titleText);
    if (parsed.name) {
      product_name_raw = parsed.name;
      name_source = 'title';
      if (!brand_name && parsed.brand) brand_name = parsed.brand;
    }
  }
}
console.log(
  `[S2-CODE/PARSE] F3 title: ` +
  `${name_source === 'title' ? 'WON' : (product_name_raw ? 'not_tried (F1/F2 won)' : 'skipped (empty/mojibake/no-name)')}`
);

// Source 4: <meta property="og:title">
if (!product_name_raw) {
  const og = $('meta[property="og:title"]').attr('content') || '';
  if (og && !hasMojibake(og)) {
    const parsed = parseTitlePair(og);
    if (parsed.name) {
      product_name_raw = parsed.name;
      name_source = 'og_title';
      if (!brand_name && parsed.brand) brand_name = parsed.brand;
    }
  }
}
console.log(
  `[S2-CODE/PARSE] F4 og_title: ` +
  `${name_source === 'og_title' ? 'WON' : (product_name_raw ? 'not_tried (earlier won)' : 'skipped (empty/mojibake/no-name)')}`
);

// Source 5: img[alt] in the photo carousel
if (!product_name_raw) {
  try {
    const imgs = $('img[alt*="商品写真"], img[alt*="/"]').toArray();
    for (const img of imgs) {
      const alt = $(img).attr('alt') || '';
      if (!alt || hasMojibake(alt)) continue;
      // Expected: "{name}/{brand} 商品写真 N枚目"
      const firstSeg = alt.split('/')[0].trim();
      if (!firstSeg) continue;
      const stripped = stripVariationSuffix(firstSeg);
      if (stripped && hasJPChar(stripped)) {
        product_name_raw = stripped;
        name_source = 'img_alt';
        break;
      }
    }
  } catch (e) {}
}
console.log(
  `[S2-CODE/PARSE] F5 img_alt: ` +
  `${name_source === 'img_alt' ? 'WON' : (product_name_raw ? 'not_tried (earlier won)' : 'skipped (no valid img alt)')}`
);
console.log(
  `[S2-CODE/PARSE] name cascade result: name_source=${name_source ?? 'null'} ` +
  `product_name_raw=${product_name_raw ? (product_name_raw.length > 60 ? product_name_raw.substring(0, 60) + '...' : product_name_raw) : 'null'}`
);

if (!product_name_raw && !scraper_flags.includes('name_extract_failed')) {
  scraper_flags.push('name_extract_failed');
}

const product_name_clean = cleanProductName(product_name_raw);

// Cleaning fallback: if cleaning stripped everything.
if (product_name_raw && product_name_clean === product_name_raw) {
  const testClean = product_name_raw
    .replace(/【限定】|【数量限定】|【新発売】|【NEW】|【リニューアル】/g, '')
    .replace(/#[^\s#]*/g, '')
    .trim();
  if (!testClean) scraper_flags.push('name_clean_fallback');
}

// ---------- Rating ----------

const rating_text = $('.info-rating .info-rev .info-desc p.average').text().trim();
let rating_avg = rating_text ? parseFloat(rating_text) : null;
if (rating_avg !== null && (isNaN(rating_avg) || rating_avg < 0 || rating_avg > 7)) {
  scraper_flags.push('rating_invalid');
  rating_avg = null;
}

// ---------- Review counts ----------

const review_count_text = $('li.review a .num').first().text().trim();
const review_count = review_count_text
  ? parseInt(review_count_text.replace(/[(),]/g, '')) || null
  : null;

const photo_count_text = $('li.post-photo a .num').first().text().trim();
const review_count_photo = photo_count_text
  ? parseInt(photo_count_text.replace(/[(),]/g, '')) || null
  : null;

// ---------- Launch date ----------

const launch_date_text = $('.info-ttl:contains("発売日")').next('.info-desc').first().text().trim();
const launch_date = parseDate(launch_date_text);
let launch_year = null;

if (launch_date_text) {
  const yearMatch = launch_date_text.match(/(\d{4})/);
  if (yearMatch) launch_year = parseInt(yearMatch[1]);

  if (!launch_date) {
    const testDate = new Date(launch_date_text);
    if (!isNaN(testDate.getTime()) && testDate > new Date()) {
      scraper_flags.push('launch_date_future');
    }
  }
  if (/(\d{4})年(\d{1,2})月$/.test(launch_date_text)
      || /(\d{4})\/(\d{1,2})$/.test(launch_date_text)) {
    scraper_flags.push('launch_day_missing');
  }
}

// ---------- Maker ----------
//
// Source: `#product-spec dl.maker dd a` — the anchor's href is
// `/maker/maker_id/{id}` and its text is the maker display name.
// Example (cross-product-stable):
//   10248076 → /maker/maker_id/102317 → コスメデコルテ
//   10243030 → /maker/maker_id/51     → アテニア
//   10259468 → /maker/maker_id/110    → ランコム
// maker_id is a stable numeric foreign key useful for maker↔brand analytics
// (a single maker can own multiple brands); added to the contract so
// consumers don't have to re-derive it from href.

const makerAnchor = $('#product-spec dl.maker dd a').first();
const maker_name = makerAnchor.text().trim() || null;
const maker_href = makerAnchor.attr('href') || '';
const maker_id = (maker_href.match(/\/maker\/maker_id\/(\d+)/) || [])[1] || null;

// ---------- Categories (IDs + names + structured chains) ----------
//
// The product-spec `dl.item-category dd` block contains one or more taxonomy
// CHAINS. Each chain is a left-to-right sequence of anchors of the form
// `/categories/item/{id}/` separated by separators (>, ›, /) or wrapped in
// nested `<span>`s. Multiple chains appear when a product belongs to
// several branches of the cosme taxonomy simultaneously (observed on
// 10259468: two parallel chains ending in 美容液(1006) and ブースター・導入液(1072)).
//
// Strategy:
//   - Parse each top-level chain container (a `dd > span` or sibling `<br>`
//     group) as its own list of anchors. This preserves hierarchy.
//   - Maintain the flat `category_ids`/`category_names` for backwards
//     compatibility with v1 consumers.
//   - Define `category_primary_id` as the last id of the FIRST chain
//     (deterministic, order follows DOM order which follows cosme's own
//     primary-first convention).

const category_chains = [];
const category_ids = [];
const category_names = [];

{
  const ddEl = $('#product-spec dl.item-category dd').first();
  if (ddEl && ddEl.length) {
    // A "chain container" is a child span (or the dd itself if flat). We walk
    // direct children and group anchors split by line-breaks / separator
    // punctuation. Empirically cosme wraps each chain in its own `<span>`.
    const chainContainers = ddEl.children('span').toArray();
    const containersToScan = chainContainers.length > 0
      ? chainContainers
      : [ddEl.get(0)];

    for (const container of containersToScan) {
      const anchors = $(container).find('a[href*="/categories/item/"]').toArray();
      const chain = [];
      for (const a of anchors) {
        const href = $(a).attr('href') || '';
        const m = href.match(/\/categories\/item\/(\d+)\//);
        if (!m) continue;
        const id = m[1];
        const name = $(a).text().trim();
        if (hasMojibake(name)) continue;
        chain.push({ id, name: name || null });
        // Maintain flat lists (dedup by id across chains).
        if (!category_ids.includes(id)) {
          category_ids.push(id);
          if (name) category_names.push(name);
        }
      }
      if (chain.length) category_chains.push(chain);
    }
  }
}

// Primary = last id of the first chain (deterministic). Falls back to the
// flat list's last entry only if chains couldn't be parsed structurally.
let category_primary_id = null;
if (category_chains.length > 0) {
  const firstChain = category_chains[0];
  category_primary_id = firstChain[firstChain.length - 1].id;
} else if (category_ids.length > 0) {
  category_primary_id = category_ids[category_ids.length - 1];
}

// ---------- Effects (IDs + names) ----------

const effect_links = $('#product-relation-link dl dd a[href*="/categories/effect/"]').toArray();
const effect_ids = [];
const effect_names = [];
for (const el of effect_links) {
  const href = $(el).attr('href') || '';
  const m = href.match(/\/categories\/effect\/(\d+)\//);
  if (m) effect_ids.push(m[1]);
  const txt = $(el).text().trim();
  if (txt && !hasMojibake(txt)) effect_names.push(txt);
}

// ---------- Ingredient tag IDs (best-effort; spec says ~50% null) ----------

const ingredient_tag_ids = $('a[href*="/categories/ingredient/"]').toArray()
  .map(el => {
    const href = $(el).attr('href') || '';
    return (href.match(/\/categories\/ingredient\/(\d+)\//) || [])[1] || null;
  })
  .filter(Boolean);

// ---------- Regulation class ----------

let regulation_class = null;
const specText = $('#product-spec').text();
if (/医薬部外品/.test(specText)) regulation_class = 'quasi_drug';
else if (/化粧品/.test(specText)) regulation_class = 'cosmetic';
else if (/医療機器/.test(specText)) regulation_class = 'medical_device';
else if (/その他/.test(specText) && /区分|分類/.test(specText)) regulation_class = 'other';

// ---------- Official name ----------

let official_name = null;
const officialMatch = specText.match(/販売名[：:]\s*([^\n\r]+)/);
if (officialMatch) official_name = officialMatch[1].trim() || null;

// ---------- is_official ----------
//
// Heuristic: a product page is considered "official" when @cosme has verified
// it as a brand-official product. Signals observed on /products/ pages:
//   - presence of a "公式" badge (img alt / span text)
//   - a header/spec link to the brand's tieup "公式商品情報" page
//   - LD+JSON Organization or Product where "brand" matches brand_name
// We return true / false / null (if no reliable signal).

let is_official = null;
{
  const badgeText = $('body').text();
  const hasKoushikiBadge = /公式(?:商品情報|ページ|サイト)?/.test(badgeText);
  const hasTieupLink = brand_id
    ? $(`a[href*="/brands/${brand_id}/tieup/"]`).length > 0
    : false;
  if (hasKoushikiBadge || hasTieupLink) {
    is_official = true;
  } else if (body_has_jp) {
    // JP text decoded correctly but neither signal present → confidently not official
    is_official = false;
  }
  // else leave null (page didn't decode well, no reliable call)
}

// ---------- price_text (best-effort) ----------
//
// Validated against 10248076 / 10243030 / 10259468 (MCP BrightData, 2026-04-21):
// the info-spec block has a labelled row where the label element carries the
// literal 容量・希望小売価格 (or occasionally just 希望小売価格) and the
// adjacent .info-desc holds a ` / `-separated list of `{volume}・{price}円`
// pairs. We extract this with the same `.info-ttl:contains()` → `.info-desc`
// pattern already proven for launch_date, which is robust to cosme's
// occasional structural variations (nested spans, inline formatting).

let price_text = null;
{
  // Primary: 容量・希望小売価格 (the combined volume+price label — most common).
  let ttl = $('.info-ttl:contains("容量・希望小売価格")').first();
  // Fallback: 希望小売価格 alone (some products split the two rows).
  if (!ttl.length) ttl = $('.info-ttl:contains("希望小売価格")').first();
  if (ttl.length) {
    const desc = ttl.next('.info-desc').first().text().trim();
    if (desc && !hasMojibake(desc)) {
      // Collapse whitespace but preserve the ` / ` delimiters that
      // separate variant pairs — downstream regex depends on them.
      price_text = desc.replace(/[ \t\r\n　]+/g, ' ').trim();
      if (price_text.length > 500) price_text = price_text.substring(0, 500);
    }
  }
}

// ---------- variants[] (parsed from price_text) ----------
//
// Structure of the desc payload (validated 2026-04-21):
//   "6g（ミニサイズ）・3,300円 / 7g（ミニサイズ）・3,300円 / 16g・6,270円 / 20g・6,270円"
//   "175ml・1,980円 / 350ml・3,630円 / -・275円"
//   "30mL・12,430円 / 50mL(リフィル)・15,950円 / 50mL・18,700円 / 115mL・37,950円"
//
// Split on ` / ` (spaces around the slash are load-bearing; a bare `/` can
// legitimately appear inside a volume like `50mL(リフィル)`). For each pair:
//   - `^(.*?)・([\d,]+)円` — left = volume_raw (possibly `-` for unspecified),
//     right = JPY integer.
//   - Volume regex reused from v2: captures leading number + unit.
//   - sku_note: annotation in parens like (リフィル), (ミニサイズ), (限定).
// Tax status is not present in this block (cosme does not annotate 税込/税抜
// here); leave `price_tax_included` null rather than guessing.

const variants = [];
{
  if (price_text) {
    const pairs = price_text.split(/\s+\/\s+/);
    for (const raw of pairs) {
      const pair = raw.trim();
      if (!pair) continue;
      const m = pair.match(/^(.*?)・\s*([\d,]+)\s*円/);
      if (!m) continue;
      let volumeRaw = m[1].trim();
      const priceJpy = parseInt(m[2].replace(/,/g, ''));

      // Placeholder `-` (or `—`) = volume unspecified (e.g. 350ml refill on
      // 10243030 with a `-` variant for a complementary accessory).
      if (/^[-—－]$/.test(volumeRaw)) volumeRaw = null;

      // Extract sku_note: trailing parenthetical annotation. Supports both
      // full-width （…） and half-width (…).
      let skuNote = null;
      if (volumeRaw) {
        const noteMatch = volumeRaw.match(/[（(]([^）)]+)[）)]\s*$/);
        if (noteMatch) {
          skuNote = noteMatch[1].trim();
          volumeRaw = volumeRaw.replace(/[（(][^）)]+[）)]\s*$/, '').trim() || null;
        }
      }

      // Parse volume_value / volume_unit from the cleaned volumeRaw.
      let volumeValue = null;
      let volumeUnit = null;
      if (volumeRaw) {
        const vm = volumeRaw.match(/^(\d+(?:\.\d+)?)\s*(ml|mL|g|kg|個|本|枚)\b/);
        if (vm) {
          volumeValue = parseFloat(vm[1]);
          volumeUnit = /^(個|本|枚)$/.test(vm[2]) ? 'piece' : vm[2].toLowerCase();
        }
      }

      variants.push({
        volume_raw: volumeRaw,
        volume_value: volumeValue,
        volume_unit: volumeUnit,
        price_jpy: isNaN(priceJpy) ? null : priceJpy,
        price_tax_included: null,  // not annotated in this row
        sku_note: skuNote
      });
    }
  }
}

// ---------- variations[] ----------
//
// Validated cross-product pattern (2026-04-21 MCP scrape of 10248076,
// 10243030, 10259468): variations live as anchors of the form
// `<a href="/variations/{variation_id}/">{label}</a>`. The old v2 selectors
// (select.variation option, .variation-list li, ul.color-list li,
// .shade-item) are not present in cosme's real DOM. Each element now
// contributes an object `{variation_id, label}` so downstream can join to
// a future variations crawl without re-scraping.

const variations = [];
{
  const variationAnchors = $('a[href*="/variations/"]').toArray();
  const seen = new Set();
  for (const el of variationAnchors) {
    const href = $(el).attr('href') || '';
    const m = href.match(/\/variations\/(\d+)\//);
    if (!m) continue;
    const variationId = m[1];
    if (seen.has(variationId)) continue;  // dedupe: the same anchor can appear in list + detail panels
    const label = $(el).text().replace(/\s+/g, ' ').trim();
    if (!label || hasMojibake(label)) continue;
    if (/^(選択|選んでください|please select)$/i.test(label)) continue;
    seen.add(variationId);
    variations.push({ variation_id: variationId, label });
  }
}

// ---------- Rankings ----------

const ranking_links = $('#product-spec dl.bestcosme dd li a').toArray();
const rankings = ranking_links.map(el => {
  const text = $(el).text().trim();
  let year = null;
  const yearTextMatch = text.match(/(\d{4})/);
  if (yearTextMatch) year = parseInt(yearTextMatch[1]);
  let position = null;
  const positionMatch = text.match(/第(\d+)位/);
  if (positionMatch) position = parseInt(positionMatch[1]);
  let scope = null;
  if (text.includes('上半期')) scope = 'H1';
  else if (text.includes('下半期')) scope = 'H2';
  else if (text.includes('アワード')) scope = 'annual';
  return { ranking_name: text, position, year, scope };
});

// ---------- Final assembly ----------

console.log(
  `[S2-CODE/PARSE] final counts: category_ids=${category_ids.length} ` +
  `effect_ids=${effect_ids.length} rankings=${rankings.length} ` +
  `scraper_flags=[${scraper_flags.join(',')}]`
);

return {
  product_id,
  product_url: product_url ? new URL(product_url) : null,
  product_name_raw,
  product_name_clean,
  brand_id,
  brand_name,
  category_primary_id,
  category_ids,
  category_names,
  category_chains,
  effect_ids,
  effect_names,
  ingredient_tag_ids,
  rating_avg,
  review_count,
  review_count_photo,
  launch_date,
  launch_year,
  regulation_class,
  official_name,
  is_official,
  maker_id,
  maker_name,
  price_text,
  variants,
  variations,
  rankings,
  scraped_date: new Date().toISOString(),
  scraper_flags,
  has_mojibake,
  // Debug-only (not part of the contract but useful for post-mortem):
  _name_source: name_source
};
