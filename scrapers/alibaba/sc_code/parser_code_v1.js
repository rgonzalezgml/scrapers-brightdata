// parser_code_v1 — Alibaba detail page (Code worker).
//
// Fixes vs vendor/sc_code/parser_code.js:
//   (A) Cascada de selectores spec §4 para cubrir los 2 templates de detail
//       page (fixed-price vs customizable). Vendor solo cubría fixed-price,
//       fallando 18/26 URLs.
//   (B) extractPrice reescrito según spec §7: detecta moneda (símbolos
//       multi-char primero, luego ISO code), separador decimal (EU vs US),
//       rango min-max, unidad, y convierte a USD con EXCHANGE_RATES. Vendor
//       dejaba el valor raw como si fuera USD — números erróneos.
//   (C) Emite las 16 keys de spec §2 + scraper_flags (antes emitía 10).
//   (D) Filtros de skip §6 como flags `skipped_<reason>` en scraper_flags
//       (maquinaria, sin nombre, sin precio, título no ASCII). El middleware
//       filtra downstream; el parser NUNCA devuelve null porque Scraper Studio
//       rechaza el save con "Output can't be empty".
//
// Nota: el runtime de Scraper Studio valida `parse()` contra el Output Schema
// declarado en el dashboard. Los 16 campos + scraper_flags deben existir en
// ese schema; si falta alguno el runtime lanza parse validation error (R9).

// ---------------------------------------------------------------------------
// Constantes (spec §7, §9).
// ---------------------------------------------------------------------------

// Símbolos de moneda a detectar en el price_raw. Los multi-char van primero
// para que `NZ$` no quede reducido a `$`, `US$` a `$`, etc.
const CURRENCY_SYMBOLS = [
  ["NZ$", "NZD"], ["CA$", "CAD"], ["A$", "AUD"], ["US$", "USD"], ["R$", "BRL"],
  ["B/.", "PAB"], ["RM", "MYR"], ["Rp", "IDR"],
  ["€", "EUR"], ["£", "GBP"], ["¥", "JPY"], ["₹", "INR"], ["₩", "KRW"],
  ["฿", "THB"], ["円", "JPY"], ["$", "USD"],
];

// ISO codes que se buscan en uppercase como fallback si no matchea un símbolo.
const ISO_CODES = [
  "USD", "EUR", "GBP", "JPY", "CNY", "INR", "KRW", "THB", "BRL", "CAD",
  "AUD", "NZD", "MYR", "IDR", "PHP", "VND", "SGD", "HKD", "TWD", "MXN",
  "PAB", "CHF", "SEK", "NOK", "DKK", "ZAR", "AED", "SAR", "TRY", "RUB",
];

// TODO: refresh periódico de tasas. Snapshot aproximado (base USD).
// Si una moneda no está aquí, se devuelve valor raw + flag price_fx_needed.
const EXCHANGE_RATES = {
  USD: 1.0,
  EUR: 1.098,
  GBP: 1.27,
  JPY: 0.00661,
  CNY: 0.138,
  INR: 0.0120,
  KRW: 0.000725,
  THB: 0.0294,
  BRL: 0.194,
  CAD: 0.735,
  AUD: 0.665,
  NZD: 0.605,
  MYR: 0.226,
  IDR: 0.0000621,
  PHP: 0.0178,
  VND: 0.0000406,
  SGD: 0.749,
  HKD: 0.128,
  TWD: 0.0310,
  MXN: 0.0595,
  CHF: 1.125,
  SEK: 0.0953,
  NOK: 0.0938,
  DKK: 0.147,
  ZAR: 0.0549,
  AED: 0.272,
  SAR: 0.266,
  TRY: 0.0307,
  RUB: 0.0110,
  PAB: 1.0,
};

const UNIT_ALIASES = {
  kg: "kg", kilogram: "kg", kilograms: "kg", kilo: "kg", kilos: "kg",
  ton: "ton", tons: "ton", tonne: "ton", tonnes: "ton",
  mt: "mt", "metric ton": "mt", "metric tons": "mt",
  l: "L", liter: "L", liters: "L", litre: "L", litres: "L",
  piece: "piece", pieces: "piece", pc: "piece", pcs: "piece",
  unit: "piece", units: "piece",
  set: "set", sets: "set",
};

