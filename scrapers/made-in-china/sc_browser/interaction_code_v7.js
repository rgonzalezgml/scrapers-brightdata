// v7 — versión mínima de prueba: una URL → una página → products only.
// Sin paginación, sin reruns, sin suppliers. Solo: navigate → wait → parse → next_stage.
// Usar para validar que el scraper llega a la categoría y extrae product URLs.
// Una vez confirmado, volver a v6 (con paginación paralela) o extender v7.

navigate(input.url);

const wait_selector = '.search-list, .list-node, .products-item, .prod-item';
wait(wait_selector);

if (!el_exists('.list-node, .products-item, .prod-item'))
    dead_page('no listing cards found');

const { product_urls } = parse();

console.log(`Emitting ${product_urls.length} products`);

for (const url of product_urls)
    next_stage({ url });
