// ---------- EXCHANGE rates ----------

const EXCHANGE_RATES = {
    INR: 0.012,
    USD: 1,
    EUR: 1.08,
    GBP: 1.27,
};

// ---------- helpers ----------

function parseJsonLdBlocks($) {
    // Único try/catch aceptado (R7): JSON.parse del loop JSON-LD.
    return $('script[type="application/ld+json"]').toArray()
        .map(el => {
            const raw = $(el).html();
            if (!raw) return null;
            try { return JSON.parse(raw); } catch { return null; }
        })
        .filter(Boolean)
        .flatMap(x => Array.isArray(x) ? x : [x])
        .filter(Boolean);
}

function pickImage(img) {
    if (!img) return null;
    if (typeof img === 'string') return img;
    if (Array.isArray(img)) return img[0] ?? null;
    return img?.url ?? null;
}

function truncate(s, n) {
    if (s == null) return null;
    const str = String(s).replace(/\s+/g, ' ').trim();
    if (!str) return null;
    return str.length > n ? str.slice(0, n) : str;
}

function cleanName(name) {
    if (!name) return { clean: null, fallback: true };
    let s = String(name).replace(/\s+/g, ' ').trim();
    s = s.replace(/\b(high quality|best price|industrial grade|hot sale|best selling|oem\s*odm|customized|wholesale|bulk|premium|top quality|supplier|manufacturer|exporter|wholesale supplier)\b/gi, ' ');
    s = s.replace(/\b(ISO\d+|CE|GMP|FDA|REACH|RoHS|Kosher|Halal|Certified|Approved)\b/gi, ' ');
    s = s.replace(/\b(Delhi|Mumbai|Chennai|Kolkata|Ahmedabad|Bengaluru|Hyderabad|Jaipur|Pune|Surat)\b/gi, ' ');
    s = s.replace(/\([^)]{20,}\)/g, ' ');
    s = s.replace(/[|\/&]+/g, ' ');
    s = s.replace(/\s+/g, ' ').trim();
    if (s.length > 80) {
        const cut = s.slice(0, 80);
        const lastSpace = cut.lastIndexOf(' ');
        s = (lastSpace > 40 ? cut.slice(0, lastSpace) : cut).trim();
    }
    if (!s) return { clean: null, fallback: true };
    return { clean: s, fallback: false };
}

function parseTitlePrice(titleText) {
    // Formato real del title: "Caustic Soda Flakes at ₹ 50/kg | Caustic Soda in New Delhi | ID: 22408594448"
    // Extrae el fragmento "₹ 50/kg" o "₹ 50-100/kg". Si hay rango, min/max distintos.
    if (!titleText) return { raw: null, min: null, max: null, unit: null };
    const m = titleText.match(/([₹$€£¥])\s*([\d,]+(?:\.\d+)?)(?:\s*-\s*([\d,]+(?:\.\d+)?))?\s*\/\s*([A-Za-z]+)/);
    if (!m) return { raw: null, min: null, max: null, unit: null };
    const raw = m[0];
    const minNum = parseFloat(m[2].replace(/,/g, ''));
    const maxNum = m[3] ? parseFloat(m[3].replace(/,/g, '')) : minNum;
    const unit = (m[4] ?? '').toLowerCase();
    return { raw, min: minNum, max: maxNum, unit: unit || null };
}

function normalizeMoqUnit(unit) {
    if (!unit) return null;
    const u = String(unit).toLowerCase().trim();
    if (u === 'kg' || u === 'kgs') return 'kg';
    if (u === 'mt') return 'mt';
    if (u === 'ton' || u === 'tons' || u === 'tonne' || u === 'tonnes') return 'ton';
    if (u === 'l' || u === 'litre' || u === 'litres' || u === 'liter' || u === 'liters') return 'L';
    if (u === 'piece' || u === 'pieces' || u === 'pcs' || u === 'pc' || u === 'number' || u === 'unit' || u === 'units') return 'piece';
    if (u === 'bag' || u === 'bags') return 'bag';
    if (u === 'drum' || u === 'drums') return 'drum';
    if (u === 'set' || u === 'sets') return 'set';
    if (u === 'dozen' || u === 'dozens') return 'dozen';
    if (u === 'box' || u === 'boxes') return 'box';
    return u;
}

