// ============================================================================
// cosme-new-arrivals — sc_browser interaction_code_v2.js
// ============================================================================
// Browser worker (Scraping Browser / headless Chromium).
//
// Cambios vs v1 — arregla E1 (mismo fix que sc_code/interaction_code_v2.js,
// adaptado para Browser worker):
//   • Stage 1: `const target_url = input.url || ...` (fallback explícito igual
//     que en sc_code v2, aunque v1 ya lo tenía — lo preservamos para simetría).
//   • Stage 2: navigate usa `input.url` directamente (consistente con sc_code v2).
//   • Mantiene todos los wait() y el_exists() de v1 propios del Browser worker:
//       – wait('table.calendarNaviDay, div.inr-calendar') antes del parse() de Stage 1.
//       – wait('div.newProductList, div.inr-calendar') antes del parse() de Stage 2.
//       – if (!el_exists('div.newProductList')) return; guard en Stage 2.
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

// year/month los extrae el parser de los hrefs de los días (siempre tienen /year/YYYY/month/MM/day/DD)
for (const day_info of month_data.day_urls) {
  next_stage({
    url:   day_info.url,
    year:  input.year  || month_data.year,
    month: input.month || month_data.month,
    day:   day_info.day,
  });
}
