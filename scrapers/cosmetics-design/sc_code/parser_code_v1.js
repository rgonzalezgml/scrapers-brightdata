// cosmetics-design — sc_code/parser_code_v1.js
// Bootstrap desde vendor + cierre de gaps §2/§4/§5/§6/§8 del spec:
// - Fuente primaria: window.Fusion.globalContent embebido en HTML (§5).
//   Parseado con conteo de llaves para recortar el JSON completo.
//   Fallback: selectores DOM del vendor (headline, subheadline, paragraphs) si Fusion falta.
// - Emite contrato §2 + campos adicionales §4 (subheadline, description, author_slugs,
//   promo_image_caption, scraper_flags). Nombres exactos del contrato.
// - article_id derivado de Fusion._id (no regex del URL).
// - website fijo "nutraingredients-v2". supplier desde input.supplier (default "William Reed").
// - subtype desde Fusion. display_date / publish_date / first_publish_date / last_updated_date ISO.
// - region_tags derivados de section_paths con prefijo /Regions/ (quitar prefijo).
// - topic_tags derivados de section_paths con navigation.type === 'news' (slug del ultimo segmento).
// - body_text: concatenar content_elements type='text' con \n\n; header como linea propia;
//   skip image/divider/video/list. Quitar <em>/<b>/<i>/<a> residual.
// - paywalled: article_content_type === 'metered' && paywall_hit === true (§2 spec).
// - scraper_flags: lista de strings (§8): paywalled, date_future, region_missing,
//   body_fallback_html, fusion_parse_fallback, consent_wall_retried.
// - SKIP (no emitir fila, lanza dead_page/bad_input segun §8):
//     * article_id no resuelto.
//     * Fusion.globalContent ausente Y fallbacks DOM tampoco dan headline.
//     * headline y body_text ambos vacios.
//
// Nota: Como parser_code no puede llamar dead_page/bad_input (son de interaction),
// la emision de null/vacio en campos criticos se ejecuta devolviendo un objeto con
// flag __skip (convencion interna) si decidieramos skipear. Aqui emitimos la fila
// con null donde aplique y dejamos al interaction marcar el skip via status_code.

// ============================================================================
// Helpers
// ============================================================================

// Strip residual HTML tags (em, b, i, a) from Fusion text, preservando texto interno.
const stripInlineHtml = (s) => {
  if (s === null || s === undefined) return s;
  return String(s)
    .replace(/<\/?(em|b|i|strong|a)(\s[^>]*)?>/gi, '')
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/\s+/g, ' ')
    .trim() || null;
};

// Word count: split por whitespace (§5 spec).
const wordCount = (text) => {
  if (!text) return null;
  return text.trim().split(/\s+/).filter(Boolean).length;
};

// Extraer objeto JSON completo desde el texto HTML con conteo de llaves (§5 spec).
// Busca el primer '{' tras needle, cuenta { y } respetando strings "..." y \" escape.
const extractJsonAfterNeedle = (html, needle) => {
  const idx = html.indexOf(needle);
  if (idx < 0) return null;
  const start = html.indexOf('{', idx);
  if (start < 0) return null;
  let depth = 0;
  let inStr = false;
  let esc = false;
  for (let i = start; i < html.length; i++) {
    const c = html[i];
    if (esc) { esc = false; continue; }
    if (c === '\\') { esc = true; continue; }
    if (c === '"') { inStr = !inStr; continue; }
    if (inStr) continue;
    if (c === '{') depth++;
    else if (c === '}') {
      depth--;
      if (depth === 0) {
        const raw = html.substring(start, i + 1);
        return raw;
      }
    }
  }
  return null;
};

