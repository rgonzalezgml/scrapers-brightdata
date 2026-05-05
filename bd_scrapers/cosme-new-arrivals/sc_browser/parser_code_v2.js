// ============================================================
// STAGE 1 — PARSER CODE
// Extrae los días activos del calendario (los que tienen link).
// Retorna { activeDays: [...] }
// ============================================================

const BASE_URL = 'https://www.cosme.net';

// Extraer año/mes del link "current" en el nav del calendario
// <span class="current"><a href=".../year/2026/month/05">



let year, month;

const urlMatch = input.url && input.url.match(/year\/(\d{4})\/month\/(\d{2})/);

// Start Day
if (input.start_at && /^\d{4}-\d{2}-\d{2}$/.test(input.start_at)) {
  // Extraer año y mes directamente del input start_at
  const parts = input.start_at.split('-');
  year = parseInt(parts[0], 10);
  month = parseInt(parts[1], 10);
} else if (urlMatch) {
  // Extraer año y mes de la URL si tiene formato /year/YYYY/month/MM
  year = parseInt(urlMatch[1], 10);
  month = parseInt(urlMatch[2], 10);
} else {
  // Fallback: extraer del nav del calendario en el HTML
  const currentLink = $('span.current a').attr('href') || '';
  console.log(`Current link: ${currentLink}`);
  const currentMatch = currentLink.match(/year\/(\d{4})\/month\/(\d{2})/);
  if (currentMatch) {
    year = parseInt(currentMatch[1], 10);
    month = parseInt(currentMatch[2], 10);
  } else {
    const now = new Date();
    year = now.getFullYear();
    month = now.getMonth() + 1;
  }
}


const activeDays = [];

$('table.calendarNaviDay th').each((i, th) => {
  const link = $(th).find('a[href]').first();
  if (!link.length) return; // día sin lanzamientos

  const href = link.attr('href');
  const dayMatch = href.match(/\/day\/(\d+)/);
  if (!dayMatch) return;

  const day = parseInt(dayMatch[1], 10);
  const dayUrl = href.startsWith('http') ? href : BASE_URL + href;

  activeDays.push({ url: dayUrl, day, year, month });
});

return { activeDays };

