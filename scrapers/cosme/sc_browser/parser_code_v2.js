// cosme v1 — parser code (sc_browser stage)
//
// Logs de diagnóstico agregados 2026-04-22 para debug de E6/E8. Prefijo
// [S1-BROWSER/PARSE] en todos los console.log de este archivo. Sin cambios
// semánticos respecto a la revisión previa.
//
// Stage 1 parser. Reads the current DOM and extracts URL collections for the
// integration code (interaction_code_v1.js) to emit as next_stage() payloads.
// NO product-level field extraction happens here; that is Stage 2's job.
//
// v1 changes vs vendor (E6 fix, documented in results/errors.md 2026-04-22):
//
//   The vendor parser (v4) derives `award_year` exclusively from
//   `location.href` via the regex `/bestcosme\/archive\/(\d+)\//`, with a
//   `new Date().getFullYear()` fallback. That works when the page IS the
//   archive root of a past year (200 OK), but breaks in two ways on the
//   E6 fallback path:
//     (a) The seed URL may have been `/bestcosme/archive/{current_year}/`
//         which 404's; the integration code (v1) then hops to the hub
//         `https://www.cosme.net/bestcosme/`. `location.href` on that hub
//         has NO year segment, so the vendor's regex falls through to
//         `new Date().getFullYear()` — which is the PHYSICAL current year,
//         not the year of the awards cycle the hub is currently displaying
//         (they can diverge in Jan/Feb before a new cycle launches).
//     (b) The vendor selectors `a[href*="/bestcosme/archive/${award_year}/
//         {grand|hall|rookie|category}/"]` are parametrised on the
//         URL-derived year and return 0 matches on the hub when that year
//         was misread.
//
//   v1 fix:
//     1. Try the URL-based regex first (cheap, handles past-year archive
//        pages like /archive/2024/).
//     2. If the URL has no year segment (hub fallback), look for the first
//        anchor `a[href*="/bestcosme/archive/"]` in the DOM and read the
//        year out of ITS href. That is the canonical "current award cycle"
//        year advertised by the hub.
//     3. Only as a last resort fall back to `new Date().getFullYear()` with
//        a `year_source='fallback_current_year'` tag in the debug log.
//     4. Return the resolved `award_year` in the output so the integration
//        can propagate it into `next_stage()` sidecar metadata (already
//        consumed downstream).
//
//   Product-URL extraction on leaf pages (grand/hall/rookie/category) is
//   preserved verbatim from vendor v4 — the DOM structure is identical on
//   those pages, only the discovery root moved.
//
//   parse() is still invoked with NO arguments (R4/R9). `input` is not
//   consulted; everything is derived from the DOM + location.href.
//
// Return shape:
//   - On archive root / hub fallback:
//       { category_urls, grand_url, hall_url, rookie_url, award_year }
//   - On leaf page (grand/hall/rookie/category):
//       { product_urls }

// ---------- Helpers ----------

// Canonicalize a product URL by dropping search/hash so /products/{id}/ with
// and without a ?from=... tracking param dedupe to the same entry.
function canonicalizeProductUrl(href) {
    try {
        const u = new URL(href, location.href);
        return `${u.origin}${u.pathname}`;
    } catch (_) {
        return href;
    }
}

