// cosme v2 — integration code (sc_code / Stage 2 FETCH)
//
// Logs de diagnóstico agregados 2026-04-22 para debug de E6/E8. Prefijo
// [S2-CODE/INT] en todos los console.log de este archivo. Sin cambios
// semánticos respecto a la revisión previa.
//
// What changed vs v1 (which was a verbatim copy of vendor/):
//   (E8) The vendor pattern `collect(parse({ html: decoded_html, ... }))`
//        is structurally broken on BrightData Scraper Studio:
//          1. `parse()` does NOT accept arbitrary keyword args — per
//             runtime rule R2 in `docs/specs/brightdata-errors.md`, any
//             non-schema field triggers `parse validation error`.
//          2. Even when the runtime tolerates the extra keys silently, `$`
//             inside the parser stays bound to whatever the last
//             `navigate()` loaded (raw Shift-JIS bytes, not the decoded
//             `decoded_html` buffer we tried to sideload). That makes
//             `$('body')` return a wrapper whose `.text()` is missing or
//             operates on garbage — matching exactly the preview error:
//               Crawler error: (intermediate value).text is not a function
//             at the very first `.text()` call of the parser (line 178,
//             `const bodyText = $('body').text();`).
//        Root cause confirmed by the Scraper Studio live log:
//          [20:21:33] $("body")
//          [20:21:33] Crawler error: (intermediate value).text is not a function
//        This is the FIRST `.text()` in the parser — well before the
//        breadcrumb cascade E7 tried to fix. E7's diagnosis was partial:
//        the breadcrumb code was a secondary latent issue that would have
//        eventually bitten on specific fixtures, but the reason the
//        collector could not save at all is this one: the parser never
//        got a correctly-bound `$`.
//
// The correct pattern per SKILL `scraper-implementation` §4 + §7
// ("Encoding no-UTF-8 (cosme.net Shift_JIS)"):
//
//     request(encoding:null) → decode manually with iconv-lite →
//     load_html(decoded_html)   ← THIS binds $ to the decoded content
//     collect(parse())          ← parse() takes no args (R2, R9 of skill)
//
// `load_html()` is the documented sc_code primitive for re-binding the
// cheerio-like `$` global to an arbitrary HTML string. `parse({html:...})`
// was never the correct channel and never worked on BrightData real runs
// (the vendor had a latent bug that only surfaced now because we finally
// tried to save the collector through preview).
//
// The shift_jis_fallback flag is no longer threaded through parse-args
// (that channel doesn't exist). Instead the parser self-detects mojibake
// from `$('body').text()` — logic that was already present in v1 as a
// belt-and-suspenders fallback (lines ~179-186 of parser_code_v1.js). The
// parser sets the flag when it sees mojibake; since we now decode
// correctly BEFORE parsing, the flag should fire only on genuinely broken
// pages (block pages, empty 404, etc.), which is what we want.
//
// Degraded path: if `request()` throws or returns a body with NEITHER a
// successful UTF-8 decode NOR a clean Shift-JIS decode, fall back to a
// bare `parse()` — which will read $ from the prior `navigate()` — so at
// least we get SOMETHING parsed (the parser will then flag mojibake /
// name_extract_failed as appropriate). No silent data loss.

console.log(`[S2-CODE/INT] entry input.url=${input.url}`);

navigate(input.url);

let decoded_html = null;
let decode_path = 'unknown';
let raw_buffer_bytes = 0;

try {
  const response = request({
    url: input.url,
    encoding: null  // raw buffer — do NOT let the runtime autodetect
  });

  const raw_buffer = response.body;
  raw_buffer_bytes = raw_buffer && raw_buffer.length ? raw_buffer.length : 0;
  const utf8_text = raw_buffer.toString('utf-8');

  // Precondition: a valid UTF-8 decode must contain ≥1 JP char and zero
  // U+FFFD replacement chars. Otherwise the payload is Shift-JIS.
  const has_jp_char = /[ぁ-ヿ一-龯]/.test(utf8_text);
  const has_replacement_chars = /�/.test(utf8_text);

  if (!has_jp_char || has_replacement_chars) {
    const iconv = require('iconv-lite');
    decoded_html = iconv.decode(raw_buffer, 'shift_jis');
    decode_path = 'shift_jis_fallback';
  } else {
    decoded_html = utf8_text;
    decode_path = 'utf8_ok';
  }
} catch (e) {
  // request() failed outright (network, HTTP error, decode blew up).
  // We'll fall through to the degraded path below.
  decoded_html = null;
  decode_path = 'degraded';
}

console.log(
  `[S2-CODE/INT] decode_path=${decode_path} raw_buffer_bytes=${raw_buffer_bytes}`
);

if (decoded_html !== null) {
  // Re-bind $ to the decoded HTML, then parse normally.
  // This is the documented sc_code pattern for custom decoding.
  console.log(`[S2-CODE/INT] calling load_html(decoded_html) + parse() bare`);
  load_html(decoded_html);
  collect(parse());
} else {
  // Degraded: no decoded buffer. Parse whatever navigate() gave us.
  // Parser will flag mojibake / name_extract_failed from $('body').text().
  console.log(`[S2-CODE/INT] degraded path — calling parse() bare without load_html`);
  collect(parse());
}

console.log(`[S2-CODE/INT] done`);
