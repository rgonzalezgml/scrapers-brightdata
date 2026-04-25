// cosmetics-design — sc_browser/interaction_code_v1.js
// Bootstrap desde vendor + cierre de gaps:
// - input.max_pages (default -1 = sin limite) reemplaza el hardcode max_clicks=10.
//   Si max_pages >= 0, el loop se corta a ese numero de clicks del boton "Load more".
//   Si -1, el loop corre hasta que el boton desaparezca.
// - Se mantiene el guard por desaparicion del boton (break natural cuando no hay mas paginas).
// - El filtro de cross-promo (/Product-innovations/, /Events/) se aplica en parser_code_v1.js.
// - input.supplier (default "William Reed") se propaga al stage de detalle via next_stage sidecar.
//
// Referencias spec: §3, §7, §10.

// Navigate to the Beauty-wellness category page
navigate(input.url);

// Wait for the main content to load
const story_items_selector = '.story-item';
const load_more_button_selector = 'button.stories-see-more';

wait(story_items_selector);

// Runtime input: max_pages. -1 = sin limite (loop hasta que no haya mas boton).
// Entero >= 0: cap duro de clicks del "Load more".
const max_pages = (input.max_pages !== undefined ? input.max_pages : -1);
const unlimited = (max_pages === -1);

// Handle pagination by clicking "Load more" button repeatedly.
// The page uses a "Load more" button to dynamically load additional articles.
let clicks = 0;
while (true) {
    if (!unlimited && clicks >= max_pages) break;
    if (el_exists(load_more_button_selector, 1000)) {
        scroll_to(load_more_button_selector);
        click(load_more_button_selector);
        // Wait for new content to load
        wait(story_items_selector, {timeout: 10000});
        clicks++;
    } else {
        // No more "Load more" button, we've reached the end
        break;
    }
}

// Parse the page to extract article URLs (parser filters out /Product-innovations/ and /Events/)
const {article_urls} = parse();

// Propagate supplier down to detail stage via next_stage sidecar.
// Default = "William Reed" (ver §4 / §10 del spec).
const supplier = (input.supplier !== undefined ? input.supplier : 'William Reed');

// Collect each article URL using next_stage
for (let url of article_urls) {
    next_stage({url: url, supplier: supplier});
}