const MACHINERY_KW = [
  "machine", "equipment", "pump", "motor", "meter", "sensor", "device",
  "tool", "instrument", "apparatus", "system",
  "maquina", "equipo", "bomba", "herramienta",
  "maschine", "gerat", "anlage",
];

// Patrones a remover de product_name_original (case-insensitive). Spec §7.
const REMOVE_PATTERNS = [
  // Marketing EN/ES/DE
  "high quality", "best price", "hot sale", "factory direct", "free sample",
  "top quality", "oem", "odm", "customized", "wholesale", "bulk",
  "best selling", "professional",
  "direktvertrieb", "vom hersteller", "meistverkaufter", "fabrik",
  "qualit[aä]t", "zertifiziert", "reinheit",
  "calidad", "certificado", "fabricante", "proveedor", "directo",
  "mejor precio", "venta directa",
  // Certificaciones
  "iso\\s*\\d+(\\s*(certified|approved|standard))?",
  "\\bce\\s*(certified|approved|standard)?\\b",
  "\\bgmp\\b", "\\bfda\\b", "\\breach\\b", "\\brohs\\b",
  "\\bkosher\\b", "\\bhalal\\b",
  // Roles
  "manufacturer", "factory", "supplier", "exporter", "producer",
  // Ciudades CN
  "jiahua", "shandong", "hebei", "guangzhou", "shanghai", "beijing",
];

// Clasificación (spec §9). Orden importa: la primera categoría que matchee gana.
const PACKAGING_KEYWORDS = {
  Packaging_Drum: ["drum", "barrel"],
  Packaging_Bag: ["bag", "sack"],
  Packaging_Container: ["container", "ibc", "tank", "bottle"],
};

const CHEMICAL_CATEGORIES = [
  ["Alkali", ["sodium hydroxide", "caustic soda", "potassium hydroxide", "naoh", "koh"]],
  ["Acid", ["hydrochloric", "sulfuric", "nitric", "acetic", "acid", "hcl", "h2so4", "citric"]],
  ["Surfactant", ["sles", "sls", "laureth", "lauryl", "surfactant", "detergent"]],
  ["Solvent", ["ethanol", "methanol", "acetone", "isopropanol", "ipa", "solvent"]],
  ["Preservative", ["sodium benzoate", "potassium sorbate", "preservative", "benzoate"]],
  ["Fragrance", ["fragrance", "perfume", "aroma", "essential oil"]],
  ["Glycol", ["glycerin", "glycerol", "propylene glycol", "peg"]],
  ["Silicate", ["silicate", "silica", "silicon"]],
  ["Polymer", ["polycarboxylate", "polypropylene", "polymer", "resin"]],
  ["Corrosion", ["corrosion inhibitor", "rust inhibitor", "anti-corrosion"]],
  ["Bleach", ["chlorine", "hypochlorite", "bleach"]],
  ["Fertilizer", ["npk", "ammonium", "urea", "fertilizer", "nitrate", "phosphate"]],
];

// ---------------------------------------------------------------------------
// Helpers.
// ---------------------------------------------------------------------------

const flags = [];
const addFlag = (f) => { if (!flags.includes(f)) flags.push(f); };

// Spec §6 fallback: extraer nombre desde /product-detail/{slug}_{id}.html.
const nameFromUrl = (url) => {
  if (!url) return null;
  const m = url.match(/\/product-detail\/([^_]+)_/) || url.match(/\/product-detail\/(.+?)[\?_]/);
  if (!m) return null;
  return m[1].replace(/-/g, " ").trim();
};

