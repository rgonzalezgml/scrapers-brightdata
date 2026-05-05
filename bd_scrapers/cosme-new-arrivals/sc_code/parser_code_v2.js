// ============================================================================
// cosme-new-arrivals — sc_code parser_code_v2.js
// ============================================================================
// Cambios vs v1 — arregla E1:
//
//   STAGE 1:
//   • Extrae year/month de location.href (URL real tras redirect) antes de
//     intentar input.url. Esto soluciona el caso en que input.url es
//     "https://www.cosme.net/calendar/" y no contiene /year/YYYY/month/MM.
//   • Fallback adicional: si location.href tampoco tiene year/month, los
//     extrae del primer href de día encontrado en la tabla (siempre tiene
//     /year/YYYY/month/MM/day/DD).
//   • El patrón .map(fn).get() ya era correcto (R12). Sin cambios en selectores.
//
//   STAGE 2:
//   • Sin cambios. year/month/day se extraen del input (pasado desde Stage 1
//     con valores correctos) o como fallback del path de input.url, que en
//     Stage 2 siempre es la URL del día con /year/YYYY/month/MM/day/DD.
//
// Output schema (spec §2):
// {"new_product":["product_id","product_url","product_name","brand_id",
//                 "brand_name","brand_url","release_date","shop_url","scraped_at"]}
// ============================================================================

const BASE = 'https://www.cosme.net';
const scraped_at = new Date().toISOString();

// ============================================================================
// Helpers
// ============================================================================

// Extrae un ID numérico de un path de cosme.net
// extractId('/products/10260179/', 'products') → '10260179'
function extractId(href, segment) {
  if (!href) return null;
  const m = href.match(new RegExp('\\/' + segment + '\\/(\\d+)\\/'));
  return m ? m[1] : null;
}

// Asegura URL absoluta: si href empieza con '/' lo prefija con BASE
function absUrl(href) {
  if (!href) return null;
  if (href.startsWith('http://') || href.startsWith('https://')) return href;
  if (href.startsWith('/')) return BASE + href;
  return null;
}

// Parsea el texto del h3.subTitle (ej. "5月1日 (金)") → {month, day} enteros
function parseTitleDate(text) {
  if (!text) return null;
  const m = text.match(/(\d+)月(\d+)日/);
  if (!m) return null;
  return { month: parseInt(m[1], 10), day: parseInt(m[2], 10) };
}

// Construye YYYY-MM-DD con zero-padding
function buildDate(year, month, day) {
  const mm = String(month).padStart(2, '0');
  const dd = String(day).padStart(2, '0');
  return String(year) + '-' + mm + '-' + dd;
}

// ============================================================================
// STAGE 1: extraer links de días activos del mes
// ============================================================================
if (!input.day) {
  // Fix E1: priorizar location.href (URL real tras redirect) para extraer
  // year/month. En Code worker, `location` es un objeto {href} disponible
  // como global en el parser y refleja la URL final después de cualquier 302.
  // Si location.href no tiene year/month (caso inesperado), intentar input.url.
  const loc_href = (typeof location !== 'undefined' && location && location.href)
    ? location.href
    : null;

  const loc_match   = loc_href   ? loc_href.match(/\/year\/(\d{4})\/month\/(\d{1,2})/)   : null;
  const input_match = (input.url || '').match(/\/year\/(\d{4})\/month\/(\d{1,2})/);

  let year  = input.year  || null;
  let month = input.month || null;

  if (!year && loc_match)   year  = parseInt(loc_match[1],   10);
  if (!month && loc_match)  month = parseInt(loc_match[2],   10);
  if (!year && input_match) year  = parseInt(input_match[1], 10);
  if (!month && input_match) month = parseInt(input_match[2], 10);

  const day_urls = [];

  // Días activos están en table.calendarNaviDay → celdas th con <a>
  // Los días sin lanzamientos tienen clase p.dayNN sin <a> o con clase .off.
  $('table.calendarNaviDay th').map(function (_, el) {
    const $th = $(el);
    const $a  = $th.find('p a').first();
    const href = $a.attr('href');
    if (!href) return; // día sin link = sin lanzamientos

    // Extraer el número de día del href
    const day_match = href.match(/\/day\/(\d{1,2})\/?$/);
    if (!day_match) return;

    const day_num = parseInt(day_match[1], 10);
    const day_url = absUrl(href);

    // Fallback E1: si todavía no tenemos year/month, extraerlos del primer
    // href de día encontrado (siempre tiene /year/YYYY/month/MM/day/DD).
    if ((!year || !month) && href) {
      const fb = href.match(/\/year\/(\d{4})\/month\/(\d{1,2})/);
      if (fb) {
        if (!year)  year  = parseInt(fb[1], 10);
        if (!month) month = parseInt(fb[2], 10);
      }
    }

    day_urls.push({ url: day_url, day: day_num });
  }).get(); // R12: .map().get() portable en ambos workers

  return { day_urls, year, month };
}

