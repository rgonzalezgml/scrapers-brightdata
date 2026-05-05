// ============================================================================
// cosme-new-arrivals — sc_browser parser_code_v1.js
// ============================================================================
// Misma lógica que sc_code/parser_code_v1.js.
// El DOM de cosme.net es HTML estático: los selectores cheerio son idénticos
// en ambos workers.
//
// IMPORTANTE R12: se usa el patrón .map((_, el) => ...).get() en vez de
// .toArray().map() para máxima portabilidad en el runtime Browser worker.
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

function extractId(href, segment) {
  if (!href) return null;
  const m = href.match(new RegExp('\\/' + segment + '\\/(\\d+)\\/'));
  return m ? m[1] : null;
}

function absUrl(href) {
  if (!href) return null;
  if (href.startsWith('http://') || href.startsWith('https://')) return href;
  if (href.startsWith('/')) return BASE + href;
  return null;
}

function parseTitleDate(text) {
  if (!text) return null;
  const m = text.match(/(\d+)月(\d+)日/);
  if (!m) return null;
  return { month: parseInt(m[1], 10), day: parseInt(m[2], 10) };
}

function buildDate(year, month, day) {
  const mm = String(month).padStart(2, '0');
  const dd = String(day).padStart(2, '0');
  return String(year) + '-' + mm + '-' + dd;
}

// ============================================================================
// STAGE 1: extraer links de días activos del mes
// ============================================================================
if (!input.day) {
  const url_match = (input.url || '').match(/\/year\/(\d{4})\/month\/(\d{1,2})/);
  const year = input.year || (url_match ? parseInt(url_match[1], 10) : null);
  const month = input.month || (url_match ? parseInt(url_match[2], 10) : null);

  const day_urls = [];

  $('table.calendarNaviDay th').map(function (_, el) {
    const $th = $(el);
    const $a = $th.find('p a').first();
    const href = $a.attr('href');
    if (!href) return;

    const day_match = href.match(/\/day\/(\d{1,2})\/?$/);
    if (!day_match) return;

    const day_num = parseInt(day_match[1], 10);
    const day_url = absUrl(href);

    day_urls.push({ url: day_url, day: day_num });
  }).get();

  return { day_urls, year, month };
}

// ============================================================================
// STAGE 2: parsear productos de una página de día
// ============================================================================

const url_match2 = (input.url || '').match(/\/year\/(\d{4})\/month\/(\d{1,2})\/day\/(\d{1,2})/);
const year  = input.year  || (url_match2 ? parseInt(url_match2[1], 10) : null);
const month = input.month || (url_match2 ? parseInt(url_match2[2], 10) : null);
const day   = input.day   || (url_match2 ? parseInt(url_match2[3], 10) : null);

const products = [];
const scraper_flags = [];

const sample_text = $('body').text_sane();
const has_cjk = /[　-鿿豈-﫿]/.test(sample_text);
if (sample_text.length > 0 && !has_cjk) {
  scraper_flags.push('shift_jis_fallback');
}

if ($('div.newProductList').length === 0) {
  return { products: [] };
}

const subtitle_text = $('div.newProductList h3.subTitle').first().text_sane();
const title_date = parseTitleDate(subtitle_text);

if (title_date && year && month) {
  if (title_date.month !== month || (day && title_date.day !== day)) {
    scraper_flags.push('date_mismatch');
  }
}

const release_date = (year && month && day) ? buildDate(year, month, day) : null;

let current_brand_name = null;
let current_brand_id = null;
let current_brand_url = null;

$('div.newProductList').children().map(function (_, el) {
  const $el = $(el);
  const tag = el.tagName ? el.tagName.toLowerCase() : '';

  if (tag === 'h4' && $el.hasClass('brandName')) {
    const $brand_a = $el.find('a').first();
    const brand_href = $brand_a.attr('href') || null;

    if (brand_href) {
      current_brand_name = $brand_a.text_sane();
      current_brand_id   = extractId(brand_href, 'brands');
      current_brand_url  = absUrl(brand_href);
    } else {
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
      const $li = $(li);
      const $span = $li.find('span.name');

      const $prod_a = $span.find('a').not('.btn-cmn-buy').first();
      const prod_href = $prod_a.attr('href') || null;

      const product_id = extractId(prod_href, 'products');
      if (!product_id) return;

      const product_name = $prod_a.text_sane();
      if (!product_name) {
        if (scraper_flags.indexOf('product_name_missing') === -1) {
          scraper_flags.push('product_name_missing');
        }
        return;
      }

      const product_url = BASE + '/products/' + product_id + '/';

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
        scraper_flags: scraper_flags.slice(),
      });
    }).get();
    return;
  }
}).get();

return { products };
