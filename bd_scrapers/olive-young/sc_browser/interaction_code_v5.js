
// Input
// url: https://global.oliveyoung.com/display/page/best-seller?target=pillsTab1Nav1
// region: kr (allowed: kr, us)

country(input.region ?? 'kr');
navigate(input.url, { wait_until: 'domcontentloaded' });

wait_network_idle({ timeout: 5000 });

let data = parse();


if (!data.products || data.products.length === 0) {
    // Debug: ver qué hay en la página
    console.log('products found: 0');
    console.log('all li count: ' + data.debug_li_count);
    console.log('body snippet: ' + data.body_snippet);
    dead_page('no_products_found');
}

collect(data.products);