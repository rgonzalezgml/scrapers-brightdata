
const base_url = 'https://global.oliveyoung.com/display/page/best-seller';
const url = new URL(input.url || base_url);

navigate(url);

wait('.nav-item.nbs-tab-item');

const region = input.region || 'usa';

if (region.toLowerCase() === 'korea') {
    if (!el_exists('#pillsTab1Nav2.active')) {
        click('#pillsTab1Nav2');
        wait('#pillsTab1Cont2');
    }
    scroll_to('bottom');
} else {
    if (!el_exists('#pillsTab1Nav1.active')) {
        click('#pillsTab1Nav1');
        wait('#pillsTab1Cont1');
    }
    scroll_to('bottom');
}

const data = parse();
const { product_urls } = data;

console.log(`Found ${product_urls.length} product URLs for region: ${region}`);

for (let product_url of product_urls) {
    next_stage({ url: product_url });
}