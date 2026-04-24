// cosme v4 — integration code (sc_browser stage)
//
// Stage 1 of the 2-stage pipeline:
//   Stage 1 (this file) = DISCOVERY — headless Chrome navigates the bestcosme
//     archive / category / award pages, extracts product URLs, and emits each
//     as a next_stage() input for Stage 2.
//   Stage 2 (sc_code/v2) = FETCH — plain HTTP against the product URL, parses
//     the Shift-JIS-decoded body and emits the product record.
//
// v4 changes vs v3:
//   v3 invoked parse() passing an object as input: parse({ award_year }). The
//   BrightData runtime validates the input of parse() against an internal
//   schema and rejects undeclared fields, so v3 rebounded with:
//     Crawler error: parse validation error: "[0].award_year" is not allowed
//   See FINDINGS.md "Restricciones del runtime de BrightData" rule R4.
//
//   So v4 calls parse() with NO arguments. The parser code (parser_code.js v4)
//   no longer reads input.award_year; instead it derives the year from
//   location.href via the regex /bestcosme\/archive\/(\d+)\//, with a fallback
//   to new Date().getFullYear() if the URL does not match (should not happen
//   for valid archive paths, but kept for safety).
//
//   The integration code STILL needs award_year to:
//     1. Build the base URL when input.url is missing.
//     2. Pass award_year as sidecar metadata in next_stage(...) so Stage 2
//        receives it without re-parsing the URL.
//   Both happen in this file (not in parse()), so they remain valid.
//
//   Removed (from v3): parse({ award_year }) calls — replaced with parse().
//
//   Preserved (from v3): navigate() flat at top-level (R1), resolveYear()
//   with award_year_defaulted / award_year_invalid warns, page classification,
//   sidecar metadata propagated to Stage 2 via next_stage().
//
//   Stage 2 is unchanged: its retry-with-backoff around request() is fine
//   because request() is sync in the BrightData Code runtime (see FINDINGS R2).

// ---------- Helpers (pure sync, no async calls — safe under R1) ----------

const CURRENT_YEAR_FALLBACK = new Date().getFullYear();

function resolveYear(raw) {
    // Accept: number (2025), numeric string ("2025"), undefined / null / "".
    // Reject: anything that does not coerce to an integer in [2000, current+1].
    if (raw === undefined || raw === null || raw === '') {
        return { year: CURRENT_YEAR_FALLBACK, warn: 'award_year_defaulted' };
    }
    const n = Number(raw);
    if (!Number.isFinite(n) || !Number.isInteger(n) || n < 2000 || n > CURRENT_YEAR_FALLBACK + 1) {
        // Invalid input — fall back but flag it so the run summary shows the
        // operator passed garbage.
        return { year: CURRENT_YEAR_FALLBACK, warn: 'award_year_invalid' };
    }
    return { year: n, warn: null };
}

function extractAwardCategorySlug(url) {
    // /bestcosme/archive/{year}/category/{slug}/ -> {slug}
    // Anything else -> null.
    const m = /\/bestcosme\/archive\/\d+\/category\/([^/]+)\//.exec(url);
    return m ? m[1] : null;
}

function deriveAwardGroup(url) {
    if (url.includes('/grand/')) return 'grand';
    if (url.includes('/hall/')) return 'hall';
    if (url.includes('/rookie/')) return 'rookie';
    if (url.includes('/category/')) return 'category';
    return null;
}

// ---------- Main ----------

const { year: award_year, warn: year_warn } = resolveYear(input.award_year);
if (year_warn) {
    console.log(`award_year resolved with warning=${year_warn}, using year=${award_year}`);
}

const base_url = `https://www.cosme.net/bestcosme/archive/${award_year}/`;
const url = new URL(input.url || base_url);

// navigate() invoked PLAIN at top-level — see FINDINGS R1. No try/catch, no
// retry, no sleep wrapping. If it fails the worker dies and the external
// orchestration re-queues the input.
navigate(url.href);

// Classify the page.
const is_category_page = location.href.includes('/category/');
const is_grand_page = location.href.includes('/grand/');
const is_hall_page = location.href.includes('/hall/');
const is_rookie_page = location.href.includes('/rookie/');

if (!is_category_page && !is_grand_page && !is_hall_page && !is_rookie_page) {
    // Archive root: emit the 3 awards + the category list.
    // parse() called with NO arguments — see FINDINGS R4. The parser derives
    // award_year from location.href.
    const { category_urls, grand_url, hall_url, rookie_url } = parse();

    if (grand_url) {
        next_stage({
            url: grand_url,
            page_type: 'grand',
            award_year: award_year,
            award_group: 'grand',
            award_category_slug: null,
        });
    }
    if (hall_url) {
        next_stage({
            url: hall_url,
            page_type: 'hall',
            award_year: award_year,
            award_group: 'hall',
            award_category_slug: null,
        });
    }
    if (rookie_url) {
        next_stage({
            url: rookie_url,
            page_type: 'rookie',
            award_year: award_year,
            award_group: 'rookie',
            award_category_slug: null,
        });
    }

    // Optional category filter (substring match, case-insensitive).
    let filtered_urls = category_urls;
    if (input.category) {
        filtered_urls = category_urls.filter(u =>
            u.toLowerCase().includes(input.category.toLowerCase())
        );
    }

    // Optional crawl limit.
    const crawl_limit = input.crawl_limit || filtered_urls.length;
    const urls_to_crawl = filtered_urls.slice(0, crawl_limit);

    console.log(`Found ${category_urls.length} category URLs, crawling ${urls_to_crawl.length} (year=${award_year})`);

    for (const category_url of urls_to_crawl) {
        next_stage({
            url: category_url,
            page_type: 'category',
            award_year: award_year,
            award_group: 'category',
            award_category_slug: extractAwardCategorySlug(category_url),
        });
    }
} else {
    // Award / category page: extract product URLs.
    // parse() called with NO arguments — see FINDINGS R4.
    const { product_urls } = parse();

    const derived_group = deriveAwardGroup(location.href);
    const derived_slug = extractAwardCategorySlug(location.href);

    console.log(`Found ${product_urls.length} product URLs on ${derived_group || 'unknown'} page (slug=${derived_slug})`);

    for (const product_url of product_urls) {
        next_stage({
            url: product_url,
            page_type: 'product',
            award_year: award_year,
            award_group: derived_group,
            award_category_slug: derived_slug,
        });
    }
}
