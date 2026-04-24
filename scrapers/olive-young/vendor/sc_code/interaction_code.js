navigate(input.url);

// Check if it's an error page immediately
if (el_exists('.main.type-error.error-not-found')) {
  dead_page('Product not found');
}

let data = null;
try {
  data = parse()
} catch(e) {
  console.log('Error', e)
}

if (data) {
  collect(data);
}