// Derive the award year from, in order:
//   1. location.href path segment (handles past-year archive roots).
//   2. First DOM anchor pointing at /bestcosme/archive/{N}/ (handles the
//      hub fallback /bestcosme/ which has no year in its URL).
//   3. new Date().getFullYear() — absolute last resort; should not happen
//      in practice because the hub is guaranteed to list at least one
//      /archive/{YYYY}/... anchor for the current cycle.
function deriveAwardYear() {
    const from_url = /\/bestcosme\/archive\/(\d+)\//.exec(location.href);
    if (from_url) {
        return { year: parseInt(from_url[1], 10), source: 'url' };
    }
    // Look at any archive anchor in the DOM.
    const anchors = $('a[href*="/bestcosme/archive/"]').toArray();
    for (const el of anchors) {
        const href = $(el).attr('href') || '';
        const m = href.match(/\/bestcosme\/archive\/(\d+)\//);
        if (m) {
            return { year: parseInt(m[1], 10), source: 'dom_anchor' };
        }
    }
    return { year: new Date().getFullYear(), source: 'fallback_current_year' };
}

console.log(`[S1-BROWSER/PARSE] entry location.href=${location.href}`);

const { year: award_year, source: year_source } = deriveAwardYear();
console.log(
    `[S1-BROWSER/PARSE] dom_award_year=${award_year} source=${year_source} ` +
    `(regex URL → DOM scan → fallback)`
);

// Page classification (mirror of integration_code).
const is_category_page = location.href.includes('/category/');
const is_grand_page = location.href.includes('/grand/');
const is_hall_page = location.href.includes('/hall/');
const is_rookie_page = location.href.includes('/rookie/');
const is_leaf_page = is_category_page || is_grand_page || is_hall_page || is_rookie_page;

if (!is_leaf_page) {
    // Archive root or hub fallback — emit grand/hall/rookie + category list.
    //
    // Selector strategy (validated 2026-04-22 via curl on
    //   /bestcosme/archive/2024/   (past-year archive root, 200 OK)
    //   /bestcosme/                (hub, 200 OK, shows current cycle 2025)
    // — both use absolute hrefs of the shape
    //   https://www.cosme.net/bestcosme/archive/{YYYY}/{grand|hall|rookie}/
    //   https://www.cosme.net/bestcosme/archive/{YYYY}/category/{slug}/
    // parametrised on the derived `award_year` to filter out cross-year
    // navigation links that may appear on either page).
    const CATEGORY_SEL = `a[href*="/bestcosme/archive/${award_year}/category/"]`;
    const GRAND_SEL = `a[href*="/bestcosme/archive/${award_year}/grand/"]`;
    const HALL_SEL = `a[href*="/bestcosme/archive/${award_year}/hall/"]`;
    const ROOKIE_SEL = `a[href*="/bestcosme/archive/${award_year}/rookie/"]`;

    const category_urls = $(CATEGORY_SEL)
        .toArray()
        .map(el => $(el).attr('href'))
        .filter(href => href && href.includes('/category/'))
        // Strip in-page hash anchors like /category/blush/#rnk-1 which
        // appear on the hub alongside the canonical /category/blush/.
        .map(href => {
            try {
                const u = new URL(href, location.href);
                return `${u.origin}${u.pathname}`;
            } catch (_) {
                return href;
            }
        })
        // Only keep real category leaves (trailing /category/{slug}/ shape).
        .filter(u => /\/bestcosme\/archive\/\d+\/category\/[^/]+\/$/.test(u))
        // Dedupe preserving order.
        .filter((u, index, self) => self.indexOf(u) === index);

    const grand_anchors_count = $(GRAND_SEL).length;
    const hall_anchors_count = $(HALL_SEL).length;
    const rookie_anchors_count = $(ROOKIE_SEL).length;
    const category_anchors_count = $(CATEGORY_SEL).length;

    const grand_href = $(GRAND_SEL).first().attr('href');
    const hall_href = $(HALL_SEL).first().attr('href');
    const rookie_href = $(ROOKIE_SEL).first().attr('href');

    console.log(
        `[S1-BROWSER/PARSE] archive-root: grand=${grand_anchors_count} ` +
        `hall=${hall_anchors_count} rookie=${rookie_anchors_count} ` +
        `categories=${category_anchors_count} (dedup categories=${category_urls.length})`
    );

    return {
        category_urls,
        grand_url: grand_href ? new URL(grand_href, location.href).href : null,
        hall_url: hall_href ? new URL(hall_href, location.href).href : null,
        rookie_url: rookie_href ? new URL(rookie_href, location.href).href : null,
        award_year,
    };
} else {
    // Award / category leaf page — extract product URLs from ranked sections.
    //
    // Unchanged from vendor v4. Validated DOM structure on
    //   /bestcosme/archive/2025/grand/
    //   /bestcosme/archive/2025/category/serum/
    // both use <section id="rnk-{N}"> blocks with an `.award-product-name`
    // inside an `<a href="/products/{id}/">` wrapper.
    const product_sections = $('section[id^="rnk-"]').toArray();

    const product_urls_raw = product_sections
        .map(section => {
            const product_link = $(section).find('.award-product-name').closest('a').attr('href');
            return product_link ? new URL(product_link, location.href).href : null;
        })
        .filter(u => u !== null)
        .map(canonicalizeProductUrl);

    // Dedupe on canonical URL.
    const unique_product_urls = [...new Set(product_urls_raw)];

    console.log(
        `[S1-BROWSER/PARSE] leaf: sections[id^="rnk-"]=${product_sections.length} ` +
        `product_links_raw=${product_urls_raw.length} unique=${unique_product_urls.length}`
    );

    return {
        product_urls: unique_product_urls,
    };
}
