navigate(input.url);

// The page at https://dir.indiamart.com/indore/ is a directory listing page with category links, not product detail pages
// Product detail pages with "proddetail" in the URL don't exist on this directory page



const {product_urls} = parse();

for (let url of product_urls) {
    next_stage({url});
}