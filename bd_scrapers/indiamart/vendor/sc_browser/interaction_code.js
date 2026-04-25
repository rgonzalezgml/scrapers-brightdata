navigate(input.url);

const product_link_selector = 'a[href*="proddetail"]';

wait(product_link_selector);

scroll_to('bottom');

wait(product_link_selector);

const {product_urls} = parse();

for (let url of product_urls) {
    next_stage({url});
}