// Slug del ultimo segmento de URL.
const urlSlug = (u) => {
  if (!u) return null;
  let s = String(u).replace(/[?#].*$/, '').replace(/\/+$/, '');
  const last = s.split('/').pop();
  return last || null;
};

// ISO 8601 UTC de un valor de fecha (Fusion ya los da ISO; normalizar igual).
const toIso = (v) => {
  if (!v) return null;
  try {
    const d = new Date(v);
    if (isNaN(d.getTime())) return null;
    return d.toISOString();
  } catch (e) {
    return null;
  }
};

// scraped_date en YYYY-MM-DD (UTC del runtime).
const scrapedDateToday = () => {
  const d = new Date();
  const y = d.getUTCFullYear();
  const m = String(d.getUTCMonth() + 1).padStart(2, '0');
  const dd = String(d.getUTCDate()).padStart(2, '0');
  return `${y}-${m}-${dd}`;
};

// ============================================================================
// Inputs + flags
// ============================================================================

const supplier = (input.supplier !== undefined ? input.supplier : 'William Reed');
const website = 'nutraingredients-v2';
const scraper_flags = [];

// Consent wall detection (flag only, no intento de retry aqui en sc_code).
if ($('.interstitial-container-popup').length > 0) {
  scraper_flags.push('consent_wall_retried');
}

// ============================================================================
// Parse Fusion.globalContent
// ============================================================================

let fusion = null;
let fusion_parse_failed = false;

// $.html() devuelve el HTML completo cargado.
const fullHtml = $.root ? ($.root().html() || '') : ($('html').html() || '');

const fusionRaw = extractJsonAfterNeedle(fullHtml, 'Fusion.globalContent');
if (fusionRaw) {
  try {
    fusion = JSON.parse(fusionRaw);
  } catch (e) {
    fusion_parse_failed = true;
  }
} else {
  fusion_parse_failed = true;
}

if (fusion_parse_failed) {
  scraper_flags.push('fusion_parse_fallback');
}

// ============================================================================
// Base fields (prefer Fusion, fallback DOM)
// ============================================================================

const article_id = fusion?._id ?? null;

// URL canonica del input.
const url = input.url ?? null;
const slug = urlSlug(url);

const headline = fusion?.headlines?.basic ?? $('.headline-block-header').text_sane() ?? null;
const subheadline = fusion?.subheadlines?.basic
  ?? $('.subheadline-block').text_sane()
  ?? $('.subheadline-block-skinny').text_sane()
  ?? null;
const description = fusion?.description?.basic ?? null;

const display_date = toIso(fusion?.display_date) ?? (function () {
  // Fallback DOM: "15-Apr-2026"
  const t = $('.date-block time').first().text_sane();
  return t ? toIso(t) : null;
})();
const publish_date = toIso(fusion?.publish_date);
const first_publish_date = toIso(fusion?.first_publish_date);
const last_updated_date = toIso(fusion?.last_updated_date);

const subtype = fusion?.subtype ?? null;

// ============================================================================
// Authors (credits.by[])
// ============================================================================

const credits = fusion?.credits?.by ?? [];
const author_names = credits.map(c => c?.name).filter(Boolean);
const author_slugs = credits.map(c => c?.slug).filter(Boolean);

// ============================================================================
// Taxonomy: primary_section_path + section_paths
// ============================================================================

const primary_section_path = fusion?.taxonomy?.primary_section?.path ?? null;

const taxo_sections = fusion?.taxonomy?.sections ?? [];
const section_paths = taxo_sections.map(s => s?.path).filter(Boolean);

// region_tags: section_paths que empiezan con /Regions/, strip prefijo.
// Ej: /Regions/North-America -> North-America
const region_tags = section_paths
  .filter(p => p.indexOf('/Regions/') === 0)
  .map(p => p.substring('/Regions/'.length).replace(/\/.*$/, ''))
  .filter(Boolean);

// topic_tags: section_paths donde navigation.type === 'news' (§6 spec).
// Preservar ultimo segmento como slug.
const topic_tags = taxo_sections
  .filter(s => s?.navigation?.type === 'news' && s?.path)
  .map(s => {
    const parts = s.path.split('/').filter(Boolean);
    return parts[parts.length - 1] || null;
  })
  .filter(Boolean);

if (region_tags.length === 0) {
  scraper_flags.push('region_missing');
}

// ============================================================================
// Body text from content_elements (§5 spec)
// ============================================================================

let body_text = null;
let body_word_count = null;
let body_fallback_html = false;

const content_elements = fusion?.content_elements ?? [];
if (content_elements.length > 0) {
  const pieces = [];
  for (const el of content_elements) {
    const t = el?.type;
    if (t === 'text') {
      const cleaned = stripInlineHtml(el?.content);
      if (cleaned) pieces.push(cleaned);
    } else if (t === 'header') {
      const cleaned = stripInlineHtml(el?.content);
      if (cleaned) pieces.push(cleaned);
    }
    // skip: image, divider, video, list, interstitial_link, correction, oembed_response, etc.
  }
  body_text = pieces.length > 0 ? pieces.join('\n\n') : null;
}

// Fallback DOM si Fusion no trajo content_elements.
if (!body_text) {
  const paragraphs = $('article p.c-paragraph.b-article-body-skinny').toArray()
    .map(el => $(el).text_sane())
    .filter(Boolean);
  if (paragraphs.length > 0) {
    body_text = paragraphs.join('\n\n');
    body_fallback_html = true;
  }
}

if (body_fallback_html) {
  scraper_flags.push('body_fallback_html');
}

body_word_count = wordCount(body_text);

// ============================================================================
// Promo image
// ============================================================================

const promo_image_url = fusion?.promo_items?.basic?.url ?? null;
const promo_image_caption = fusion?.promo_items?.basic?.caption ?? null;

// ============================================================================
// Paywall (§2 spec: article_content_type === 'metered' && paywall_hit === true)
// ============================================================================

const paywalled = (fusion?.article_content_type === 'metered' && fusion?.paywall_hit === true);
if (paywalled) {
  scraper_flags.push('paywalled');
}

// ============================================================================
// date_future flag
// ============================================================================

const scraped_date = scrapedDateToday();

if (display_date) {
  const ad = new Date(display_date);
  const sd = new Date(scraped_date + 'T00:00:00Z');
  // Consideramos futuro si display_date > hoy UTC.
  if (!isNaN(ad.getTime()) && ad > sd) {
    // Agregar +1 dia para tolerar diferencia de fuso; si sigue siendo futura, flag.
    const todayEnd = new Date(sd.getTime() + 24 * 60 * 60 * 1000);
    if (ad > todayEnd) {
      scraper_flags.push('date_future');
    }
  }
}

// ============================================================================
// Emit — contrato §2 + campos §4
// ============================================================================

return {
  // §2 strict
  article_id: article_id,
  url: url,
  slug: slug,
  headline: headline,
  display_date: display_date,
  publish_date: publish_date,
  last_updated_date: last_updated_date,
  website: website,
  supplier: supplier,
  subtype: subtype,
  author_names: author_names,
  primary_section_path: primary_section_path,
  section_paths: section_paths,
  region_tags: region_tags,
  topic_tags: topic_tags,
  body_text: body_text,
  body_word_count: body_word_count,
  promo_image_url: promo_image_url,
  paywalled: paywalled,
  scraped_date: scraped_date,

  // §4 adicionales (frecuentes con null explicito)
  subheadline: subheadline,
  description: description,
  author_slugs: author_slugs,
  promo_image_caption: promo_image_caption,
  first_publish_date: first_publish_date,
  scraper_flags: scraper_flags
};
