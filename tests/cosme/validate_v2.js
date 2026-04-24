const fs = require('fs');
const path = require('path');
const cheerio = require('cheerio');
const iconv = require('iconv-lite');

const ROOT = path.resolve(__dirname, '..', '..');
const FIXTURES_DIR = path.join(__dirname, 'fixtures');
const PARSER_PATH = path.join(ROOT, 'docs/specs/brightd-scrapers/cosme/parser/sc_code/v2/parser_code_2.js');
const OUT_DIR = path.join(ROOT, 'docs/specs/brightd-scrapers/cosme/parser/sc_code/v2');

const parserSource = fs.readFileSync(PARSER_PATH, 'utf-8');
const runParser = new Function('$', 'input', parserSource);

const fixtures = [
  {
    id: '10248076',
    must_pass: true,
    expect: {
      product_name_raw: 'ルース パウダー',
      brand_name: 'コスメデコルテ',
      brand_id: '79',
      maker_id: '102317',
    },
  },
  {
    id: '10243030',
    expect: {
      brand_name: 'アテニア',
      brand_id: '438',
      maker_id: '51',
    },
  },
  {
    id: '10259468',
    expect: {
      brand_name: 'ランコム',
      brand_id: '42',
      maker_id: '110',
    },
  },
];

const results = [];
let failures = 0;

for (const fx of fixtures) {
  const htmlPath = path.join(FIXTURES_DIR, `${fx.id}.html`);
  const buf = fs.readFileSync(htmlPath);
  const html = iconv.decode(buf, 'shift_jis');
  const $ = cheerio.load(html);
  const input = {
    url: `https://www.cosme.net/products/${fx.id}/`,
    shift_jis_fallback: true,
  };

  let out;
  try {
    out = runParser($, input);
  } catch (e) {
    console.log(`\n=== ${fx.id} === PARSER THREW: ${e.message}`);
    failures++;
    continue;
  }

  if (out.product_url && typeof out.product_url === 'object' && out.product_url.toString) {
    out.product_url = out.product_url.toString();
  }

  console.log(`\n=== ${fx.id} ${fx.must_pass ? '(MUST PASS)' : ''} ===`);
  for (const [k, v] of Object.entries(fx.expect)) {
    const actual = out[k];
    const pass = actual === v;
    console.log(`  ${pass ? '✓' : '✗'} ${k}: expected=${JSON.stringify(v)} got=${JSON.stringify(actual)}`);
    if (!pass) failures++;
  }

  console.log('  — populated fields —');
  console.log(`  product_name_clean : ${JSON.stringify(out.product_name_clean)}`);
  console.log(`  category_chains    : ${(out.category_chains || []).length} chain(s)`);
  console.log(`  category_ids       : ${JSON.stringify(out.category_ids)}`);
  console.log(`  category_primary_id: ${out.category_primary_id}`);
  console.log(`  category_names     : ${JSON.stringify(out.category_names)}`);
  console.log(`  effect_ids         : ${JSON.stringify(out.effect_ids)}`);
  console.log(`  ingredient_tag_ids : ${JSON.stringify(out.ingredient_tag_ids)}`);
  console.log(`  rating_avg         : ${out.rating_avg}`);
  console.log(`  review_count       : ${out.review_count}`);
  console.log(`  review_count_photo : ${out.review_count_photo}`);
  console.log(`  launch_date        : ${out.launch_date}`);
  console.log(`  launch_year        : ${out.launch_year}`);
  console.log(`  maker_name         : ${JSON.stringify(out.maker_name)}`);
  console.log(`  price_text         : ${JSON.stringify(out.price_text)}`);
  console.log(`  variants.length    : ${(out.variants || []).length}`);
  if ((out.variants || []).length) console.log(`    [0]: ${JSON.stringify(out.variants[0])}`);
  console.log(`  variations.length  : ${(out.variations || []).length}`);
  if ((out.variations || []).length) console.log(`    [0]: ${JSON.stringify(out.variations[0])}`);
  console.log(`  is_official        : ${out.is_official}`);
  console.log(`  regulation_class   : ${out.regulation_class}`);
  console.log(`  rankings.length    : ${(out.rankings || []).length}`);
  console.log(`  scraper_flags      : ${JSON.stringify(out.scraper_flags)}`);
  console.log(`  _name_source       : ${out._name_source}`);

  results.push({ ...out, input });
}

const now = new Date();
const ts = now.toISOString().replace(/[-:]/g, '').replace(/\..+/, '').replace('T', '_');
const outFile = path.join(OUT_DIR, `cosme.net_${ts}.json`);
fs.writeFileSync(outFile, JSON.stringify(results, null, 2));

console.log(`\n==============================`);
console.log(`Saved output → ${outFile}`);
console.log(`Failures: ${failures}`);
process.exit(failures > 0 ? 1 : 0);
