// parser_code_v8 — Alibaba detail page (Code worker).
//
// Fix v8.3:
//   (price_raw) price_raw debe ser siempre texto original del DOM, sin construir.
//       priceFromJsonLd() construía strings sintéticos ("USD20-USD25") que no
//       reflejan el texto visible en la página. Fix: reemplazar por scanJsonLd()
//       que retorna valores ya parseados {min, max, currency}. La cascada DOM
//       P1–P6 corre primero y popula price_raw + llama parsePrice(). Si DOM no
//       encuentra precio (hydration timeout), scanJsonLd() corre como P7 y
//       asigna priceParsed directamente — price_raw queda null. Elimina
//       priceFromJsonLd(); priceFromLadder y demás estrategias sin cambios.
//
// Fix v8.2:
//   (P0) JSON-LD single-price aplana ladder — cuando el JSON-LD solo tiene
//       `price: "20"` (tier mínimo), P0 disparaba primero y bloqueaba P1
//       (.price-item) que sí leía el rango completo del DOM (20–25).
//       Supersedido por v8.3 que mueve JSON-LD completo al final.
//
// Fix v8.1 (post-run 08):
//   (P0/FB4) JSON-LD array top-level — priceFromJsonLd() y FB4 usaban
//       `data['@graph'] ? data['@graph'] : [data]`, que falla cuando
//       `data` es un JSON array (typeof object, pero sin clave @graph).
//       Fix: `Array.isArray(data) ? data : (data['@graph'] ? ...)`.
//       Causa del parse error "Cannot read properties of null (reading 'price_raw')"
//       en run 08 para páginas cuyo JSON-LD es un array top-level.
//
// Cambios sobre parser_code_v7.js (delta v8):
//
//   (P0) Nueva estrategia JSON-LD — INSERTAR AL INICIO DE LA CASCADA.
//       El 41% de filas con price_raw=null en v7 (run 07-alibaba_20260507_195655.json,
//       180/439 URLs) tienen el h1 presente pero ninguna de las estrategias P1–P6
//       extrae precio. Hipótesis confirmada: Alibaba incluye <script type="application/ld+json">
//       en el HTML inicial (pre-hidratación React) con el nodo Product/offers que contiene
//       lowPrice/highPrice/price y priceCurrency. Esta fuente es más robusta que el DOM
//       dinámico porque no depende de que React hidrate los componentes de precio.
//       Soporta tanto objeto directo como @graph array. El precio construido sigue el
//       patrón CUR+low–CUR+high (ej "USD1.20-USD2.50") para que detectCurrency() lo
//       procese correctamente en parsePrice().
//       Flag: price_source_P0_jsonld.
//
//   (FB4-FB6) Nuevos fallbacks de supplier_name:
//       FB4 — JSON-LD brand/seller/manufacturer: si los 3 fallbacks de supplier en v7
//             fallan, escanear los mismos <script type="application/ld+json"> buscando
//             brand.name, seller.name o manufacturer.name. Flag: supplier_source_jsonld.
//       FB5 — meta og:site_name: si no hay nombre de empresa y el og:site_name no contiene
//             "alibaba" (es decir, viene del supplier, no de la plataforma). Flag: supplier_source_og.
//       FB6 — data-testid broad net: selectores [data-testid*="seller"],
//             [data-testid*="company-name"], [data-testid*="supplier-name"] excluyendo
//             el selector exacto ya cubierto en la cascada primaria.
//
//   (FLAG) Nuevo flag rfc_only_page / hydration_timeout.
//       Cuando price_raw sigue null tras todas las estrategias, distingue dos causas:
//         • supplier_name encontrado → precio oculto/RFQ, flag 'rfc_only_page'.
//         • supplier_name también null → timeout de hidratación React, flag 'hydration_timeout'.
//
// Fixes heredados de parser_code_v7.js:
//
//   (R-v6) Regresión de cascada bloqueada por `.price-item` presente pero vacío.
//       En v6, todos los fallbacks de precio (P2 range-spans, P3 CSS, P4 MOQ-body,
//       P5 tiered-body, P6 body-full) vivían dentro del `else` del bloque
//       `if (priceItems.length > 0)`. Resultado: cuando `.price-item` existe
//       pero `.id-text-2xl span` y el split-decimal de C7 retornan null,
//       `price_raw` queda null y la cascada se detiene. 52 URLs que tenían
//       precio en v1 pasaron a entregar null en v6.
//
//       Fix: refactorizar toda la extracción de precio en 6 funciones
//       independientes (P1–P6) y ejecutarlas en cascada — el primer resultado
//       no-null gana. La presencia de `.price-item` ya NO bloquea P2–P6.
//
// Fixes heredados de parser_code_v6.js:
//
//   (C7) Template ladder-price: .price-item con split-decimal spans
//       El branch .price-item usaba ".id-text-2xl span" para leer el precio
//       dentro de cada tier. Alibaba ahora usa "id-text-[28px]" (clase Tailwind
//       arbitraria) con el mismo patrón split-decimal de range-price — sin punto
//       decimal en el DOM. Fix: helper priceFromItem() que intenta primero el
//       selector legacy ".id-text-2xl span" y cae en reconstrucción de spans
//       desde 'div[class*="whitespace-pre"] span' si no lo encuentra.
//
// Fixes heredados de parser_code_v4.js:
//
//   (C6) Template range-price split-decimal [spec §4c]
//       Alibaba renderiza algunos precios en el header del producto con
//       [data-testid="range-price"]. El precio visual "$6.98-$17.70" está
//       partido en spans sin punto decimal:
//         <span>$</span><span>6</span><span>98</span>-<span>17</span><span>70</span>
//       text_sane() devuelve "$698-1770" (incorrecto). Fix: intentar
//       [data-testid="range-price"] como estrategia P2 antes de los fallbacks
//       de texto. Se recolectan los spans, se reconstruye el precio insertando
//       el punto decimal entre el integer y el decimal de cada parte.
//
//   (C2+C3) CURRENCY_RE ampliada [spec §4b, §8]
//       La CURRENCY_RE local del bloque tiered-price (E1) solo cubría prefijo
//       con símbolo simple. V5 amplía:
//         - Añade SEK, DKK, RSD como prefijo
//         - Añade 円 al charset de símbolos de prefijo
//         - Añade segunda alternativa sufijo: [\d.,]+\s*(TL|TRY|SEK|DKK|RSD|円|€)
//         - Flag gi para case-insensitive (cubre "tl", "try" en texto)
//       CURRENCY_SYMBOLS también recibe SEK, DKK, RSD, TL (→TRY) para que
//       detectCurrency() los identifique en price_raw.
//
//   (C1+C4) Strip RTL + body fallback [spec §4b F1, F4]
//       El selector 'section, div[class*="description"], ...' no matchea el
//       contenedor real en ninguna de las 105 URLs con precio NULL (análisis
//       2026-05-05). Fix: si el loop de tieredCandidates no produce precio,
//       hacer fallback a $('body').text_sane() completo; antes de aplicar
//       CURRENCY_RE, remover caracteres de control RTL Unicode (UI hebrea de
//       Alibaba). El encabezado de sección ("Product descriptions from the
//       supplier" y equivalentes en chino/turco/hebreo) se usa como ancla para
//       acotar la búsqueda a 2000 chars; si no se encuentra, usar los últimos
//       3000 chars del body.
//
//   (C5) Formato lakh indio en parseNumber [spec §4b]
//       "1,55,448" (lakh indio) se parseaba como 1.55 porque la rama EU-format
//       solo reemplazaba la primera coma con punto. Fix: si hay más de una coma
//       en el string (múltiples comas = miles repetidos o lakh), tratar todas
//       como separadores de miles y removerlas; solo si hay exactamente una
//       coma aplicar la lógica EU decimal.
//
// Todos los demás comportamientos son idénticos a v7.