function parseMoqString(qtyStr, unitStr) {
    if (qtyStr == null) return { quantity: null, unit: null };
    const numStr = String(qtyStr).replace(/,/g, '').trim();
    if (!numStr) return { quantity: null, unit: null };
    const num = parseFloat(numStr);
    if (Number.isNaN(num)) return { quantity: null, unit: null };
    const unit = normalizeMoqUnit(unitStr);
    return {
        quantity: Number.isInteger(num) ? num : num,
        unit,
    };
}

function normalizePerKg(priceUsd, unit) {
    if (priceUsd == null || !unit) return null;
    const u = String(unit).toLowerCase();
    if (u === 'kg') return priceUsd;
    if (u === 'ton' || u === 'mt') return priceUsd / 1000;
    return null;
}

function toUsd(value, currency) {
    if (value == null) return null;
    const rate = EXCHANGE_RATES[currency];
    if (rate == null) return null;
    return Number((value * rate).toFixed(4));
}

function isoDateToday() {
    const d = new Date();
    const y = d.getUTCFullYear();
    const mo = String(d.getUTCMonth() + 1).padStart(2, '0');
    const da = String(d.getUTCDate()).padStart(2, '0');
    return `${y}-${mo}-${da}`;
}

function toUrl(value) {
    if (!value) return null;
    return new URL(value);
}

function toMoney(value, currency) {
    if (value == null || Number.isNaN(Number(value))) return null;
    return new Money(Number(value), currency || 'USD');
}

function specTableValue($, labels) {
    // Busca en `<table> <tr><td>{label}</td><td>{value}</td></tr>` el primer
    // value cuyo label (case-insensitive) matchee cualquiera de `labels`.
    const rows = $('table tr').toArray();
    for (const tr of rows) {
        const cells = $(tr).find('td').toArray();
        if (cells.length < 2) continue;
        const label = $(cells[0]).text_sane().toLowerCase();
        if (!label) continue;
        for (const want of labels) {
            if (label === want.toLowerCase()) {
                return $(cells[cells.length - 1]).text_sane() || null;
            }
        }
    }
    return null;
}

function compdtsValue($, labelRegex) {
    // `<li class="compdtsItems"><p class="fs12 color1">{Label}</p><h4 class="cmpfvalh4">{Value}</h4></li>`
    const hits = $('li.compdtsItems').toArray()
        .map(li => {
            const label = $(li).find('p.fs12.color1').text_sane();
            const value = $(li).find('h4.cmpfvalh4').text_sane();
            return { label, value };
        })
        .filter(x => x.label && labelRegex.test(x.label));
    return hits[0]?.value ?? null;
}

// ---------- parse ----------

const flags = [];
const raw_html = $.html();
const urlRaw = String(input.url || '');

// 1) JSON-LD blocks ---------------------------------------------------------

const lds = parseJsonLdBlocks($);
const product_ld = lds.find(x => x?.['@type'] === 'Product') ?? null;
const breadcrumb = lds.find(x => x?.['@type'] === 'BreadcrumbList') ?? null;
if (!product_ld) flags.push('jsonld_parse_fallback');
if (!breadcrumb) flags.push('breadcrumb_missing');

// 2) product_id -------------------------------------------------------------

const product_id = urlRaw.match(/-(\d{11,13})\.html(?:$|\?)/)?.[1]
    ?? urlRaw.match(/(\d{11,13})\.html$/)?.[1]
    ?? null;

// 3) product_url (canonical) ------------------------------------------------

const canonical_href = $('link[rel="canonical"]').attr('href') || null;
const product_url_str = canonical_href || urlRaw;

// 4) name / description / image (desde Product JSON-LD) ---------------------

