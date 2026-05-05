// ============================================================
// STAGE 1 — INTERACTION CODE
// Input: { url }
// e.g. { url: "https://www.cosme.net/calendar/" }
// Navega al calendario mensual y lanza next_stage por cada
// día activo que tenga lanzamientos.
// ============================================================

navigate(input.url, { wait_until: 'domcontentloaded' });
wait_visible('table.calendarNaviDay', { timeout: 15000 });

const { activeDays } = parse();

for (const dayInput of activeDays) {
  next_stage(dayInput);
}

