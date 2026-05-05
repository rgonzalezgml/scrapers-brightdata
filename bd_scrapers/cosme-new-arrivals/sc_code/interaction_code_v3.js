// ============================================================
// STAGE 2 — INTERACTION CODE v3
// Cambio vs v2: en lugar de collect(products) aplica filtro por fecha.
// Productos con release_date >= hoy → next_stage(campos_base) → Stage 3.
// Productos con release_date < hoy  → collect(producto_base) directo.
// Los productos futuros se ordenan de más próximos a más lejanos
// antes de emitir next_stage, para que el cap de 500 de Stage 3
// priorice los lanzamientos más inmediatos (spec §6).
// Input: { url, day, year, month }
// ============================================================

navigate(input.url, { wait_until: 'domcontentloaded' });

try {
  wait_visible('div.newProductList', { timeout: 10000 });
} catch (e) {
  // Día sin productos — terminar silenciosamente
}

const { products } = parse();

for (const p of products) {
  next_stage({
    url: p.url,
    product_id: p.product_id,
    product_name: p.product_name,
    // brand_id: p.brand_id,
    brand_name: p.brand_name,
    brand_url: p.brand_url,
    release_date: p.release_date,
    shop_url: p.shop_url,
    scraped_at: p.scraped_at,
  });

}