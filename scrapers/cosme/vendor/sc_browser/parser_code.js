// cosme v4 — parser code (sc_browser stage)
//
// Stage 1 parser. Reads the current DOM and extracts URL collections for the
// integration code to emit as next_stage() payloads. NO product-level field
// extraction happens here; that is Stage 2's job.
//
// v4 changes vs v3:
//   v3 read award_year from input.award_year, which forced the integration
//   code to call parse({ award_year }). The BrightData runtime validates the
//   parse() input against an internal schema and rejected the call with:
//     Crawler error: parse validation error: "[0].award_year" is not allowed
//   See FINDINGS.md rule R4.
//
//   v4 fix: derive award_year from location.href using the regex
//     /bestcosme\/archive\/(\d+)\//
//   Fallback to new Date().getFullYear() if the URL does not match (e.g. an
//   archive root without the year segment, which should not normally happen
//   with valid input). The derived year is logged for traceability.
//
//   parse() is now invoked with NO arguments. input is no longer consulted.
//
// Return shape (unchanged vs v3):
//   - On archive root: { category_urls, grand_url, hall_url, rookie_url }
//   - On award/category page: { product_urls }

// Derive award_year from location.href instead of relying on parse() input
// (which is schema-validated and rejects undeclared fields — see FINDINGS R4).
function deriveAwardYearFromUrl(href) {
    const m = /\/bestcosme\/archive\/(\d+)\//.exec(href);
    if (m) {
        return { year: parseInt(m[1], 10), source: 'url' };
    }
    return { year: new Date().getFullYear(), source: 'fallback_current_year' };
}

const { year: award_year, source: year_source } = deriveAwardYearFromUrl(location.href);
console.log(`parser_code: derived award_year=${award_year} from ${year_source} (location.href=${location.href})`);

// Canonicalize a product URL by dropping search/hash so /products/{id}/ with
// and without a ?from=... tracking param dedupe to the same entry.
function canonicalizeProductUrl(href) {
    try {
        const u = new URL(href, location.href);
        // Keep pathname only (drop ?query and #hash) — product detail ids live
        // in the path, never in query.
        return `${u.origin}${u.pathname}`;
    } catch (_) {
        return href;
    }
}

// Page classification (mirror of integration_code).
const is_category_page = location.href.includes('/category/');
const is_grand_page = location.href.includes('/grand/');
const is_hall_page = location.href.includes('/hall/');
const is_rookie_page = location.href.includes('/rookie/');
const is_main_page = !is_category_page && !is_grand_page && !is_hall_page && !is_rookie_page;

if (is_main_page) {
    // Archive root — emit the 3 top-level award URLs + the list of categories.
    const CATEGORY_SEL = `a[href*="/bestcosme/archive/${award_year}/category/"]`;
    const GRAND_SEL = `a[href*="/bestcosme/archive/${award_year}/grand/"]`;
    const HALL_SEL = `a[href*="/bestcosme/archive/${award_year}/hall/"]`;
    const ROOKIE_SEL = `a[href*="/bestcosme/archive/${award_year}/rookie/"]`;

    const category_urls = $(CATEGORY_SEL)
        .toArray()
        .map(el => $(el).attr('href'))
        .filter(href => href && href.includes('/category/'))
        .map(href => new URL(href, location.href).href)
        .filter((u, index, self) => self.indexOf(u) === index); // dedupe

    const grand_url = $(GRAND_SEL).first().attr('href');
    const hall_url = $(HALL_SEL).first().attr('href');
    const rookie_url = $(ROOKIE_SEL).first().attr('href');

    return {
        category_urls,
        grand_url: grand_url ? new URL(grand_url, location.href).href : null,
        hall_url: hall_url ? new URL(hall_url, location.href).href : null,
        rookie_url: rookie_url ? new URL(rookie_url, location.href).href : null,
    };
} else {
    // Award / category page — extract product URLs from the ranked sections.
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

    return {
        product_urls: unique_product_urls,
    };
}
