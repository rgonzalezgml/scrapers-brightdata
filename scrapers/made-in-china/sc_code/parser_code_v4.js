// parser_code_v3.js — Code worker made-in-china
// Iteración v3. Restaura wrappers del Output Schema de BD Studio sobre la base de v2.
//
// Contexto del cambio (2026-04-21):
// El parser v2 emitía tipos JS puros (string / Number) en los campos `url`, `product_url`,
// `supplier_url`, `price_min_usd`, `price_max_usd`, `price_normalized_per_kg`. El Output
// Schema declarado en BD Studio exige tipos semánticos:
//   - url / product_url / supplier_url → URL  (no Text)
//   - price_min_usd / price_max_usd / price_normalized_per_kg → Price/Money  (no Number)
// La UI rechazaba cada run con "Expected URL, Actual Text" / "Expected Price/Money,
// Actual Number". Los errores E5 (new URL) y E6 (new Money) del errors.md estaban mal
// diagnosticados — NO eran bugs, eran requisitos del schema. Restaurados aquí.
//
// Diff semántico vs v2:
// - Restaurados de vendor por requisito de schema BD: `new URL(value)` para todos los
//   campos URL; `new Money(numericValue, currency)` para todos los campos Price/Money
//   (wrappers vienen expuestos como globals del runtime de BD Studio — ver skill
//   scraper-implementation sec. 4 "Constructores").
// - Alineado al §2 corregido del spec: nombres largos (`product_url`, `product_name_clean`,
//   `supplier_name`, `supplier_url`, etc.) y superset completo (29 campos product + 14
//   supplier). Reorden de claves del return para matchear el orden del array §2.
// - Eliminado el `__entity` marker: §2 no lo declara. El branching ya está resuelto por el
//   pathname de input.url (isProductDetail); el parser devuelve el shape correspondiente
//   y el interaction no necesita saber cuál es. El interaction v2 ya hace `collect(data)`
//   sin inspeccionar __entity, así que este cambio no rompe nada downstream.
// - Eliminado el campo extra `url` que v2 devolvía en la rama product (duplicaba
//   `product_url`); §2 del product NO lo tiene.
//
// Errores vigentes preservados de v2 (no regresión):
// - E1 category_mic/path breadcrumb DOM `.sr-QPWords-cont a` (JSON-LD BreadcrumbList vacío).
// - E2 price_unit del priceText con regex, no del MOQ.
// - E3 mapa COUNTRY_ISO + flag country_iso_unknown (solo rama supplier).
// - E4 texto literal "Audited Supplier" en sign-items/bsc-items.
// - E7 business_type combinando todos los sign-items con regex.
// - E8 branching product vs supplier por `/product/` en URL, entidades separadas.
// - E13 product_name_original = JSON-LD.name con fallback `.sr-proMainInfo-baseInfoH1`.
// - E14 supplier_country SOLO en rama supplier home.
// - E15 MOQ con `.sa-only-property-price` simple + regex spec §7.
// - E16 JSON-LD Product como fuente autoritaria; DOM fallback/complemento.
//
// Errores reclasificados como false positive en errors.md (ver bloque corrección 2026-04-21):
// - E5 `new URL(value)` — requerido por schema BD, RESTAURADO aquí.
// - E6 `new Money(value, 'USD')` — requerido por schema BD, RESTAURADO aquí.
//
// Reglas duras: sin try/catch (R7) — único aceptado: JSON.parse del loop JSON-LD.
// `parse()` sin args (R9). `text_sane` (R11). `toArray().map` (R12).
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
    // Único try/catch aceptado (R7): JSON.parse del loop de JSON-LD.
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
    s = s.replace(/\s+/g, ' ').trim();
    s = s.replace(/\b(high quality|best price|factory direct|hot sale|free sample|top quality|oem\s*odm|customized|wholesale|bulk|best selling|china manufacturer|supplier direct)\b/gi, ' ');
    s = s.replace(/\b(ISO\d+|CE|GMP|FDA|REACH|RoHS|Kosher|Halal|Certified|Approved)\b/gi, ' ');
    s = s.replace(/\b(Shandong|Hebei|Guangzhou|Shanghai|Beijing|Weihai|Wuhan)\b/gi, ' ');
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

