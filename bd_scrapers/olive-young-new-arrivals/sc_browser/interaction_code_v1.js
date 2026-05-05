// ============================================================
// STAGE 1 — INTERACTION CODE
// Navega al listado New Arrivals y lanza next_stage
// por cada producto hacia Stage 2.
// ============================================================

const base_url = input.url || 'https://global.oliveyoung.com/display/page/new-arrivals';

navigate(base_url, {
  wait_until: 'domcontentloaded'
});

wait_visible('.unit-box', { timeout: 30000 });

const { products } = parse();

for (const product of products) {
  next_stage(product);
}