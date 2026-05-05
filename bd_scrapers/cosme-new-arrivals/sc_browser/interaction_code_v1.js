// ============================================================================
// cosme-new-arrivals — sc_browser interaction_code_v1.js
// ============================================================================
// Browser worker (Scraping Browser / headless Chromium).
// Mismo flujo que sc_code pero usando wait() para esperar carga de DOM.
//
// Estrategia (spec §6):
//   Stage 1 (sin input.day): Navegar al mes → wait selector → parse() → next_stage por día.
//   Stage 2 (con input.day): Navegar al día → wait → parse() → collect por producto.
//
// NOTA: cosme.net es HTML estático Shift_JIS — preferir sc_code worker (más
// barato y rápido). Este archivo existe para fallback o tests comparativos.
// ============================================================================

const target_url = input.url || 'https://www.cosme.net/calendar/';

// ------------------------------------------------------------------
// STAGE 2: procesar un día concreto
// ------------------------------------------------------------------
if (input.day) {
  navigate(input.url, {
    timeout: 30000,
    allow_status: [404, 410],
  });

  const sc = status_code();

  if (sc === 404 || sc === 410) {
    dead_page('no-products-day-' + input.day);
  }

  if (sc >= 400) {
    blocked('unexpected-status-' + sc);
  }

  // Esperar el contenedor principal o el indicador de página vacía (R1 pattern)
  wait('div.newProductList, div.inr-calendar', { timeout: 30000 });

  if (!el_exists('div.newProductList')) {
    // Página cargó pero no tiene productos → retornar sin collect
    return;
  }

  const result = parse();

  if (result && result.products && result.products.length > 0) {
    for (const product of result.products) {
      collect(product);
    }
  }

  return;
}

// ------------------------------------------------------------------
// STAGE 1: descubrir días activos del mes
// ------------------------------------------------------------------

navigate(target_url, { timeout: 30000, allow_status: [404] });

const sc1 = status_code();

if (sc1 === 404) {
  dead_page('month-page-not-found');
}

if (sc1 >= 400) {
  blocked('month-page-error-' + sc1);
}

// Esperar la tabla de navegación de días (R1 pattern: multi-selector)
wait('table.calendarNaviDay, div.inr-calendar', { timeout: 30000 });

const month_data = parse();

if (!month_data || !month_data.day_urls || month_data.day_urls.length === 0) {
  dead_page('no-active-days-found');
}

for (const day_info of month_data.day_urls) {
  next_stage({
    url: day_info.url,
    year: input.year || month_data.year,
    month: input.month || month_data.month,
    day: day_info.day,
  });
}
