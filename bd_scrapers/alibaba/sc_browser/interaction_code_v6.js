
// Input (modo single):
//   url: "https://www.alibaba.com/trade/search?SearchText=..."
//   search_keyword: "citric acid"
//   max_pages: 5  (default 5, -1 = sin limite)
//   min_price / max_price / min_order_quantity / supplier_country  (opcionales)
//
// v6: cap subido de 20 a 100 páginas.

const base_url = 'https://www.alibaba.com';

// let url = new URL(input.url || `${base_url}/trade/search`);
let url = new URL(`${base_url}/trade/search`);

if (input.search_keyword) {
    url.searchParams.set('SearchText', input.search_keyword ?? 'Industrial+chemicals');
}
url.searchParams.set('has4Tab', 'true');


navigate(url.href);

const product_card_selector = 'div.fy23-search-card.J-search-card-wrapper';
wait(product_card_selector, { timeout: 60000 });

if (el_exists('[action="/errors/validateCaptcha"]')) {
    blocked('Captcha detected on page');
}

scroll_to('bottom');
wait(product_card_selector);

let page_data = parse();

if (!input.is_rerun) {
    const max_pages = Math.min(input.max_pages || 5, 100);
    const current_page = parseInt(url.searchParams.get('page')) || 1;
    const has_next = el_exists('button.pagination-item.next:not([disabled])');

    if (has_next && current_page < max_pages) {
        for (let page = 2; page <= max_pages; page++) {
            const next_url = new URL(url.href);
            next_url.searchParams.set('page', page.toString());
            rerun_stage({
                url: next_url.href,
                search_keyword: input.search_keyword,
                min_order_quantity: input.min_order_quantity,
                supplier_country: input.supplier_country,
                min_price: input.min_price,
                max_price: input.max_price,
                max_pages: input.max_pages,
                is_rerun: true,
            });
        }
    }
}

for (const product_url of page_data.product_urls) {
    next_stage({ url: product_url });
}