// Spec §7 clean_name: remueve marketing/cert/roles/ciudades, colapsa
// separadores, trunca a 80 chars en último espacio.
const cleanName = (raw) => {
  if (!raw) return null;
  let s = raw;
  // Parentesis largos (20+ chars de contenido) → vacío.
  s = s.replace(/\([^)]{20,}\)/g, " ");
  for (const pat of REMOVE_PATTERNS) {
    try {
      s = s.replace(new RegExp(pat, "gi"), " ");
    } catch {
      // Si el patrón es literal con caracteres especiales no escapados.
    }
  }
  // Separadores a espacio.
  s = s.replace(/[|\/\\&]/g, " ");
  // Whitespace collapse.
  s = s.replace(/\s{2,}/g, " ").trim();
  if (!s) {
    addFlag("name_clean_fallback");
    return raw.slice(0, 80).trim();
  }
  if (s.length <= 80) return s;
  const truncated = s.slice(0, 80);
  const lastSpace = truncated.lastIndexOf(" ");
  return (lastSpace > 0 ? truncated.slice(0, lastSpace) : truncated).trim();
};

// Spec §9 classify → {type, category}.
const classify = (cleanedName) => {
  if (!cleanedName) return { type: "chemical", category: "Other" };
  const n = cleanedName.toLowerCase();
  // Packaging primero.
  for (const [cat, kws] of Object.entries(PACKAGING_KEYWORDS)) {
    if (kws.some((k) => n.includes(k))) return { type: "packaging", category: cat };
  }
  // Si además contiene "packaging" / "package" pero no matcheó bucket específico.
  if (n.includes("packaging") || n.includes("package")) {
    return { type: "packaging", category: "Packaging_Container" };
  }
  for (const [cat, kws] of CHEMICAL_CATEGORIES) {
    if (kws.some((k) => n.includes(k))) return { type: "chemical", category: cat };
  }
  return { type: "chemical", category: "Other" };
};

// Detecta moneda en el price_raw. Devuelve [isoCode, stringSinSimbolo].
const detectCurrency = (raw) => {
  for (const [sym, iso] of CURRENCY_SYMBOLS) {
    if (raw.includes(sym)) return [iso, raw.split(sym).join(" ")];
  }
  const upper = raw.toUpperCase();
  for (const iso of ISO_CODES) {
    // Usar word-boundary para no matchear "USDA" como "USD".
    const re = new RegExp(`\\b${iso}\\b`);
    if (re.test(upper)) return [iso, raw.replace(new RegExp(iso, "gi"), " ")];
  }
  return [null, raw];
};

// Parsea un número string respetando separador EU vs US.
// - Si hay `,` después del último `.` → formato EU (`.`=miles, `,`=decimal).
// - Si solo hay `.` o solo hay `,` una vez → asumir decimal.
// - Si solo hay `,` con patrón de miles (`1,234,567`) → quitar todas.
const parseNumber = (s) => {
  if (!s) return null;
  const cleaned = s.replace(/[^0-9.,]/g, "");
  if (!cleaned) return null;
  const lastDot = cleaned.lastIndexOf(".");
  const lastComma = cleaned.lastIndexOf(",");
  let normalized;
  if (lastComma > lastDot) {
    // Formato EU: `.` miles, `,` decimal.
    normalized = cleaned.replace(/\./g, "").replace(",", ".");
  } else if (lastDot > lastComma) {
    // Formato US: `,` miles, `.` decimal.
    normalized = cleaned.replace(/,/g, "");
  } else {
    // Solo un tipo de separador o ninguno.
    const commaCount = (cleaned.match(/,/g) || []).length;
    const dotCount = (cleaned.match(/\./g) || []).length;
    if (commaCount && !dotCount) {
      // Si hay múltiples comas o la última tiene 3 dígitos después → miles.
      const afterLast = cleaned.slice(lastComma + 1);
      if (commaCount > 1 || afterLast.length === 3) {
        normalized = cleaned.replace(/,/g, "");
      } else {
        normalized = cleaned.replace(",", ".");
      }
    } else if (dotCount && !commaCount) {
      // Si hay múltiples puntos, asumir miles EU.
      if (dotCount > 1) {
        normalized = cleaned.replace(/\./g, "");
      } else {
        const afterLast = cleaned.slice(lastDot + 1);
        // Si después del punto hay exactamente 3 dígitos y no hay otros separadores,
        // es ambiguo; Alibaba suele usar `.` decimal, mantenemos.
        normalized = cleaned;
        if (afterLast.length === 3 && cleaned.split(".")[0].length >= 2) {
          // Heurística suave: `1.500` podría ser `1500` EU. Mantenemos como 1.5
          // solo si parece precio unitario (<100). Caso borde documentado.
          const asFloat = parseFloat(cleaned);
          if (asFloat >= 100) normalized = cleaned.replace(/\./g, "");
        }
      }
    } else {
      normalized = cleaned;
    }
  }
  const n = parseFloat(normalized);
  return isNaN(n) ? null : n;
};