const product_name_original = product_ld?.name
    ?? $('h1.center-heading').text_sane()
    ?? null;
const nameResult = cleanName(product_name_original);
if (nameResult.fallback) flags.push('name_clean_fallback');

const product_description = truncate(product_ld?.description, 500);
const image_primary = pickImage(product_ld?.image)
    ?? $('meta[property="og:image"]').attr('content')
    ?? null;

// 5) breadcrumb → category_path / category_mic / industry_slug / type -------

const breadcrumbItems = Array.isArray(breadcrumb?.itemListElement)
    ? breadcrumb.itemListElement
    : [];
// position=1 es "IndiaMART" → se descarta
const categoryItems = breadcrumbItems
    .filter(x => (x?.position ?? 0) >= 2)
    .sort((a, b) => (a.position ?? 0) - (b.position ?? 0));

const category_path = categoryItems.map(x => x?.item?.name ?? x?.name ?? null).filter(Boolean);
const category_mic = category_path.length ? category_path[category_path.length - 1] : null;

// industry_slug desde position=2 `.@id` regex `/indianexporters/ind_(\w+)\.html`
const position2 = categoryItems.find(x => x?.position === 2) ?? null;
const position2_id = position2?.item?.['@id'] ?? position2?.['@id'] ?? '';
const position2_name = position2?.item?.name ?? position2?.name ?? '';
const industry_slug = position2_id.match(/\/indianexporters\/ind_(\w+)\.html/i)?.[1] ?? null;

// type enum según §4/§8:
let type = 'other';
if (/ind_chem/i.test(position2_id) || /Chemical/i.test(position2_name)) {
    type = 'chemical';
} else if (/ind_packaging/i.test(position2_id) || /Packaging/i.test(position2_name)) {
    type = 'packaging';
}

// 6) title + price ----------------------------------------------------------

const titleText = $('title').text_sane();
const titleParsed = parseTitlePrice(titleText);

// JSON-LD offers (source primario de currency + value)
const offers = product_ld?.offers ?? null;
const price_currency = offers?.priceCurrency ?? 'INR';
if (price_currency && price_currency !== 'INR') flags.push('currency_unexpected');

const price_value_raw = offers?.price != null ? String(offers.price) : (titleParsed.min != null ? String(titleParsed.min) : null);
const price_raw = titleParsed.raw ?? null;
const price_unit = titleParsed.unit ?? null;
if (!price_unit) flags.push('price_unit_unknown');

// Conversión a USD: JSON-LD price → min; title max → max
const jsonldMin = offers?.price != null ? parseFloat(String(offers.price).replace(/,/g, '')) : null;
const priceMinNative = jsonldMin ?? titleParsed.min ?? null;
const priceMaxNative = titleParsed.max ?? priceMinNative ?? null;
const price_min_usd_num = toUsd(priceMinNative, price_currency);
const price_max_usd_num = toUsd(priceMaxNative, price_currency);
const price_norm_num = normalizePerKg(price_min_usd_num, price_unit);

// availability
const availabilityRaw = offers?.availability ?? null;
let availability = null;
if (availabilityRaw) {
    const av = String(availabilityRaw);
    if (/InStock/i.test(av)) availability = 'InStock';
    else if (/OutOfStock/i.test(av)) availability = 'OutOfStock';
    else availability = av.split('/').pop();
}

// 7) MOQ: spec table → embedded JSON fallback -------------------------------

let moq_raw_value = specTableValue($, ['Minimum Order Quantity']);
let moq_quantity = null;
let moq_unit = null;

if (moq_raw_value) {
    const m = moq_raw_value.match(/(\d+(?:[,.]\d+)?)\s*([A-Za-z]+)?/);
    if (m) {
        const parsed = parseMoqString(m[1], m[2]);
        moq_quantity = parsed.quantity;
        moq_unit = parsed.unit;
    }
}