function parsePriceRange(priceText) {
    if (!priceText) return { min: null, max: null, unit: null };
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

// Wrappers del schema BD — centralizados para consistencia y para documentar la intención.
function toUrl(value) {
    // `url: URL` del Output Schema de BD Studio. El constructor global URL del runtime
    // de BD serializa al tipo URL. Si `value` es falsy, null (URL opcional).
    if (!value) return null;
    return new URL(value);
}

function toMoney(value, currency) {
    // `price_*: Price/Money` del Output Schema. Constructor global Money del runtime BD.
    // Devuelve null si no hay valor numérico válido.
    if (value == null || Number.isNaN(Number(value))) return null;
    return new Money(Number(value), currency || 'USD');
}

// ---------- branching ----------

const urlRaw = String(input.url || '');
const isProductDetail = /\/product\//.test(urlRaw);

const lds = parseJsonLdBlocks($);
const scraped_date = isoDateToday();

// ========== RAMA PRODUCT ==========
if (isProductDetail) {
    const flags = [];

    const product = lds.find(x => x?.['@type'] === 'Product') ?? null;
    if (!product) flags.push('jsonld_parse_fallback');

    const product_id = urlRaw.match(/\/product\/([^\/]+)\//)?.[1] ?? null;
    const sku = product?.sku ?? product_id;
    const supplier_id = supplierIdFromUrl(urlRaw);

    // breadcrumb DOM (E1, E16) — JSON-LD BreadcrumbList vacío en fixture real
    const breadcrumbItems = $('.sr-QPWords-cont a').toArray()
        .map(el => $(el).text_sane())
        .filter(Boolean);
    const category_path = breadcrumbItems.filter(t => t.toLowerCase() !== 'home');
    const category_mic = category_path.length ? category_path[category_path.length - 1] : null;

    const type = TYPE_BY_PATH0[category_path[0]] ?? 'other';

    // name (E13, E16) — JSON-LD primary, DOM fallback sin clase inexistente J-baseInfo-name
    const product_name_original = product?.name ?? $('.sr-proMainInfo-baseInfoH1').text_sane() ?? null;
    const nameResult = cleanName(product_name_original);
    if (nameResult.fallback) flags.push('name_clean_fallback');

    // precio: DOM raw + JSON-LD currency (E2 — unit del priceText, no del MOQ)
    const price_raw = $('.only-one-priceNum-td-left').text_sane() ?? null;
    const priceParsed = parsePriceRange(price_raw);
    const offers = product?.offers ?? null;
    const price_currency = offers?.priceCurrency ?? 'USD';
    const jsonldPriceMin = offers?.price ? parseFloat(offers.price) : null;
    const priceMinNum = priceParsed.min ?? jsonldPriceMin ?? null;
    const priceMaxNum = priceParsed.max ?? jsonldPriceMin ?? null;
    const price_unit = priceParsed.unit ?? null;
    if (price_currency !== 'USD') flags.push('price_fx_needed');
    if (!price_unit) flags.push('price_unit_unknown');

    const priceNormNum = normalizePerKg(priceMinNum, price_unit);

    // MOQ (E15) — selector sin segunda clase inexistente
    const moq_raw = $('.sa-only-property-price').text_sane() ?? null;
    const moq = parseMoq(moq_raw);

    const image_primary = pickImage(product?.image);

    // specs técnicas vía additionalProperty
    const props = addPropMap(product?.additionalProperty);
    const cas_no = props['cas no.'] ?? props['cas no'] ?? props['cas'] ?? null;
    const grade = props['quality'] ?? props['grade'] ?? props['grade standard'] ?? null;
    const appearance = props['appearance'] ?? null;
    const formula = props['formula'] ?? props['molecular formula'] ?? null;
    const einecs = props['einecs'] ?? props['einecs no.'] ?? null;
    const origin_country = props['origin country'] ?? props['country of origin'] ?? null;

    const supplier_name_raw = product?.brand?.name ?? null;

    const rating_avg = product?.aggregateRating?.ratingValue != null
        ? parseFloat(product.aggregateRating.ratingValue)
        : null;
    const ratingAuthor = product?.aggregateRating?.author ?? product?.review?.author?.name ?? null;
    if (rating_avg === 5 && String(ratingAuthor).toUpperCase().includes('MIC_BUYER')) {
        flags.push('rating_synthetic');
    }

    // Shape product = §2 corregido (29 campos, nombres largos, orden exacto del array).
    return {
        product_id,
        sku,
        site_code: 'made-in-china',
        product_url: toUrl(urlRaw),                          // URL (E5 restaurado)
        product_name_original,
        product_name_clean: nameResult.clean,
        type,
        category_mic,
        category_path,
        price_raw,
        price_currency,
        price_min_usd: toMoney(priceMinNum, price_currency), // Price/Money (E6 restaurado)
        price_max_usd: toMoney(priceMaxNum, price_currency), // Price/Money (E6 restaurado)
        price_unit,
        price_normalized_per_kg: toMoney(priceNormNum, price_currency), // Price/Money
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
// input.url es https://{slug}.en.made-in-china.com/ o similar sin /product/.
{
    const flags = [];
    const supplier_id = supplierIdFromUrl(urlRaw);

    // name: Organization JSON-LD si existe, sino og:site_name o <title>
    const org = lds.find(x => x?.['@type'] === 'Organization' || x?.['@type'] === 'Corporation') ?? null;
    const supplier_name = org?.name
        ?? $('meta[property="og:site_name"]').attr('content')
        ?? $('title').text_sane()
        ?? null;

    // country (E14 — solo rama supplier; E3 — mapa ISO-2)
    const addressText = $('.info-item').toArray()
        .map(el => $(el).text_sane())
        .find(t => /address/i.test(t)) ?? null;
    const addrTail = addressText ? addressText.split(/[,:]/).map(s => s.trim()).filter(Boolean).pop() : null;
    const country_name = addrTail ?? null;
    const supplier_country = country_name ? (COUNTRY_ISO[country_name] ?? null) : null;
    if (country_name && !supplier_country) flags.push('country_iso_unknown');

    // business_type (E7) — combina sign-items relevantes
    const businessTypes = $('.sr-comInfo-sign .sign-item, .sign-item, .bsc-item').toArray()
        .map(el => $(el).text_sane())
        .filter(t => /Manufacturer|Trader|Exporter|Importer|Retailer|Wholesaler|Factory|Trading\s*Company/i.test(t));
    const business_type = businessTypes.length ? Array.from(new Set(businessTypes)).join(' ') : null;

    // profile fields
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
    const year_established = yoeRaw ? (parseInt(yoeRaw.match(/\d{4}/)?.[0] ?? '', 10) || null) : null;
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

    // management certs
    const certText = $('.sign-item, .bsc-item, .certification, .cert-item').toArray()
        .map(el => $(el).text_sane())
        .join(' ');
    const management_certifications = Array.from(
        new Set((certText.match(/ISO\s*\d{4,5}|GMP|HACCP|FDA|CE|REACH|RoHS|Kosher|Halal/gi) ?? [])
            .map(s => s.replace(/\s+/g, '').toUpperCase()))
    );

    // Shape supplier = §2 corregido (14 campos, nombres largos, orden exacto del array).
    return {
        supplier_id,
        supplier_url: toUrl(urlRaw),                         // URL (E5 restaurado)
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
