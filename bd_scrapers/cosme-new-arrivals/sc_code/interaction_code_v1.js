// // ============================================================================
// // cosme-new-arrivals — sc_code interaction_code_v1.js
// // ============================================================================
// // Estrategia de crawl v1 (spec §6):
// //   Stage 1 (sin input.day): Carga página del mes → extrae links de días activos
// //             → next_stage por cada día.
// //   Stage 2 (con input.day): Carga página del día → parsea productos → collect().
// //
// // Worker: Code worker (HTTP puro). No usa wait/click/tag_*.
// // Proxy: residencial JP (configurado en el dashboard de BrightData).
// // Encoding: Shift_JIS → parser decodifica con iconv-lite + load_html().
// // ============================================================================

// const target_url = input.url || 'https://www.cosme.net/calendar/';

// // ------------------------------------------------------------------
// // STAGE 2: procesar un día concreto
// // ------------------------------------------------------------------
// if (input.day) {
//   const day_url = input.url;

//   navigate(day_url, {
//     timeout: 30000,
//     allow_status: [404, 410],
//   });

//   const sc = status_code();

//   // 404 / 410 → no hay lanzamientos ese día, skip silencioso (spec §7)
//   if (sc === 404 || sc === 410) {
//     dead_page('no-products-day-' + input.day);
//   }

//   // Cualquier otro error HTTP no esperado → blocked para retry
//   if (sc >= 400) {
//     blocked('unexpected-status-' + sc);
//   }

//   const result = parse();

//   // result puede ser null cuando el parser detecta bloqueo y llama dead_page
//   // o cuando div.newProductList no existe (parser retorna {products: []})
//   if (result && result.products && result.products.length > 0) {
//     for (const product of result.products) {
//       collect(product);
//     }
//   }

//   // Si result.blocked === true el parser ya emitió dead_page/blocked.
//   // No hacemos nada más aquí.
//   return;
// }

// // ------------------------------------------------------------------
// // STAGE 1: descubrir días activos del mes
// // ------------------------------------------------------------------

// navigate(target_url, { timeout: 30000, allow_status: [404] });

// const sc1 = status_code();

// if (sc1 === 404) {
//   dead_page('month-page-not-found');
// }

// if (sc1 >= 400) {
//   blocked('month-page-error-' + sc1);
// }

// const month_data = parse();

// if (!month_data || !month_data.day_urls || month_data.day_urls.length === 0) {
//   dead_page('no-active-days-found');
// }

// // Dispatch Stage 2 por cada día activo
// for (const day_info of month_data.day_urls) {
//   next_stage({
//     url: day_info.url,
//     year: input.year || month_data.year,
//     month: input.month || month_data.month,
//     day: day_info.day,
//   });
// }

navigate(input.url);


// Collect the parsed data
collect(parse());
