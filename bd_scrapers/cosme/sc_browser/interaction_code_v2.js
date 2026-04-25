// Input
// url: https://www.cosme.net/bestcosme/archive/2025/grand/
// category: "skincare"  // optional substring filter on category URLs (e.g. "skincare" to only crawl categories with "skincare" in the URL)
// crawl_limit: 5  // optional limit on number of category URLs to crawl (applies after category filter, if any)



// cosme v1 — integration code (sc_browser stage)
//
// Logs de diagnóstico agregados 2026-04-22 para debug de E6/E8. Prefijo
// [S1-BROWSER/INT] en todos los console.log de este archivo. Sin cambios
// semánticos respecto a la revisión previa.
//
// Stage 1 of the 2-stage pipeline:
//   Stage 1 (this file) = DISCOVERY — headless Chrome navigates the bestcosme
//     hub / archive page, extracts grand/hall/rookie + category URLs and
//     emits one next_stage() per sub-page. Each sub-page is then crawled
//     (by a separate Stage 1 invocation that lands in a category/grand/hall/
//     rookie branch) to harvest product URLs, which in turn trigger Stage 2.
//   Stage 2 (sc_code/v1) = FETCH — plain HTTP on the product URL, Shift-JIS
//     decode, DOM parse, emit product record. (Unchanged from vendor.)
//
// v1 changes vs vendor (E6 fix, documented in results/errors.md 2026-04-22):
//
//   The vendor (v4) integration assumes `https://www.cosme.net/bestcosme/
//   archive/{year}/` is a valid discovery page. In practice, for the CURRENT
//   and FUTURE year that URL returns a server-side 404 (title
//   `ページが見つかりません 404 Not Found`), so the vendor parser finds zero
//   category/grand/hall/rookie anchors, the integration emits zero
//   next_stage(), and the collector ends with `{"status":"empty"}` ~60s
//   after trigger. Only past years (2000..most-recently-closed) render real
//   archive pages there.
//
//   The canonical discovery page for the CURRENT year is the hub
//   `https://www.cosme.net/bestcosme/` (HTTP 200, title `@cosmeベストコスメ
//   アワード{YYYY}`), which lists the same sub-paths
//   (`/bestcosme/archive/{YYYY}/grand/`, `/hall/`, `/rookie/`, +63 `/category/
//   {slug}/`, +6 `/category-group/{slug}/`).
//
//   v1 fix: after the initial navigate() to the archive-root URL the
//   integration code detects a 404 (title contains `ページが見つかりません`)
//   AND/OR the complete absence of `/bestcosme/archive/` anchors on the
//   page, and in that case fires a SECOND navigate() to the hub. That
//   second navigate() is still a plain top-level call (R1 / R8 respected:
//   no wrapping function, no try/catch around navigate). The rest of the
//   pipeline — parse() with no args, sidecar metadata in next_stage(),
//   classification of grand/hall/rookie/category branches — is preserved
//   verbatim from vendor.
//
//   The parser (parser_code_v1.js) is updated in parallel to derive
//   `award_year` from the DOM (first `a[href*="/bestcosme/archive/{YYYY}/
//   grand/"]`) when the URL lies (e.g. we seeded with `/archive/2025/` and
//   landed on a 404, then hopped to `/bestcosme/`). See parser_code_v1.js
//   header for details.
//
// Preserved from vendor (all mandatory, R1/R4/R8/R9 from brightdata-errors.md):
//   - `navigate()` plain at top-level, no retry wrapper.
//   - `parse()` called with NO arguments (R9 / R4: runtime rejects undeclared
//     fields).
//   - `award_year` / warn resolution via `resolveYear()` for sidecar metadata.
//   - Page classification into grand / hall / rookie / category branches by
//     substring on `location.href`.
//   - `next_stage({url, page_type, award_year, award_group,
//     award_category_slug})` — sidecar does NOT go through parse().

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
        return { year: CURRENT_YEAR_FALLBACK, warn: 'award_year_invalid' };
    }
    return { year: n, warn: null };
}

function extractAwardCategorySlug(url) {
    // /bestcosme/archive/{year}/category/{slug}/ -> {slug}
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
    console.log(`[S1-BROWSER/INT] award_year resolved with warning=${year_warn}, using year=${award_year}`);
}

const base_url = `https://www.cosme.net/bestcosme/archive/${award_year}/`;
const seed_url = input.url || base_url;

console.log(
    `[S1-BROWSER/INT] seed url=${seed_url} year=${award_year} ` +
    `crawl_limit=${input.crawl_limit ?? 'null'} category=${input.category ?? 'null'}`
);

// First navigate — honours the seed URL the middleware / caller provided
// (spec §10: middleware sends the archive-root URL built from award_year).
navigate(seed_url);

// Classify the page by the URL the runtime actually ended up on.
let current_href = location.href;
let is_category_page = current_href.includes('/category/');
let is_grand_page = current_href.includes('/grand/');
let is_hall_page = current_href.includes('/hall/');
let is_rookie_page = current_href.includes('/rookie/');
let is_leaf_page = is_category_page || is_grand_page || is_hall_page || is_rookie_page;

console.log(
    `[S1-BROWSER/INT] after navigate location.href=${current_href} ` +
    `branch=${is_category_page ? 'category' : is_grand_page ? 'grand' : is_hall_page ? 'hall' : is_rookie_page ? 'rookie' : 'archive-root'}`
);

