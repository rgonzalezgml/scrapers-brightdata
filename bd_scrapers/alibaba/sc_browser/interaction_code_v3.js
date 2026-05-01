// Input (modo array):
//   search_keywords: ["Citric Acid Anhydrous", "Glycerin USP", ...]
//
// Input (modo single):
//   url: "https://www.alibaba.com/trade/search?SearchText=..."
//   search_keyword: "citric acid"
//   max_pages: 5  (default 5, -1 = sin limite)
//   min_price / max_price / min_order_quantity / supplier_country  (opcionales)
//
// Input vacio -> fan-out por keywords por defecto

const BASE_URL = 'https://www.alibaba.com';

const DEFAULT_KEYWORDS = [
    'pharmaceutical ingredients',
    'pharmaceutical packaging',
];

function search_url(keyword) {
    return `${BASE_URL}/trade/search?SearchText=${encodeURIComponent(keyword)}&has4Tab=true`;
}

// --- Fan-out: array de keywords -> rerun por cada uno, sin navegar ---
if (Array.isArray(input.search_keywords) && input.search_keywords.length > 0) {
    for (const kw of input.search_keywords) {
        rerun_stage({
            url:               search_url(kw),
            search_keyword:    kw,
            max_pages:         -1,
            min_price:         input.min_price,
            max_price:         input.max_price,
            min_order_quantity:input.min_order_quantity,
            supplier_country:  input.supplier_country,
        });
    }

// --- Sin input -> fan-out por keywords por defecto ---
} else if (!input.url && !input.search_keyword) {
    for (const kw of DEFAULT_KEYWORDS) {
        rerun_stage({
            url:            search_url(kw),
            search_keyword: kw,
            max_pages:      -1,
        });
    }

// --- Modo single: un keyword o URL directa ---
} else {
    let url = new URL(input.url || `${BASE_URL}/trade/search`);
    url.searchParams.set('has4Tab', 'true');

    if (input.search_keyword) {
        url.searchParams.set('SearchText', input.search_keyword);
    }

    navigate(url.href);

    const product_card_selector = 'div.fy23-search-card.J-search-card-wrapper';
    wait(product_card_selector, { timeout: 60000 });

    if (el_exists('[action="/errors/validateCaptcha"]')) {
        blocked('Captcha detected on page');
    }

    scroll_to('bottom');
    wait(product_card_selector);

    const page_data = parse();

    if (!input.is_rerun) {
        const max_pages    = input.max_pages === -1 ? Infinity : Math.min(input.max_pages || 5, 10);
        const current_page = parseInt(url.searchParams.get('page')) || 1;
        const has_next     = el_exists('button.pagination-item.next:not([disabled])');

        if (has_next && current_page < max_pages) {
            for (let page = 2; page <= max_pages; page++) {
                const next_url = new URL(url.href);
                next_url.searchParams.set('page', page.toString());
                rerun_stage({
                    url:               next_url.href,
                    search_keyword:    input.search_keyword,
                    min_order_quantity:input.min_order_quantity,
                    supplier_country:  input.supplier_country,
                    min_price:         input.min_price,
                    max_price:         input.max_price,
                    max_pages:         input.max_pages,
                    is_rerun:          true,
                });
            }
        }
    }

    for (const product_url of page_data.product_urls) {
        next_stage({ url: product_url });
    }
}
