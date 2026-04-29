// ============================================================================
// STAGE 1 — INTERACTION CODE (Browser): Descubrir productos del ranking
// ============================================================================
// page = 0 → primera página (sin /page/)
// page = 1 → /page/1 (segunda página)
// page = 9 → /page/9 (décima página)
// ============================================================================

const base_url = (input.url || 'https://www.cosme.net/ranking/products')
    .replace(/\/page\/\d+\/?$/, '').replace(/\/$/, '');
const page = input.page || 0;

// ---------- Build URL ----------

const target_url = page === 0
    ? base_url
    : new URL('/ranking/products/page/' + page, base_url).href;

// ---------- Navigate ----------

navigate(target_url, { timeout: 30000 });

try {
    wait('#list-item dl', { timeout: 15000 });
} catch (e) {
    if (el_exists('.error-404, img[src*="error_pages"]')) {
        dead_page('Ranking page not found');
    }
    blocked('Ranking content did not load');
}

// ---------- Parse ----------

const data = parse();
const items = data.items || [];
const total_pages = data.total_pages || 1;

// ---------- Dispatch Stage 2 for each product ----------

for (const item of items) {
    next_stage(item);
}

// ---------- Pagination R3 from page 0 ----------

if (page === 0 && total_pages > 1) {
    for (let p = 1; p < total_pages; p++) {
        rerun_stage({
            url: base_url,
            page: p,
        });
    }
}