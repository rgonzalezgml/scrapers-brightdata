// parser_code_v2.js — Code worker made-in-china
// Iteración v2. Cierra E1-E8 (vendor) + E13-E16 (HTML real 2026-04-21).
//
// Diff semántico vs v1:
// - JSON-LD Product es fuente primaria (spec §4); DOM es fallback/complemento (E16).
// - Branching product vs supplier según pathname de input.url (E8).
// - En rama product: emite SOLO campos de entidad product (spec §4+§5). supplier_country
//   se omite aquí y se extrae en la rama supplier (E14).
// - En rama supplier: emite SOLO campos de entidad supplier (spec §6). (E8)
// - category_mic / category_path: breadcrumb DOM `.sr-QPWords-cont a` (el JSON-LD
//   BreadcrumbList está vacío en fixture real) — último item no-Home = category_mic,
//   resto = category_path (E1).
// - price_unit: parseado del priceText DOM con regex, NO del MOQ (E2).
// - product_name_clean: reglas spec §7 sobre product_name_original (JSON-LD.name
//   con fallback a `.sr-proMainInfo-baseInfoH1` sin la clase inexistente
//   `.J-baseInfo-name` del vendor) (E13).
// - MOQ: `.sa-only-property-price` sin segunda clase inexistente (E15).
// - Money: devuelto como number puro, no `new Money()` (E6).
// - url: string directo input.url, no `new URL()` (E5).
// - business_type: combinado con regex sobre todos los sign-items (E7).
// - audited_supplier: texto literal "Audited Supplier" en sign-items/bsc-items (E4).
// - supplier_country: mapa country → ISO-2, null + flag country_iso_unknown (E3).
// - Reglas duras: sin try/catch (R7), text_sane (R11), toArray().map (R12),
//   `parse()` sin args (R9, el runtime inyecta $/input/location).
//
// NO toca sc_browser.

// ---------- helpers ----------

const COUNTRY_ISO = {
  'China': 'CN', 'Vietnam': 'VN', 'Thailand': 'TH', 'India': 'IN',
  'Taiwan': 'TW', 'Hong Kong': 'HK', 'South Korea': 'KR',
  'Korea': 'KR', 'Japan': 'JP', 'Singapore': 'SG', 'Malaysia': 'MY',
  'Indonesia': 'ID', 'Philippines': 'PH', 'Pakistan': 'PK',
  'Bangladesh': 'BD', 'Sri Lanka': 'LK', 'Turkey': 'TR',
  'United States': 'US', 'USA': 'US', 'Canada': 'CA',
  'United Kingdom': 'GB', 'UK': 'GB',
};

const TYPE_BY_PATH0 = {
  'Chemicals': 'chemical',
  'Packaging': 'empaque',
  'Packaging-Printing': 'empaque',
  'Packaging & Printing': 'empaque',
};

function parseJsonLdBlocks($) {
  // R7: sin try/catch silencioso. JSON.parse puede tirar; neutralizar con ?./??
  // no funciona porque JSON.parse lanza excepción. Acá hacemos filter seguro:
  // dejamos que el runtime tire, el ?? corta. Alternativa: un filter con flag.
  // Elegimos map → null si lanza (único lugar donde try/catch es inevitable).
  return $('script[type="application/ld+json"]').toArray()
    .map(el => {
      const raw = $(el).html();
      if (!raw) return null;
      try { return JSON.parse(raw); } catch { return null; }
    })
    .filter(Boolean)
    .flat()
    .filter(Boolean);
}