// ---------------------------------------------------------------------------
// Constantes (spec §7, §9).
// ---------------------------------------------------------------------------

// Símbolos de moneda a detectar en el price_raw. Los multi-char van primero
// para que `NZ$` no quede reducido a `$`, `US$` a `$`, etc.
// v5 añade: SEK, DKK, RSD, TL (→TRY) ANTES de "$" para que no queden tapados.
const CURRENCY_SYMBOLS = [
    ["NZ$", "NZD"], ["CA$", "CAD"], ["A$", "AUD"], ["US$", "USD"], ["R$", "BRL"],
    ["B/.", "PAB"], ["RM", "MYR"], ["Rp", "IDR"],
    ["SEK", "SEK"], ["DKK", "DKK"], ["RSD", "RSD"], ["TL", "TRY"],
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
// v5 fix C5: en la rama EU (lastComma > lastDot), si hay múltiples comas
// (formato lakh indio: 1,55,448) tratar todas como separadores de miles
// en lugar de intentar convertir la última en punto decimal.
const parseNumber = (s) => {
    if (!s) return null;
    const cleaned = s.replace(/[^0-9.,]/g, "");
    if (!cleaned) return null;
    const lastDot = cleaned.lastIndexOf(".");
    const lastComma = cleaned.lastIndexOf(",");
    let normalized;
    if (lastComma > lastDot) {
        // Formato EU: `.` miles, `,` decimal — PERO si hay múltiples comas
        // es formato lakh indio (1,55,448) o miles repetidos; en ese caso
        // remover todas las comas (no decimal).
        const commaCount = (cleaned.match(/,/g) || []).length;
        if (commaCount > 1) {
            // Múltiples comas → lakh indio o miles repetidos; tratar todas
            // como separadores de miles.
            normalized = cleaned.replace(/,/g, "");
        } else {
            // Una sola coma al final → formato EU decimal.
            normalized = cleaned.replace(/\./g, "").replace(",", ".");
        }
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

// --- Precio (cascada P0–P6). ----------------------------------------------
//
// v8: añade P0 (JSON-LD) al inicio de la cascada. El resto de estrategias P1–P6
// permanecen sin cambios respecto a v7.
//
// CURRENCY_RE compartida entre P5 y P6.
const CURRENCY_RE_SHARED = /(NZ\$|CA\$|A\$|US\$|R\$|B\/\.|RM|Rp|SEK|DKK|RSD|[€£¥₹₩฿$円])\s*[\d.,]+|[\d.,]+\s*(TL|TRY|SEK|DKK|RSD|円|€)/gi;
const MOQ_RE_SHARED = /([\d,]+)\s*(?:-\s*[\d,]+)?\s*(kilogram|kilograms|kg|ton|tons|tonne|tonnes|piece|pieces|unit|units|liter|liters|litre|litres)/i;

// scanJsonLd — escanea todos los <script type="application/ld+json"> y retorna
//   el mejor resultado de precio encontrado: {min, max, currency, unit, needsFx}.
//   Prefiere rango (lowPrice ≠ highPrice) sobre precio único.
//   Solo se usa como fallback P7 cuando la cascada DOM (P1–P6) no encuentra precio.
//   price_raw queda null — los valores se asignan directamente a priceParsed.
//   Soporta array top-level, @graph object, o nodo directo.
const scanJsonLd = () => {
    const scripts = $('script[type="application/ld+json"]').toArray();
    let best = null;
    for (const script of scripts) {
        try {
            const raw = $(script).html() || '';
            const data = JSON.parse(raw);
            const nodes = Array.isArray(data) ? data : (data['@graph'] ? data['@graph'] : [data]);
            for (const node of nodes) {
                if (!node || typeof node !== 'object') continue;
                const offers = node.offers;
                if (!offers) continue;
                const low = parseFloat(offers.lowPrice ?? offers.price);
                const high = parseFloat(offers.highPrice ?? offers.price);
                const cur = (offers.priceCurrency || 'USD').toUpperCase();
                if (isNaN(low) || low <= 0) continue;
                const hiVal = (!isNaN(high) && high > low) ? high : low;
                const isRange = hiVal > low;
                const rate = EXCHANGE_RATES[cur];
                const candidate = {
                    min: rate ? +(low * rate).toFixed(4) : low,
                    max: rate ? +(hiVal * rate).toFixed(4) : hiVal,
                    currency: cur,
                    unit: null,
                    needsFx: !rate,
                    isRange,
                    rawLow: low,
                    rawHigh: hiVal,
                    rawCur: cur,
                };
                if (!best || (isRange && !best.isRange)) best = candidate;
                if (best && best.isRange) break;
            }
        } catch (_) { }
        if (best && best.isRange) break;
    }
    return best;
};

// P1 — .price-item con .id-text-2xl span (v1 baseline) y fallback C7
//      split-decimal. Recibe el array de elementos .price-item.
//      Retorna {price_raw, moq_raw} o {price_raw: null, moq_raw: null}.
const priceFromLadder = (items) => {
    // Helper C7: intenta el selector legacy primero; si falla, reconstruye
    // desde spans split-decimal (Tailwind arbitrary class "id-text-[28px]").
    const priceFromItem = (el) => {
        const old = $(el).find(".id-text-2xl span").text_sane();
        if (old) return old;
        const spans = $(el).find('div[class*="whitespace-pre"] span').toArray()
            .map(s => $(s).text().trim()).filter(Boolean);
        if (spans.length >= 3) return `${spans[0]}${spans[1]}.${spans[2]}`;
        return null;
    };

    const first = priceFromItem(items[0]);
    const last = priceFromItem(items[items.length - 1]);

    let pr = null;
    if (first && last) {
        const lowNum = parseNumber(last.replace(/[^\d.,]/g, ""));
        const highNum = parseNumber(first.replace(/[^\d.,]/g, ""));
        if (lowNum != null && highNum != null && Math.abs(lowNum - highNum) > 0.001) {
            pr = `${last}-${first}`;
        } else {
            pr = first;
        }
    } else {
        pr = first || last;
    }

    const mq = $(items[0]).find(".id-text-sm").text_sane() || null;

    if (pr) {
        addFlag("price_source_P1");
        return { price_raw: pr, moq_raw: mq };
    }
    return { price_raw: null, moq_raw: null };
};

// P2 — [data-testid="range-price"] split-decimal (C6).
//      Retorna {price_raw, moq_raw} o {price_raw: null, moq_raw: null}.
const priceFromRangeSpans = () => {
    const rpEl = $('[data-testid="range-price"]');
    if (!rpEl.length) return { price_raw: null, moq_raw: null };

    const spans = rpEl.find('span').toArray()
        .map(s => $(s).text().trim())
        .filter(Boolean);
    // spans = ['$','6','98','17','70'] (rango) o ['$','6','98'] (único).
    if (spans.length < 3) return { price_raw: null, moq_raw: null };

    const [sym, int1, dec1, int2, dec2] = spans;
    const pr = spans.length >= 5
        ? `${sym}${int1}.${dec1}-${sym}${int2}.${dec2}`
        : `${sym}${int1}.${dec1}`;

    const moqText = rpEl.find('[class*="text-sm"]').first().text_sane() || null;

    addFlag("price_source_P2");
    return { price_raw: pr, moq_raw: moqText };
};

// P3 — selectores CSS simples (spec §4 fallback).
//      Retorna {price_raw, moq_raw} o {price_raw: null, moq_raw: null}.
const priceFromCSS = () => {
    const p = firstText([".price-range", ".do-price", ".price-original", '[class*="price"]']);
    if (!p) return { price_raw: null, moq_raw: null };
    addFlag("price_source_P3");
    return { price_raw: p, moq_raw: null };
};

// P4 — body "minimum order quantity" anchor (customizable template v1).
//      Recibe el array de elementos candidatos.
//      Retorna {price_raw, moq_raw} o {price_raw: null, moq_raw: null}.
const priceFromBodyMOQ = (candidates) => {
    for (const el of candidates) {
        const txt = $(el).text_sane();
        if (!txt) continue;
        // Patrón: "Minimum order quantity: N unit" seguido de precio (moneda + número).
        const m = txt.match(
            /minimum\s+order\s+quantity[:\s]+([^\n]+?)\s*(?:[\n\r]|(?=[A-Z$€£¥₹₩฿]))[^A-Za-z0-9]*((?:NZ\$|CA\$|A\$|US\$|R\$|B\/\.|RM|Rp|[€£¥₹₩฿$]|USD|EUR|GBP|JPY|CNY)\s*[\d.,]+(?:\s*-\s*(?:NZ\$|CA\$|A\$|US\$|R\$|B\/\.|RM|Rp|[€£¥₹₩฿$])?\s*[\d.,]+)?(?:\s*\/\s*[a-z]+)?)/i
        );
        if (m) {
            addFlag("price_source_P4");
            return { price_raw: m[2].trim(), moq_raw: m[1].trim() };
        }
        // Fallback más laxo: si el bloque dice "Customizable" y "Minimum order quantity",
        // buscar el primer monto con símbolo de moneda después.
        if (/customizable/i.test(txt) && /minimum\s+order\s+quantity/i.test(txt)) {
            const moqM = txt.match(/minimum\s+order\s+quantity[:\s]+([^\n$€£¥₹₩฿]+)/i);
            const priceM = txt.match(
                /((?:NZ\$|CA\$|A\$|US\$|R\$|B\/\.|RM|Rp|[€£¥₹₩฿$])\s*[\d.,]+(?:\s*-\s*(?:NZ\$|CA\$|A\$|US\$|R\$|B\/\.|RM|Rp|[€£¥₹₩฿$])?\s*[\d.,]+)?)/
            );
            if (priceM) {
                addFlag("price_source_P4");
                return {
                    price_raw: priceM[1].trim(),
                    moq_raw: moqM ? moqM[1].trim() : null,
                };
            }
        }
    }
    return { price_raw: null, moq_raw: null };
};

// P5 — tiered price con CURRENCY_RE en candidates (E1 de v6).
//      Recibe el array de elementos candidatos.
//      Retorna {price_raw, moq_raw} o {price_raw: null, moq_raw: null}.
const priceFromBodyTiered = (candidates) => {
    for (const el of candidates) {
        const txt = $(el).text_sane();
        if (!txt) continue;
        // Recoger todos los precios en el bloque.
        const priceMatches = [];
        let pm;
        CURRENCY_RE_SHARED.lastIndex = 0;
        while ((pm = CURRENCY_RE_SHARED.exec(txt)) !== null) {
            priceMatches.push(pm[0].trim());
        }
        if (priceMatches.length === 0) continue;
        // Extraer el valor numérico de cada match para ordenar.
        const priceValues = priceMatches.map((p) => {
            const numStr = p.replace(/[^\d.,]/g, "");
            return parseNumber(numStr);
        }).filter((v) => v !== null && v > 0);
        if (priceValues.length === 0) continue;
        const minVal = Math.min(...priceValues);
        const maxVal = Math.max(...priceValues);
        const minMatch = priceMatches.find((p) => {
            const v = parseNumber(p.replace(/[^\d.,]/g, ""));
            return v === minVal;
        });
        const maxMatch = priceMatches.find((p) => {
            const v = parseNumber(p.replace(/[^\d.,]/g, ""));
            return v === maxVal;
        });
        const pr = minVal === maxVal ? minMatch : `${minMatch}-${maxMatch}`;
        // MOQ: buscar el primer threshold de cantidad con unidad antes del primer precio.
        let mq = null;
        const firstPriceIdx = txt.search(CURRENCY_RE_SHARED);
        const textBeforePrice = firstPriceIdx > 0 ? txt.slice(0, firstPriceIdx) : txt;
        const moqM = textBeforePrice.match(MOQ_RE_SHARED);
        if (moqM) mq = moqM[0].trim();
        addFlag("tiered_price_fallback");
        addFlag("price_source_P5");
        return { price_raw: pr, moq_raw: mq };
    }
    return { price_raw: null, moq_raw: null };
};

// P6 — body fallback completo con strip RTL + ancla de sección (F1+F4 de v6).
//      Retorna {price_raw, moq_raw} o {price_raw: null, moq_raw: null}.
const priceFromBodyFull = () => {
    const bodyRaw = $('body').text_sane() || '';
    const bodyText = bodyRaw.replace(/[‎‏‪-‮﻿]/g, '');
    const SECTION_RE = /Product descriptions from the supplier|供应商的产品说明|Tedarik[cç]inin [uü]r[uü]n a[cç][iı]klamalar[iı]|תיאורי המוצרים מהספק/i;
    const sectionIdx = bodyText.search(SECTION_RE);
    const searchText = sectionIdx >= 0
        ? bodyText.slice(sectionIdx, sectionIdx + 2000)
        : bodyText.slice(-3000);

    const bodyPriceRe = /(NZ\$|CA\$|A\$|US\$|R\$|B\/\.|RM|Rp|SEK|DKK|RSD|[€£¥₹₩฿$円])\s*[\d.,]+|[\d.,]+\s*(?:TL|TRY|SEK|DKK|RSD|円|€)/gi;
    const bodyMoqRe = /([\d,]+)\s*(?:-\s*[\d,]+)?\s*(kilogram|kilograms|kg|ton|tons|tonne|tonnes|piece|pieces|unit|units|liter|liters|litre|litres|bag|bags)/i;
    const bMatches = [];
    let bm;
    while ((bm = bodyPriceRe.exec(searchText)) !== null) {
        bMatches.push(bm[0].trim());
    }
    if (bMatches.length === 0) return { price_raw: null, moq_raw: null };

    const bValues = bMatches
        .map(p => parseNumber(p.replace(/[^\d.,]/g, '')))
        .filter(v => v !== null && v > 0);
    if (bValues.length === 0) return { price_raw: null, moq_raw: null };

    const bMin = Math.min(...bValues);
    const bMax = Math.max(...bValues);
    const bMinMatch = bMatches.find(p => parseNumber(p.replace(/[^\d.,]/g, '')) === bMin);
    const bMaxMatch = bMatches.find(p => parseNumber(p.replace(/[^\d.,]/g, '')) === bMax);
    const pr = bMin === bMax ? bMinMatch : `${bMinMatch}-${bMaxMatch}`;

    let mq = null;
    const firstPricePos = searchText.search(bodyPriceRe);
    const beforePrice = firstPricePos > 0 ? searchText.slice(0, firstPricePos) : searchText;
    const moqMatch = beforePrice.match(bodyMoqRe);
    if (moqMatch) mq = moqMatch[0].trim();

    addFlag('body_text_fallback');
    addFlag('price_source_P6');
    return { price_raw: pr, moq_raw: mq };
};

// ---------------------------------------------------------------------------
// Cascada principal de precio.
// P1–P6: DOM — price_raw = texto original visible en la página, sin construir.
// P7 (JSON-LD fallback): solo cuando DOM no encuentra precio. price_raw se
//   construye con prefijo "[jsonld: CUR{low}-CUR{high}]" para distinguirlo
//   del texto DOM. priceParsed se popula directamente desde JSON-LD.
// ---------------------------------------------------------------------------
let price_raw = null;
let moq_raw = null;
let priceParsed = { min: null, max: null, currency: null, unit: null };

const priceItems = $(".price-item").toArray();
const descCandidates = $(
    'section, div[class*="description"], div[class*="detail"], [class*="supplier-desc"]'
).toArray();

const strategies = [
    () => priceItems.length > 0 ? priceFromLadder(priceItems) : null,
    () => priceFromRangeSpans(),
    () => priceFromCSS(),
    () => priceFromBodyMOQ(descCandidates),
    () => priceFromBodyTiered(descCandidates),
    () => priceFromBodyFull(),
];

for (const strategy of strategies) {
    console.log(`Trying price strategy: ${strategy.name}`);
    const result = strategy();
    console.log(`Result: price_raw=${result && result.price_raw}, moq_raw=${result && result.moq_raw}`);
    if (result && result.price_raw) {
        price_raw = result.price_raw;
        // Regla: si priceFromRangeSpans (P2) produce moq_raw, conservarlo.
        moq_raw = result.moq_raw || null;
        priceParsed = parsePrice(price_raw);
        break;
    }
}

// P7 — JSON-LD fallback (hydration timeout).
// price_raw se construye con prefijo [jsonld: ] para distinguirlo de texto DOM.
if (!price_raw) {
    const jld = scanJsonLd();
    if (jld) {
        const rangeStr = jld.isRange
            ? `${jld.rawCur}${jld.rawLow}-${jld.rawCur}${jld.rawHigh}`
            : `${jld.rawCur}${jld.rawLow}`;
        price_raw = `[jsonld: ${rangeStr}]`;
        addFlag('price_source_P0_jsonld');
        if (jld.needsFx) addFlag('price_fx_needed');
        priceParsed = { min: jld.min, max: jld.max, currency: jld.currency, unit: null };
    }
}

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
// Fallback template tiered-price (E1): el link del supplier puede tener
// formato /index en lugar del subdominio *.en.alibaba.com.
if (!supplier_name) {
    supplier_name = $('a[href*="alibaba.com"][href*="/index"]').first().text_sane() || null;
}

// --- Supplier fallbacks v8 (FB4–FB6). ------------------------------------

// FB4 — JSON-LD brand/seller/manufacturer.
if (!supplier_name) {
    const scripts = $('script[type="application/ld+json"]').toArray();
    for (const script of scripts) {
        try {
            const data = JSON.parse($(script).html() || '');
            const nodes = Array.isArray(data) ? data : (data['@graph'] ? data['@graph'] : [data]);
            for (const node of nodes) {
                const s = node.brand?.name || node.seller?.name || node.manufacturer?.name;
                if (s && typeof s === 'string' && s.trim()) {
                    supplier_name = s.trim();
                    addFlag('supplier_source_jsonld');
                    break;
                }
            }
        } catch (_) { }
        if (supplier_name) break;
    }
}

// FB5 — meta og:site_name (solo si no parece ser el nombre de la plataforma).
if (!supplier_name) {
    const og = $('meta[property="og:site_name"]').attr('content');
    if (og && og.trim() && !/alibaba/i.test(og)) {
        supplier_name = og.trim();
        addFlag('supplier_source_og');
    }
}

// FB6 — data-testid broad net (excluye el selector exacto ya cubierto en
//        la cascada primaria para evitar duplicados).
if (!supplier_name) {
    supplier_name = $(
        '[data-testid*="seller"]:not([data-testid="seller-overview-card-company-link"]),' +
        '[data-testid*="company-name"],' +
        '[data-testid*="supplier-name"]'
    ).first().text_sane() || null;
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

// Flag adicional v8: distingue precio RFQ/oculto de timeout de hidratación React.
if (!price_raw) {
    // Distingue timeout-fail de página genuinamente RFQ.
    // Si el supplier sí se encontró, probablemente es precio oculto/RFQ.
    // Si supplier también es null, probablemente es timeout de hidratación.
    addFlag(supplier_name ? 'rfc_only_page' : 'hydration_timeout');
}

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
