// ============================================================
// STAGE 2 — INTERACTION CODE
// Input: { url, day, year, month }
// e.g. { url: "https://www.cosme.net/calendar/index/year/2026/month/05/day/01",
//         day: 1, year: 2026, month: 5 }
// Navega al día específico, parsea todos los productos
// y hace collect con el array completo.
// ============================================================

navigate(input.url, { wait_until: 'domcontentloaded' });

try {
  wait_visible('div.newProductList', { timeout: 10000 });
} catch (e) {
  // Día sin productos — terminar silenciosamente
}

const { products } = parse();

collect(products);

// console.log(products[0])