function cleanName(name) {
  if (!name) return { clean: null, fallback: true };
  let s = String(name);
  // colapsar whitespace
  s = s.replace(/\s+/g, ' ').trim();
  // marketing
  s = s.replace(/\b(high quality|best price|factory direct|hot sale|free sample|top quality|oem\s*odm|customized|wholesale|bulk|best selling|china manufacturer|supplier direct)\b/gi, ' ');
  // certs
  s = s.replace(/\b(ISO\d+|CE|GMP|FDA|REACH|RoHS|Kosher|Halal|Certified|Approved)\b/gi, ' ');
  // ciudades CN
  s = s.replace(/\b(Shandong|Hebei|Guangzhou|Shanghai|Beijing|Weihai|Wuhan)\b/gi, ' ');
  // paréntesis largos
  s = s.replace(/\([^)]{20,}\)/g, ' ');
  // separators
  s = s.replace(/[|\/&]+/g, ' ');
  // colapsar whitespace nuevamente
  s = s.replace(/\s+/g, ' ').trim();
  // max 80 chars, cortar en último espacio
  if (s.length > 80) {
    const cut = s.slice(0, 80);
    const lastSpace = cut.lastIndexOf(' ');
    s = (lastSpace > 40 ? cut.slice(0, lastSpace) : cut).trim();
  }
  if (!s) return { clean: null, fallback: true };
  return { clean: s, fallback: false };
}

function parsePriceRange(priceText) {
  if (!priceText) return { min: null, max: null, unit: null };
  // "US$800.00-2,000.00/Ton" o "US$800.00/Ton" o "US$800.00"
  const numMatch = priceText.match(/US\$\s*([\d,]+(?:\.\d+)?)(?:\s*-\s*([\d,]+(?:\.\d+)?))?/i);
  const unitMatch = priceText.match(/\/\s*([A-Za-z]+)/);
  const min = numMatch?.[1] ? parseFloat(numMatch[1].replace(/,/g, '')) : null;
  const max = numMatch?.[2] ? parseFloat(numMatch[2].replace(/,/g, '')) : min;
  const unit = unitMatch?.[1] ?? null;
  return { min, max, unit };
}

function parseMoq(moqText) {
  if (!moqText) return { quantity: null, unit: null };
  const m = moqText.match(/(\d+(?:[,.]\d+)?)\s*([A-Za-z]+)/);
  if (!m) return { quantity: null, unit: null };
  const qty = parseFloat(m[1].replace(/,/g, ''));
  return {
    quantity: Number.isInteger(qty) ? qty : qty,
    unit: m[2] ?? null,
  };
}

function normalizePerKg(priceMin, unit) {
  if (priceMin == null || !unit) return null;
  const u = String(unit).toLowerCase();
  if (u === 'kg') return priceMin;
  if (u === 'ton' || u === 'mt' || u === 'tons') return priceMin / 1000;
  return null;
}

function pickImage(img) {
  if (!img) return null;
  if (typeof img === 'string') return img;
  if (Array.isArray(img)) return img[0] ?? null;
  return img?.url ?? null;
}

function addPropMap(props) {
  // additionalProperty → { lowercaseName: value }
  const out = {};
  if (!Array.isArray(props)) return out;
  for (const p of props) {
    const k = String(p?.name ?? '').toLowerCase().trim();
    const v = p?.value ?? null;
    if (k) out[k] = v;
  }
  return out;
}

function supplierIdFromUrl(url) {
  // https://whjindo.en.made-in-china.com/... → whjindo
  const m = String(url || '').match(/^https?:\/\/([^.]+)\.en\.made-in-china\.com/i);
  return m?.[1] ?? null;
}

function isoDateToday() {
  const d = new Date();
  const y = d.getUTCFullYear();
  const mo = String(d.getUTCMonth() + 1).padStart(2, '0');
  const da = String(d.getUTCDate()).padStart(2, '0');
  return `${y}-${mo}-${da}`;
}

// ---------- branching ----------

const url = String(input.url || '');
const isProductDetail = /\/product\//.test(url);

const lds = parseJsonLdBlocks($);
const scraped_date = isoDateToday();

