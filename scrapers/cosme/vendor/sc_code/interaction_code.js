// cosme v2 — integration code
//
// Strategy:
//   1. Fetch raw body as buffer (no autodetected encoding).
//   2. Decode as UTF-8 first and validate: presence of at least one char in
//      [ぁ-ヿ一-龯] (hiragana/katakana/kanji) AND no U+FFFD replacement chars.
//   3. If validation fails, re-decode as Shift-JIS with iconv-lite and pass the
//      decoded HTML into parse() via the shift_jis_fallback path.
//   4. Parse emits scraper_flags including 'shift_jis_fallback' and
//      'name_extract_failed' where applicable.
//
// Block page detection is delegated to parse() (body length + JP signature
// string). The integration just ensures decoding is correct before parse runs.

navigate(input.url);

let shift_jis_fallback = false;
let decoded_html = null;

try {
  const response = request({
    url: input.url,
    encoding: null  // raw buffer
  });

  const raw_buffer = response.body;
  const utf8_text = raw_buffer.toString('utf-8');

  // Precondition: decoded body must contain at least 1 JP char and 0 U+FFFD.
  const has_jp_char = /[ぁ-ヿ一-龯]/.test(utf8_text);
  const has_replacement_chars = /�/.test(utf8_text);

  if (!has_jp_char || has_replacement_chars) {
    // Mojibake detected — re-decode as Shift-JIS.
    const iconv = require('iconv-lite');
    decoded_html = iconv.decode(raw_buffer, 'shift_jis');
    shift_jis_fallback = true;
  } else {
    decoded_html = utf8_text;
  }
} catch (e) {
  // If the explicit request failed, fall back to navigate()-provided HTML.
  decoded_html = null;
}

if (decoded_html !== null && shift_jis_fallback) {
  // Re-parse with the correctly decoded HTML.
  collect(parse({ html: decoded_html, shift_jis_fallback: true }));
} else if (decoded_html !== null) {
  collect(parse({ html: decoded_html, shift_jis_fallback: false }));
} else {
  // Degraded path: parse against whatever navigate() gave us, with no flag.
  collect(parse());
}