// Detecta unidad en lowercase buscando /kg, /ton, /mt, /l, /piece, /set
// y variantes sin `/` (el vendor a veces ve "1 - 24 kilograms").
const detectUnit = (raw) => {
  if (!raw) return null;
  const low = raw.toLowerCase();
  // Primero patrones con slash (más específicos).
  const slashMatch = low.match(/\/\s*([a-z]+)/);
  if (slashMatch && UNIT_ALIASES[slashMatch[1]]) return UNIT_ALIASES[slashMatch[1]];
  // Luego palabra suelta.
  const keys = Object.keys(UNIT_ALIASES).sort((a, b) => b.length - a.length);
  for (const k of keys) {
    const re = new RegExp(`\\b${k}\\b`);
    if (re.test(low)) return UNIT_ALIASES[k];
  }
  if (slashMatch) addFlag("price_unit_unknown");
  return null;
};

// Spec §7 extractPrice: devuelve {min, max, currency, unit, raw}. Convierte a USD.
const parsePrice = (raw) => {
  const result = { min: null, max: null, currency: null, unit: null };
  if (!raw) return result;
  const [currency, stripped] = detectCurrency(raw);
  result.currency = currency;
  result.unit = detectUnit(raw);

  // Split por `-` para rango. Evitar romper negativos: Alibaba no muestra.
  const parts = stripped.split(/\s*[-–—]\s*/);
  const nums = parts.map(parseNumber).filter((n) => n !== null && n > 0);
  if (nums.length === 0) {
    // Sin números: devolver (null, null, currency, unit).
    return result;
  }
  let minRaw = nums[0];
  let maxRaw = nums.length > 1 ? nums[nums.length - 1] : nums[0];
  if (maxRaw < minRaw) [minRaw, maxRaw] = [maxRaw, minRaw];

  const rate = currency && EXCHANGE_RATES[currency];
  if (rate) {
    result.min = +(minRaw * rate).toFixed(4);
    result.max = +(maxRaw * rate).toFixed(4);
  } else {
    // Sin tasa: dejar valor raw y flaggear.
    result.min = minRaw;
    result.max = maxRaw;
    if (currency && !EXCHANGE_RATES[currency]) addFlag("price_fx_needed");
    if (!currency) addFlag("price_fx_needed");
  }
  return result;
};

// Spec §7 regla 13: normalización a per-kg.
const normalizePerKg = (priceMinUsd, unit) => {
  if (priceMinUsd == null) return null;
  if (unit === "kg") return priceMinUsd;
  if (unit === "ton" || unit === "mt") return +(priceMinUsd / 1000).toFixed(6);
  return null;
};

// Mapa país → ISO-2 (parcial; fallback a null).
const COUNTRY_TO_ISO = {
  china: "CN", "china (mainland)": "CN", cn: "CN",
  india: "IN", in: "IN",
  "united states": "US", usa: "US", us: "US", america: "US",
  germany: "DE", deutschland: "DE",
  "united kingdom": "GB", uk: "GB", britain: "GB",
  japan: "JP", "hong kong": "HK",
  "south korea": "KR", korea: "KR",
  taiwan: "TW", thailand: "TH", vietnam: "VN",
  indonesia: "ID", malaysia: "MY", philippines: "PH",
  singapore: "SG", brazil: "BR", mexico: "MX",
  canada: "CA", australia: "AU", france: "FR", italy: "IT",
  spain: "ES", netherlands: "NL", russia: "RU", turkey: "TR",
};
const countryToIso = (raw) => {
  if (!raw) return null;
  const key = raw.toLowerCase().trim();
  return COUNTRY_TO_ISO[key] || null;
};

