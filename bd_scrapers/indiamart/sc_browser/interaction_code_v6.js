const MCAT_URL_TMPL = 'https://dir.indiamart.com/impcat/{slug}.html';
const HUB_URL_TMPL = 'https://dir.indiamart.com/indianexporters/ind_{slug}.html';

const kind = input.kind || 'mcat';
const resolved_url = kind === 'hub'
    ? HUB_URL_TMPL.replace('{slug}', input.category_slug)
    : MCAT_URL_TMPL.replace('{slug}', input.category_slug);

country('in');
navigate(resolved_url);

// guards + scroll + parse como ya lo tenés...

const data = parse();
for (const url of data.product_urls) {
    next_stage({ url });
}