// ============================================================================
// STAGE 2: parsear productos de una página de día
// ============================================================================

// En Stage 2 input.url siempre es la URL del día (/year/YYYY/month/MM/day/DD),
// por lo que el regex siempre matchea. Además, interaction v2 ya pasa year/month
// correctos en el input. Sin cambios de lógica vs v1.
const url_match2 = (input.url || '').match(/\/year\/(\d{4})\/month\/(\d{1,2})\/day\/(\d{1,2})/);
const year  = input.year  || (url_match2 ? parseInt(url_match2[1], 10) : null);
const month = input.month || (url_match2 ? parseInt(url_match2[2], 10) : null);
const day   = input.day   || (url_match2 ? parseInt(url_match2[3], 10) : null);

const products = [];
const scraper_flags = [];

// Verificación de encoding: si no hay ningún carácter CJK y el body existe,
// puede haber un problema de Shift_JIS. Emitimos el flag diagnóstico.
const sample_text = $('body').text_sane();
const has_cjk = /[　-鿿豈-﫿]/.test(sample_text);
if (sample_text.length > 0 && !has_cjk) {
  scraper_flags.push('shift_jis_fallback');
}

// Verificar que existe la sección de productos (spec §7)
if ($('div.newProductList').length === 0) {
  // No hay lanzamientos este día → retornar lista vacía sin error
  return { products: [] };
}

// Extraer fecha del h3.subTitle para validación de consistencia (spec §5)
const subtitle_text = $('div.newProductList h3.subTitle').first().text_sane();
const title_date = parseTitleDate(subtitle_text);

if (title_date && year && month) {
  if (title_date.month !== month || (day && title_date.day !== day)) {
    scraper_flags.push('date_mismatch');
  }
}

// Construir la fecha de lanzamiento usando el path URL (prioritario según spec §5)
const release_date = (year && month && day) ? buildDate(year, month, day) : null;

// Recorrer el DOM de div.newProductList
// Estructura: h4.brandName → ul.productInformation → li* → p.productName → span.name → a*
let current_brand_name = null;
let current_brand_id   = null;
let current_brand_url  = null;

$('div.newProductList').children().map(function (_, el) {
  const $el = $(el);
  const tag = el.tagName ? el.tagName.toLowerCase() : '';

  if (tag === 'h4' && $el.hasClass('brandName')) {
    const $brand_a  = $el.find('a').first();
    const brand_href = $brand_a.attr('href') || null;

    if (brand_href) {
      current_brand_name = $brand_a.text_sane();
      current_brand_id   = extractId(brand_href, 'brands');
      current_brand_url  = absUrl(brand_href);
    } else {
      // h4.brandName sin <a> (spec §8: brand_no_link)
      current_brand_name = $el.text_sane();
      current_brand_id   = null;
      current_brand_url  = null;
      if (scraper_flags.indexOf('brand_no_link') === -1) {
        scraper_flags.push('brand_no_link');
      }
    }
    return;
  }

  if (tag === 'ul' && $el.hasClass('productInformation')) {
    $el.find('li').map(function (_, li) {
      const $li   = $(li);
      const $span = $li.find('span.name');

      // Primer <a> que no sea el botón de compra = link al producto en cosme.net
      const $prod_a   = $span.find('a').not('.btn-cmn-buy').first();
      const prod_href = $prod_a.attr('href') || null;

      // product_id → skip si no se puede extraer (spec §7)
      const product_id = extractId(prod_href, 'products');
      if (!product_id) return;

      // product_name → skip si vacío (spec §7)
      const product_name = $prod_a.text_sane();
      if (!product_name) {
        if (scraper_flags.indexOf('product_name_missing') === -1) {
          scraper_flags.push('product_name_missing');
        }
        return;
      }

      const product_url = BASE + '/products/' + product_id + '/';

      // shop_url: <a class="btn-cmn-buy"> — solo si es URL HTTP(S) (spec §4)
      const $buy_a  = $span.find('a.btn-cmn-buy').first();
      const buy_href = $buy_a.attr('href') || null;
      let shop_url = null;
      if (buy_href && (buy_href.startsWith('http://') || buy_href.startsWith('https://'))) {
        shop_url = buy_href;
      } else if (buy_href && buy_href.startsWith('javascript:')) {
        shop_url = null;
        if (scraper_flags.indexOf('shop_url_js_modal') === -1) {
          scraper_flags.push('shop_url_js_modal');
        }
      }

      products.push({
        product_id,
        product_url,
        product_name,
        brand_id:      current_brand_id,
        brand_name:    current_brand_name,
        brand_url:     current_brand_url,
        release_date,
        shop_url,
        scraped_at,
        scraper_flags: scraper_flags.slice(),
      });
    }).get(); // R12
    return;
  }

  // Otros nodos (div.ttl-day, p, etc.) → ignorar
}).get(); // R12

return { products };