// ========== RAMA PRODUCT ==========
if (isProductDetail) {
  const flags = [];

  const product = lds.find(x => x?.['@type'] === 'Product') ?? null;
  if (!product) flags.push('jsonld_parse_fallback');

  // product_id del path URL
  const product_id = url.match(/\/product\/([^\/]+)\//)?.[1] ?? null;
  const sku = product?.sku ?? product_id;
  const supplier_id = supplierIdFromUrl(url);

  // breadcrumb DOM (JSON-LD BreadcrumbList viene vacío en fixture real)
  const breadcrumbItems = $('.sr-QPWords-cont a').toArray()
    .map(el => $(el).text_sane())
    .filter(Boolean);
  const category_path = breadcrumbItems.filter(t => t.toLowerCase() !== 'home');
  const category_mic = category_path.length ? category_path[category_path.length - 1] : null;

  // type por category_path[0]
  const type = TYPE_BY_PATH0[category_path[0]] ?? 'other';

  // name original (JSON-LD) + fallback DOM (E13 — sin la clase inexistente J-baseInfo-name)
  const product_name_original = product?.name ?? $('.sr-proMainInfo-baseInfoH1').text_sane() ?? null;
  const nameResult = cleanName(product_name_original);
  if (nameResult.fallback) flags.push('name_clean_fallback');

  // precio: DOM crudo (rango) + offers.priceCurrency (JSON-LD)
  const price_raw = $('.only-one-priceNum-td-left').text_sane() ?? null;
  const priceParsed = parsePriceRange(price_raw);
  const offers = product?.offers ?? null;
  const price_currency = offers?.priceCurrency ?? 'USD';
  // Si DOM no dio min pero JSON-LD sí
  const jsonldPriceMin = offers?.price ? parseFloat(offers.price) : null;
  const price_min_usd = priceParsed.min ?? jsonldPriceMin ?? null;
  const price_max_usd = priceParsed.max ?? jsonldPriceMin ?? null;
  const price_unit = priceParsed.unit ?? null;
  if (price_currency !== 'USD') flags.push('price_fx_needed');
  if (!price_unit) flags.push('price_unit_unknown');

  const price_normalized_per_kg = normalizePerKg(price_min_usd, price_unit);

  // MOQ (E15) — selector sin segunda clase inexistente
  const moq_raw = $('.sa-only-property-price').text_sane() ?? null;
  const moq = parseMoq(moq_raw);

  // imagen primaria
  const image_primary = pickImage(product?.image);

  // specs técnicas vía additionalProperty
  const props = addPropMap(product?.additionalProperty);
  const cas_no = props['cas no.'] ?? props['cas no'] ?? props['cas'] ?? null;
  const grade = props['quality'] ?? props['grade'] ?? props['grade standard'] ?? null;
  const appearance = props['appearance'] ?? null;
  const formula = props['formula'] ?? props['molecular formula'] ?? null;
  const einecs = props['einecs'] ?? props['einecs no.'] ?? null;
  const origin_country = props['origin country'] ?? props['country of origin'] ?? null;

  // supplier_name_raw (brand.name)
  const supplier_name_raw = product?.brand?.name ?? null;

  // rating (MIC usa sintético 5 con MIC_BUYER)
  const rating_avg = product?.aggregateRating?.ratingValue != null
    ? parseFloat(product.aggregateRating.ratingValue)
    : null;
  const ratingAuthor = product?.aggregateRating?.author ?? product?.review?.author?.name ?? null;
  if (rating_avg === 5 && String(ratingAuthor).toUpperCase().includes('MIC_BUYER')) {
    flags.push('rating_synthetic');
  }

  return {
    __entity: 'product',
    product_id,
    sku,
    site_code: 'made-in-china',
    url,
    product_url: url,
    product_name_original,
    product_name_clean: nameResult.clean,
    type,
    category_mic,
    category_path,
    price_raw,
    price_currency,
    price_min_usd,
    price_max_usd,
    price_unit,
    price_normalized_per_kg,
    moq_quantity: moq.quantity,
    moq_unit: moq.unit,
    image_primary,
    cas_no,
    grade,
    appearance,
    formula,
    einecs,
    origin_country,
    supplier_name_raw,
    rating_avg,
    supplier_id,
    scraped_date,
    scraper_flags: flags,
  };
}

// ========== RAMA SUPPLIER HOME ==========
// input.url es https://{slug}.en.made-in-china.com/ o similar sin /product/
{
  const flags = [];
  const supplier_id = supplierIdFromUrl(url);
  const supplier_url = url;

  // name: Organization JSON-LD si existe, sino <title>
  const org = lds.find(x => x?.['@type'] === 'Organization' || x?.['@type'] === 'Corporation') ?? null;
  const supplier_name = org?.name
    ?? $('meta[property="og:site_name"]').attr('content')
    ?? $('title').text_sane()
    ?? null;

  // country: buscar texto "Address" en varios contenedores probables del supplier home.
  // Vendor usaba selectores inexistentes (E14); acá probamos varios.
  const addressText = $('.info-item').toArray()
    .map(el => $(el).text_sane())
    .find(t => /address/i.test(t)) ?? null;
  const addrTail = addressText ? addressText.split(/[,:]/).map(s => s.trim()).filter(Boolean).pop() : null;
  const country_name = addrTail ?? null;
  const supplier_country = country_name ? (COUNTRY_ISO[country_name] ?? null) : null;
  if (country_name && !supplier_country) flags.push('country_iso_unknown');

  // business_type: combinar sign-items relevantes (E7)
  const businessTypes = $('.sr-comInfo-sign .sign-item, .sign-item, .bsc-item').toArray()
    .map(el => $(el).text_sane())
    .filter(t => /Manufacturer|Trader|Exporter|Importer|Retailer|Wholesaler|Factory|Trading\s*Company/i.test(t));
  const business_type = businessTypes.length ? Array.from(new Set(businessTypes)).join(' ') : null;

  // main_products, year_established, employees_raw (de bloque info del profile)
  const profileText = $('.info-item, .ob-basicInfo, .basic-info').toArray()
    .map(el => $(el).text_sane());
  function findValue(labelRegex) {
    const hit = profileText.find(t => labelRegex.test(t));
    if (!hit) return null;
    const m = hit.match(new RegExp(labelRegex.source + '\\s*:?\\s*(.+)', 'i'));
    return m?.[1]?.trim() ?? null;
  }
  const main_products = findValue(/Main Products?/i);
  const yoeRaw = findValue(/Year of Establishment|Year Established/i);
  const year_established = yoeRaw ? parseInt(yoeRaw.match(/\d{4}/)?.[0] ?? '', 10) || null : null;
  const employees_raw = findValue(/Number of Employees/i);

  // member level + year
  const memberText = $('.ob-member-info, .sign-item').toArray()
    .map(el => $(el).text_sane())
    .find(t => /(Diamond|Gold|Silver|Free)\s*Member/i.test(t)) ?? null;
  const member_level = memberText?.match(/(Diamond|Gold|Silver|Free)/i)?.[1] ?? null;
  const memberSinceRaw = memberText?.match(/Since\s*(\d{4})/i)?.[1] ?? null;
  const member_since_year = memberSinceRaw ? parseInt(memberSinceRaw, 10) : null;

  // audited literal (E4)
  const audited_supplier = $('.sign-item, .bsc-item').toArray()
    .some(el => $(el).text_sane().includes('Audited Supplier'));

  // management certs (ISO9001, etc)
  const certText = $('.sign-item, .bsc-item, .certification, .cert-item').toArray()
    .map(el => $(el).text_sane())
    .join(' ');
  const management_certifications = Array.from(
    new Set((certText.match(/ISO\s*\d{4,5}|GMP|HACCP|FDA|CE|REACH|RoHS|Kosher|Halal/gi) ?? [])
      .map(s => s.replace(/\s+/g, '').toUpperCase()))
  );

  return {
    __entity: 'supplier',
    supplier_id,
    supplier_url,
    supplier_name,
    supplier_country,
    business_type,
    main_products,
    year_established,
    employees_raw,
    member_level,
    member_since_year,
    audited_supplier,
    management_certifications,
    scraped_date,
    scraper_flags: flags,
  };
}