if (moq_quantity == null) {
    // Fallback embedded JSON (E5). Regex sobre HTML raw.
    const qtyMatch = raw_html.match(/"PC_ITEM_MIN_ORDER_QUANTITY"\s*:\s*"([^"]*)"/);
    const unitMatch = raw_html.match(/"PC_ITEM_MOQ_UNIT_TYPE"\s*:\s*"([^"]*)"/);
    const qtyRaw = qtyMatch?.[1] ?? null;
    const unitRaw = unitMatch?.[1] ?? null;
    if (qtyRaw && qtyRaw.trim()) {
        const parsed = parseMoqString(qtyRaw, unitRaw);
        moq_quantity = parsed.quantity;
        moq_unit = parsed.unit;
        if (moq_quantity != null) flags.push('moq_from_embedded_json');
    } else {
        // Fallback 2: FK_IM_SPEC_MASTER_DESC ↔ SUPPLIER_RESPONSE_DETAIL por índice
        const labelsMatch = raw_html.match(/"FK_IM_SPEC_MASTER_DESC"\s*:\s*\[([^\]]*)\]/);
        const valuesMatch = raw_html.match(/"SUPPLIER_RESPONSE_DETAIL"\s*:\s*\[([^\]]*)\]/);
        if (labelsMatch && valuesMatch) {
            const labels = (labelsMatch[1].match(/"([^"]*)"/g) ?? []).map(s => s.replace(/^"|"$/g, ''));
            const values = (valuesMatch[1].match(/"([^"]*)"/g) ?? []).map(s => s.replace(/^"|"$/g, ''));
            const idx = labels.findIndex(l => /minimum order quantity/i.test(l));
            if (idx >= 0 && values[idx]) {
                const vm = values[idx].match(/(\d+(?:[,.]\d+)?)\s*([A-Za-z]+)?/);
                if (vm) {
                    const parsed = parseMoqString(vm[1], vm[2] ?? unitMatch?.[1]);
                    moq_quantity = parsed.quantity;
                    moq_unit = parsed.unit;
                    if (moq_quantity != null) flags.push('moq_from_embedded_json');
                }
            }
        }
    }
}

if (moq_quantity == null) flags.push('moq_missing');

// 8) spec table auxiliar (§5) -----------------------------------------------

const appearance_raw = specTableValue($, ['Form', 'Appearance']);
const grade_raw = specTableValue($, ['Grade', 'Quality Grade']);
const concentration_raw = specTableValue($, ['Concentration', 'Purity', 'NaOH Concentration', 'Purity %']);
const cas_no_raw = specTableValue($, ['CAS No', 'CAS No.', 'CAS Number']);
const packaging_type_raw = specTableValue($, ['Packaging Type']);

// Fallback desde embedded JSON si spec table no trae la fila
function embeddedSpecValue(labelWant) {
    const labelsMatch = raw_html.match(/"FK_IM_SPEC_MASTER_DESC"\s*:\s*\[([^\]]*)\]/);
    const valuesMatch = raw_html.match(/"SUPPLIER_RESPONSE_DETAIL"\s*:\s*\[([^\]]*)\]/);
    if (!labelsMatch || !valuesMatch) return null;
    const labels = (labelsMatch[1].match(/"([^"]*)"/g) ?? []).map(s => s.replace(/^"|"$/g, ''));
    const values = (valuesMatch[1].match(/"([^"]*)"/g) ?? []).map(s => s.replace(/^"|"$/g, ''));
    const idx = labels.findIndex(l => l.toLowerCase() === labelWant.toLowerCase());
    return idx >= 0 ? (values[idx] || null) : null;
}

const appearance = appearance_raw
    ?? embeddedSpecValue('Form')
    ?? embeddedSpecValue('Appearance')
    ?? null;
const grade = grade_raw
    ?? embeddedSpecValue('Grade')
    ?? embeddedSpecValue('Quality Grade')
    ?? null;
const concentration = concentration_raw
    ?? embeddedSpecValue('NaOH Concentration')
    ?? embeddedSpecValue('Concentration')
    ?? embeddedSpecValue('Purity')
    ?? embeddedSpecValue('Purity %')
    ?? null;
