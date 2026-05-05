// ============================================================
// STAGE 2 — PARSER CODE
// Extrae todos los productos del día con 9 campos:
//   product_id, product_url, product_name,
//   brand_id, brand_name, brand_url,
//   release_date (YYYY-MM-DD), shop_url, scraped_at
// ============================================================

const BASE_COSME = 'https://www.cosme.net';
const SHOP_DETAIL = 'https://www.cosme.com/products/detail.php';
const scraped_at = new Date().toISOString();

const year = input.year;
const month = String(input.month).padStart(2, '0');
const day = String(input.day).padStart(2, '0');
const release_date = `${year}-${month}-${day}`;

// ── Helpers ──────────────────────────────────────────────────

function toAbsolute(href) {
  if (!href) return null;
  if (href.startsWith('http')) return href;
  return BASE_COSME + href;
}

function extractId(href, segment) {
  if (!href) return null;
  const m = href.match(new RegExp(`\\/${segment}\\/(\\d+)\\/`));
  return m ? m[1] : null;
}

function resolveShopUrl(href) {
  if (!href || href === '#') return null;
  if (href.startsWith('http')) return href;
  // javascript:tb_show('','/dialog/shopping-link/index/productId/12345?...')
  const tbMatch = href.match(/productId\/(\d+)/);
  if (tbMatch) return `${SHOP_DETAIL}?product_id=${tbMatch[1]}`;
  if (href.startsWith('/')) return BASE_COSME + href;
  return null;
}

// ── Extracción ───────────────────────────────────────────────

const products = [];

if (!$('div.newProductList').length) {
  return { products };
}

let currentBrand = { brand_id: null, brand_name: null, brand_url: null };

$('div.newProductList').children().each((i, node) => {
  const el = $(node);

  // Nueva marca
  if (el.is('h4.brandName')) {
    const brandLink = el.find('a[href*="/brands/"]').first();
    if (brandLink.length) {
      const href = brandLink.attr('href');
      currentBrand = {
        brand_id: extractId(href, 'brands'),
        brand_name: brandLink.text().trim(),
        brand_url: toAbsolute(href),
      };
    }
    return;
  }

  // Lista de productos
  if (el.is('ul.productInformation')) {
    el.find('li').each((j, li) => {
      const productLink = $(li).find('p.productName span.name > a:not(.btn-cmn-buy)').first();
      if (!productLink.length) return;

      const productHref = productLink.attr('href');
      const shopHref = $(li).find('a.btn-cmn-buy').attr('href') || null;

      products.push({
        product_id: extractId(productHref, 'products'),
        url: toAbsolute(productHref),
        product_name: productLink.text().trim(),
        brand_id: currentBrand.brand_id,
        brand_name: currentBrand.brand_name,
        brand_url: currentBrand.brand_url,
        release_date,
        shop_url: resolveShopUrl(shopHref),
        scraped_at,
      });
    });
  }
});

return { products };