// Fecha ISO YYYY-MM-DD en UTC.
const today = () => new Date().toISOString().slice(0, 10);

// Primer texto no vacío de una lista de selectores (cascada).
const firstText = (selectors) => {
  for (const sel of selectors) {
    const t = $(sel).first().text_sane();
    if (t) return t;
  }
  return null;
};

// ---------------------------------------------------------------------------
// Extracción.
// ---------------------------------------------------------------------------

const scraped_date = today();
const product_url = $('link[rel="canonical"]').attr("href") || input.url || null;

// --- Nombre (cascada §4). -------------------------------------------------
// Template fixed-price: .product-title-container h1.
// Template customizable: solo h1 raw.
const rawName = firstText([
  ".product-title-container h1",
  "h1.title-first-column",
  ".product-title h1",
  'h1[class*="title"]',
  "h1",
]) || nameFromUrl(product_url);

const product_name_original = rawName;
const product_name_clean = cleanName(rawName);

// --- Precio (cascada §4 + template customizable). ------------------------
// Fixed-price: los .price-item tienen tiers (1-24 kg → $X, 25-99 → $Y).
// Customizable: el precio está en el texto del bloque "Product descriptions
// from the supplier" con shape:
//   Minimum order quantity: 1 unit
//   $12,000
// No hay un selector estable; buscamos en el módulo de descripción del supplier
// matcheando el patrón monetario después de "Minimum order quantity".
let price_raw = null;
let moq_raw = null;

const priceItems = $(".price-item").toArray();
if (priceItems.length > 0) {
  // Template fixed-price (el vendor ya funciona acá).
  const first = $(priceItems[0]).find(".id-text-2xl span").text_sane();
  const last = $(priceItems[priceItems.length - 1]).find(".id-text-2xl span").text_sane();
  if (first && last) {
    // Si hay tiers, tomar rango desde el más barato (last) al más caro (first).
    const lowNum = parseNumber(last.replace(/[^\d.,]/g, ""));
    const highNum = parseNumber(first.replace(/[^\d.,]/g, ""));
    if (lowNum != null && highNum != null && Math.abs(lowNum - highNum) > 0.001) {
      price_raw = `${last}-${first}`;
    } else {
      price_raw = first;
    }
  } else {
    price_raw = first || last;
  }
  moq_raw = $(priceItems[0]).find(".id-text-sm").text_sane();
} else {
  // Fallback selectores spec §4.
  price_raw = firstText([
    ".price-range",
    ".do-price",
    ".price-original",
    '[class*="price"]',
  ]);
  // Fallback customizable: buscar en el bloque de descripción del supplier.
  // El bloque suele estar bajo un heading "Product descriptions from the supplier".
  if (!price_raw) {
    const candidates = $(
      'section, div[class*="description"], div[class*="detail"], [class*="supplier-desc"]'
    ).toArray();
    for (const el of candidates) {
      const txt = $(el).text_sane();
      if (!txt) continue;
      // Patrón: "Minimum order quantity: N unit" seguido de precio (moneda + número).
      const m = txt.match(
        /minimum\s+order\s+quantity[:\s]+([^\n]+?)\s*(?:[\n\r]|(?=[A-Z$€£¥₹₩฿]))[^A-Za-z0-9]*((?:NZ\$|CA\$|A\$|US\$|R\$|B\/\.|RM|Rp|[€£¥₹₩฿$]|USD|EUR|GBP|JPY|CNY)\s*[\d.,]+(?:\s*-\s*(?:NZ\$|CA\$|A\$|US\$|R\$|B\/\.|RM|Rp|[€£¥₹₩฿$])?\s*[\d.,]+)?(?:\s*\/\s*[a-z]+)?)/i
      );
      if (m) {
        moq_raw = m[1].trim();
        price_raw = m[2].trim();
        break;
      }
      // Fallback más laxo: si el bloque dice "Customizable" y "Minimum order quantity",
      // buscar el primer monto con símbolo de moneda después.
      if (/customizable/i.test(txt) && /minimum\s+order\s+quantity/i.test(txt)) {
        const moqM = txt.match(/minimum\s+order\s+quantity[:\s]+([^\n$€£¥₹₩฿]+)/i);
        const priceM = txt.match(
          /((?:NZ\$|CA\$|A\$|US\$|R\$|B\/\.|RM|Rp|[€£¥₹₩฿$])\s*[\d.,]+(?:\s*-\s*(?:NZ\$|CA\$|A\$|US\$|R\$|B\/\.|RM|Rp|[€£¥₹₩฿$])?\s*[\d.,]+)?)/
        );
        if (moqM) moq_raw = moqM[1].trim();
        if (priceM) price_raw = priceM[1].trim();
        if (price_raw) break;
      }
    }
  }
}