// E6 detection (2026-04-22): for the CURRENT/FUTURE year the archive-root
// URL is a 404 page. Probe the DOM via the DSL primitive `el_exists()`:
// a real archive root (or the hub) always has at least one anchor pointing
// at `/bestcosme/archive/{YYYY}/grand/`. A 404 body has zero. If the probe
// says "no grand anchor", fall back to the hub `https://www.cosme.net/
// bestcosme/` which always lists the current award cycle's sub-pages.
//
// Only applies on the "archive root" branch (leaf pages are never re-hopped).
let fell_back_to_hub = false;
if (!is_leaf_page) {
    // Combined selector covers all years — if literally zero of the award-
    // linking anchors are present we are on a 404 (or some other unexpected
    // page). Multi-selector = 1 trip (R2 from scraper-implementation SKILL).
    const has_award_anchors = el_exists(
        'a[href*="/bestcosme/archive/"][href*="/grand/"], ' +
        'a[href*="/bestcosme/archive/"][href*="/hall/"], ' +
        'a[href*="/bestcosme/archive/"][href*="/rookie/"]'
    );

    if (!has_award_anchors) {
        console.log(
            `[S1-BROWSER/INT] E6 fallback: probe failed on ${current_href} ` +
            `(no award anchors, likely 404 for current/future year). Navigating to /bestcosme/.`
        );
        // Second navigate() — still a plain top-level call (R1/R8). No retry
        // wrapper, no try/catch, no await. If this also fails the worker
        // dies and external orchestration re-queues.
        navigate('https://www.cosme.net/bestcosme/');
        fell_back_to_hub = true;

        // Re-classify. The hub is itself an "archive root"-style page (it
        // lists grand/hall/rookie + categories); branches stay the same.
        current_href = location.href;
        is_category_page = current_href.includes('/category/');
        is_grand_page = current_href.includes('/grand/');
        is_hall_page = current_href.includes('/hall/');
        is_rookie_page = current_href.includes('/rookie/');
        is_leaf_page = is_category_page || is_grand_page || is_hall_page || is_rookie_page;

        console.log(
            `[S1-BROWSER/INT] after fallback navigate location.href=${current_href} ` +
            `branch=${is_category_page ? 'category' : is_grand_page ? 'grand' : is_hall_page ? 'hall' : is_rookie_page ? 'rookie' : 'archive-root'}`
        );
    }
}

if (!is_leaf_page) {
    // Archive root (or hub fallback): emit grand/hall/rookie + category URLs.
    // parse() called with NO arguments (R4/R9). The parser derives the
    // actual award_year from the DOM (first archive anchor), so a seed
    // mismatch (we seeded with /archive/2025/ but landed on /bestcosme/ which
    // canonicalises to archive/{most_recent_closed_or_current_year}/) is
    // resolved correctly.
    const parsed = parse();
    const category_urls = parsed.category_urls || [];
    const grand_url = parsed.grand_url;
    const hall_url = parsed.hall_url;
    const rookie_url = parsed.rookie_url;
    const dom_award_year = parsed.award_year || award_year;

    let emitted_grand = 0;
    let emitted_hall = 0;
    let emitted_rookie = 0;
    let emitted_category = 0;

    if (grand_url) {
        next_stage({
            url: grand_url,
            page_type: 'grand',
            award_year: dom_award_year,
            award_group: 'grand',
            award_category_slug: null,
        });
        emitted_grand++;
    }
    if (hall_url) {
        next_stage({
            url: hall_url,
            page_type: 'hall',
            award_year: dom_award_year,
            award_group: 'hall',
            award_category_slug: null,
        });
        emitted_hall++;
    }
    if (rookie_url) {
        next_stage({
            url: rookie_url,
            page_type: 'rookie',
            award_year: dom_award_year,
            award_group: 'rookie',
            award_category_slug: null,
        });
        emitted_rookie++;
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

    console.log(
        `[S1-BROWSER/INT] discovery: found ${category_urls.length} category URLs, ` +
        `crawling ${urls_to_crawl.length} (dom_award_year=${dom_award_year}, ` +
        `fell_back_to_hub=${fell_back_to_hub})`
    );

    for (const category_url of urls_to_crawl) {
        next_stage({
            url: category_url,
            page_type: 'category',
            award_year: dom_award_year,
            award_group: 'category',
            award_category_slug: extractAwardCategorySlug(category_url),
        });
        emitted_category++;
    }

    const total_emitted = emitted_grand + emitted_hall + emitted_rookie + emitted_category;
    console.log(
        `[S1-BROWSER/INT] emitting next_stage: grand=${emitted_grand} hall=${emitted_hall} ` +
        `rookie=${emitted_rookie} category=${emitted_category} (crawl_limit applied)`
    );
    console.log(`[S1-BROWSER/INT] done — emitted ${total_emitted} next_stage`);
} else {
    // Award / category leaf page: extract product URLs.
    // parse() called with NO arguments (R4/R9).
    const parsed = parse();
    const product_urls = parsed.product_urls || [];

    const derived_group = deriveAwardGroup(current_href);
    const derived_slug = extractAwardCategorySlug(current_href);

    console.log(
        `[S1-BROWSER/INT] leaf: found ${product_urls.length} product URLs on ` +
        `${derived_group || 'unknown'} page (slug=${derived_slug})`
    );

    let emitted_product = 0;
    for (const product_url of product_urls) {
        next_stage({
            url: product_url,
            page_type: 'product',
            award_year: award_year,
            award_group: derived_group,
            award_category_slug: derived_slug,
        });
        emitted_product++;
    }
    console.log(`[S1-BROWSER/INT] done — emitted ${emitted_product} next_stage`);
}