const cas_no = cas_no_raw
    ?? embeddedSpecValue('CAS No')
    ?? embeddedSpecValue('CAS Number')
    ?? null;
const packaging_type = packaging_type_raw
    ?? embeddedSpecValue('Packaging Type')
    ?? null;

// flag si la spec table como tal no devolvió ninguna de las rows canónicas
if (!appearance_raw && !grade_raw && !concentration_raw && !cas_no_raw && !packaging_type_raw) {
    flags.push('spec_table_missing');
}

// 9) supplier (embedded en product row como FK) -----------------------------

const supplier_name = product_ld?.offers?.seller?.name
    ?? $('h2.fs15').text_sane()
    ?? null;

const supplier_href_raw = $('h2.fs15').closest('a').attr('href')
    || $('a:has(img.c_logo)').attr('href')
    || null;
const supplier_slug = supplier_href_raw
    ?.match(/^https?:\/\/www\.indiamart\.com\/([a-z0-9-]+)\/?(?:\?|$|#)/i)?.[1]
    || null;
const supplier_url_str = supplier_slug
    ? `https://www.indiamart.com/${supplier_slug}/`
    : null;
const supplier_id = supplier_slug;

if (!supplier_id) flags.push('supplier_profile_missing');

// 10) supplier_city: regex sobre title, fallback .verT.fs13 -----------------

let supplier_city = null;
const cityMatch = titleText?.match(/\bin\s+([A-Z][A-Za-z\s]+?)\s*\|/);
if (cityMatch?.[1]) {
    supplier_city = cityMatch[1].trim();
} else {
    const vertText = $('.verT.fs13').text_sane();
    if (vertText) {
        supplier_city = vertText.split(',')[0]?.trim() || null;
    }
}
if (!supplier_city) flags.push('supplier_location_missing');

// supplier_state: NO extraible del detail SSR — flag + null (§4, §6)
const supplier_state = null;
flags.push('supplier_state_from_home_needed');

// supplier_country fijo IN (§4)
const supplier_country = 'IN';

// 11) badges desde HTML crudo (§6) ------------------------------------------

const verified = /Verified\s+Exporter/i.test(raw_html);
const trustseal = /TrustSEAL\s+Verified/i.test(raw_html);

// 12) supplier profile compdtsItems (business_type, member_since_year) ------

const business_type = compdtsValue($, /nature of business/i);
const memberValue = compdtsValue($, /indiamart member since/i);
const member_since_year = memberValue
    ? (parseInt(memberValue.match(/(\d{4})/)?.[1] ?? '', 10) || null)
    : null;

// 13) scraped_date + supplier enrichment pending ---------------------------

const scraped_date = isoDateToday();
flags.push('supplier_enrichment_pending');

// ---------- return product row (§4+§5 completo) -----------------------------

return {
    // §2 strict keys
    product_id,
    product_url: toUrl(product_url_str),
    product_name_clean: nameResult.clean,
    type,
    category_mic,
    category_path,
    price_min_usd: toMoney(price_min_usd_num, 'USD'),
    price_max_usd: toMoney(price_max_usd_num, 'USD'),
    price_unit,
    price_currency,
    moq_quantity,
    moq_unit,
    supplier_id,
    supplier_city,
    scraped_date,

    // §4 additional
    site_code: 'indiamart',
    product_name_original,
    product_description,
    image_primary,
    industry_slug,
    price_raw,
    price_value_raw,
    availability,
    supplier_name,
    supplier_state,
    supplier_country,
    supplier_url: toUrl(supplier_url_str),

    // §5 additional (specs table)
    cas_no,
    grade,
    appearance,
    packaging_type,
    concentration,
    price_normalized_per_kg: toMoney(price_norm_num, 'USD'),

    // §6 supplier fields embedded (FK copy; entidad supplier completa en Stage 3)
    business_type,
    member_since_year,
    verified,
    trustseal,

    // Flags
    scraper_flags: flags,
};
