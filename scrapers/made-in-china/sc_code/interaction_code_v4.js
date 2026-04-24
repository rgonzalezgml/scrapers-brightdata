navigate(input.url);

// Check if it's an error page immediately
if (el_exists('.main.type-error.error-not-found')) {
    dead_page('Product not found');
}

let data = parse();

if (data) {
    collect(data);
}
