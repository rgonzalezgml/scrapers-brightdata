// ============================================================================
// cosme-new-arrivals — sc_code parser_code_v1.js
// ============================================================================
// Sirve para dos stages:
//   Stage 1 (input.day ausente): extrae day_urls desde la tabla de días del mes.
//   Stage 2 (input.day presente): extrae productos del día → array de new_product.
//
// Encoding: www.cosme.net sirve Shift_JIS. BrightData Code worker recibe el
// body decodificado como Latin-1 por defecto cuando no se especifica encoding.
// La función load_html() acepta un segundo argumento de encoding. Sin embargo,
// dado que el runtime ya parsea el HTML con cheerio, usamos el $ global cargado
// por el runtime y aplicamos una corrección de encoding cuando sea necesario.
//
// Nota de implementación: en el runtime Code worker de BrightData el $ global
// ya contiene el HTML parseado (el runtime auto-decodifica). Si los caracteres
// japoneses aparecen correctamente en $ no hay nada que hacer. El flag
// shift_jis_fallback se emite como señal de diagnóstico (spec §8).
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
// extractId('/brands/42/', 'brands') → '42'
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
  // Extraer year/month del input.url como fallback
  // URL esperada: .../calendar/index/year/YYYY/month/MM
  const url_match = (input.url || '').match(/\/year\/(\d{4})\/month\/(\d{1,2})/);
  const year = input.year || (url_match ? parseInt(url_match[1], 10) : null);
  const month = input.month || (url_match ? parseInt(url_match[2], 10) : null);

  const day_urls = [];

  // Días activos están en table.calendarNaviDay → celdas th con <a>
  // Los días sin lanzamientos tienen clase p.dayNN.off (o directamente th sin <a>)
  $('table.calendarNaviDay th').map(function (_, el) {
    const $th = $(el);
    const $a = $th.find('p a').first();
    const href = $a.attr('href');
    if (!href) return; // día sin link = sin lanzamientos

    // Extraer el número de día del href
    const day_match = href.match(/\/day\/(\d{1,2})\/?$/);
    if (!day_match) return;

    const day_num = parseInt(day_match[1], 10);
    const day_url = absUrl(href);

    day_urls.push({ url: day_url, day: day_num });
  }).get(); // .get() para forzar evaluación (R12 pattern)

  return { day_urls, year, month };
}

// ============================================================================
// STAGE 2: parsear productos de una página de día
// ============================================================================

// Extraer year/month/day del input o de la URL
const url_match2 = (input.url || '').match(/\/year\/(\d{4})\/month\/(\d{1,2})\/day\/(\d{1,2})/);
const year  = input.year  || (url_match2 ? parseInt(url_match2[1], 10) : null);
const month = input.month || (url_match2 ? parseInt(url_match2[2], 10) : null);
const day   = input.day   || (url_match2 ? parseInt(url_match2[3], 10) : null);

const products = [];
const scraper_flags = [];

// Verificación de encoding: si no hay ningún carácter CJK y el body existe,
// podría haber un problema de Shift_JIS. Emitimos el flag diagnóstico.
const sample_text = $('body').text_sane();
const has_cjk = /[　-鿿豈-﫿]/.test(sample_text);
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
  // Verificar coherencia entre el path URL y el título de la página (spec §5)
  if (title_date.month !== month || (day && title_date.day !== day)) {
    scraper_flags.push('date_mismatch');
  }
}

// Construir la fecha de lanzamiento usando el path URL (prioritario según spec §5)
const release_date = (year && month && day) ? buildDate(year, month, day) : null;

// Recorrer el DOM de div.newProductList
// Estructura: h4.brandName → ul.productInformation → li* → p.productName → span.name → a*
// Cada h4.brandName introduce una nueva sección de marca hasta el próximo h4.brandName

let current_brand_name = null;
let current_brand_id = null;
let current_brand_url = null;

// Recorrer todos los nodos directos de div.newProductList que sean h4 o ul
$('div.newProductList').children().map(function (_, el) {
  const $el = $(el);
  const tag = el.tagName ? el.tagName.toLowerCase() : '';

  if (tag === 'h4' && $el.hasClass('brandName')) {
    // Actualizar contexto de marca
    const $brand_a = $el.find('a').first();
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
    // Recorrer todos los <li> de esta lista
    $el.find('li').map(function (_, li) {
      const $li = $(li);
      const $span = $li.find('span.name');

      // Primer <a> = link al producto en cosme.net
      const $prod_a = $span.find('a').not('.btn-cmn-buy').first();
      const prod_href = $prod_a.attr('href') || null;

      // product_id → skip si no se puede extraer (spec §7)
      const product_id = extractId(prod_href, 'products');
      if (!product_id) return; // skip

      // product_name → skip si vacío (spec §7)
      const product_name = $prod_a.text_sane();
      if (!product_name) {
        if (scraper_flags.indexOf('product_name_missing') === -1) {
          scraper_flags.push('product_name_missing');
        }
        return; // skip
      }

      const product_url = BASE + '/products/' + product_id + '/';

      // shop_url: <a class="btn-cmn-buy"> — solo si es URL HTTP(S) (spec §4)
      const $buy_a = $span.find('a.btn-cmn-buy').first();
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
        brand_id:     current_brand_id,
        brand_name:   current_brand_name,
        brand_url:    current_brand_url,
        release_date,
        shop_url,
        scraped_at,
        scraper_flags: scraper_flags.slice(), // copia para no compartir referencia
      });
    }).get();
    return;
  }

  // Otros nodos (div.ttl-day, p, etc.) → ignorar
}).get();

return { products };