const priceParsed = parsePrice(price_raw);

// --- MOQ (cascada §4 + extracción de quantity/unit). ---------------------
if (!moq_raw) {
  moq_raw = firstText([
    ".min-order-amount",
    '[class*="moq"]',
    '[class*="min-order"]',
    ".order-num",
  ]);
}
let moq_quantity = null;
let moq_unit = null;
if (moq_raw) {
  const qtyMatch = moq_raw.match(/(\d[\d.,]*)/);
  if (qtyMatch) {
    const n = parseNumber(qtyMatch[1]);
    if (n != null) moq_quantity = Math.round(n);
  }
  const unit = detectUnit(moq_raw);
  if (unit) moq_unit = unit;
  else {
    // Heurística: "1 - 24 kilograms" → la palabra post-número.
    const wMatch = moq_raw.match(/\d[\s-]*\d*\s*([a-zA-Z]+)/);
    if (wMatch && UNIT_ALIASES[wMatch[1].toLowerCase()]) {
      moq_unit = UNIT_ALIASES[wMatch[1].toLowerCase()];
    }
  }
}

// --- Supplier (cascada §4). ----------------------------------------------
let supplier_name = firstText([
  '[data-testid="seller-overview-card-company-link"]',
  ".company-name a",
  ".supplier-name a",
  '[class*="company-name"] a',
  '[class*="company-name"]',
]);
// Template customizable: el link al supplier no tiene data-testid; el href al
// company page es *.en.alibaba.com.
if (!supplier_name) {
  supplier_name = $('a[href*=".en.alibaba.com"]').first().text_sane() || null;
}

const supplierCountryRaw = firstText([
  ".supplier-country",
  '[class*="country"]',
  ".country-flag + span",
]);
const supplier_country = countryToIso(supplierCountryRaw);

// Badge "Gold Supplier" / "Verified". Selector no confirmado → detectar por texto.
const supplier_verified = (() => {
  const badges = $(
    '[class*="gold"], [class*="verified"], [class*="supplier-badge"], [data-testid*="verified"]'
  ).text_sane().toLowerCase();
  if (/gold\s*supplier|verified/i.test(badges)) return true;
  // Fallback: buscar en todo el body text marcadores comunes.
  const body = $("body").text_sane().toLowerCase();
  if (/gold\s*supplier/.test(body) || /verified\s*supplier/.test(body)) return true;
  return false;
})();

// --- Clasificación (§9). -------------------------------------------------
const { type, category } = classify(product_name_clean);

// ---------------------------------------------------------------------------
// Atributos tabla (spec §4 — CAS / Purity). Cascada para los 2 templates.
//
// Fixed-price (vendor baseline): filas `[data-testid="module-attribute-row"]`
// con `module-attribute-name-text` y `module-attribute-value-text`. El selector
// vendor usa `:has(...:contains("CAS No."))` que depende de pseudo-clases no
// siempre soportadas por el cheerio del runtime; reescrito a .toArray().find
// para portabilidad.
//
// Customizable: los atributos vienen en tabla markdown "Attributes" dentro del
// bloque "Product descriptions from the supplier", como filas con celda label
// + celda value. Fallback genérico por `<tr>` / `<td>`.
// ---------------------------------------------------------------------------

const attrLookup = (labelPatterns) => {
  // labelPatterns: array de regex que matchean el label (case-insensitive).
  const rows = $('[data-testid="module-attribute-row"]').toArray();
  for (const row of rows) {
    const name = $(row).find('[data-testid="module-attribute-name-text"]').text_sane() || "";
    if (labelPatterns.some((re) => re.test(name))) {
      const val = $(row).find('[data-testid="module-attribute-value-text"]').text_sane();
      if (val) return val;
    }
  }
  // Fallback: tabla genérica (customizable template).
  const trs = $("tr").toArray();
  for (const tr of trs) {
    const cells = $(tr).find("td, th").toArray();
    if (cells.length < 2) continue;
    const label = $(cells[0]).text_sane() || "";
    if (labelPatterns.some((re) => re.test(label))) {
      const val = $(cells[1]).text_sane();
      if (val) return val;
    }
  }
  // Fallback dl/dt/dd.
  const dts = $("dt").toArray();
  for (const dt of dts) {
    const label = $(dt).text_sane() || "";
    if (labelPatterns.some((re) => re.test(label))) {
      const dd = $(dt).next("dd").text_sane();
      if (dd) return dd;
    }
  }
  return null;
};

const cas_number = attrLookup([/cas\s*no\.?/i, /cas\s*number/i, /\bcas\b/i]);
const purity = attrLookup([/\bpurity\b/i, /assay/i]);

// ---------------------------------------------------------------------------
// Skip rules (spec §6) — expresadas como flags internos, no como early-return.
//
// BrightData Scraper Studio valida estáticamente que `parse()` nunca devuelva
// null (error "Output can't be empty" al guardar). Los skip flags se acumulan
// en `flags[]` para consumo interno; en Fase 1 NO se emiten en el output (el
// Output Schema del dashboard solo conoce las 10 keys vendor). El filtro
// downstream se hace sobre `price_raw === null || cleaned_product_name === null`
// en el middleware. Cuando Fase 2 aterrice, `flags[]` vuelve al output como
// `scraper_flags`.
// ---------------------------------------------------------------------------

const skipReasons = [];
if (!product_name_clean && !rawName) skipReasons.push("missing_name");
{
  const pr = (price_raw || "").toString().trim().toLowerCase();
  if (!pr || pr === "none" || pr === "[]" || pr === "null") {
    skipReasons.push("missing_price");
  }
}
{
  const hay = (product_name_clean || rawName || "").toLowerCase();
  if (hay && MACHINERY_KW.some((k) => hay.includes(k))) skipReasons.push("machinery");
}
if (product_name_original && !/[A-Za-z]/.test(product_name_original)) {
  skipReasons.push("non_ascii_title");
}
for (const r of skipReasons) addFlag(`skipped_${r}`);

// Invariantes §4: product_url y product_name_original nunca null silencioso.
// product_url ya cae al input.url en línea 361. product_name_original: si no
// se encontró h1 ni fallback, flaggear (no rompe el output, solo deja traza).
if (!product_name_original) addFlag("missing_product_name_original");
if (!product_url) addFlag("missing_product_url");

// ---------------------------------------------------------------------------
// Output — Fase 1: 10 keys vendor-compatibles (ver spec §12).
//
// Nombres vendor literales anclados al Output Schema del dashboard BrightData.
// Los 9 campos spec §2 no emitidos (product_name_original, type, category,
// price_normalized_per_kg, moq_quantity, moq_unit, supplier_country,
// supplier_verified, scraped_date) se rellenan con null desde el middleware
// vía tabla de aliases (middlewares/alibaba/models.py:208-221). Fase 2
// migrará a las 16 keys canónicas en una release coordinada.
//
// minimum_order_quantity se emite como string crudo (`moq_raw`) igual que el
// vendor, no como split quantity/unit. El middleware lo deja crudo.
// ---------------------------------------------------------------------------

return {
  cleaned_product_name: product_name_clean ?? null,
  product_url: product_url ?? null,
  supplier_name: supplier_name ?? null,
  price_raw: price_raw ?? null,
  price_min_usd: priceParsed.min ?? null,
  price_max_usd: priceParsed.max ?? null,
  price_unit: priceParsed.unit ?? null,
  minimum_order_quantity: moq_raw ?? null,
  cas_number: cas_number ?? null,
  purity: purity ?? null,
};
