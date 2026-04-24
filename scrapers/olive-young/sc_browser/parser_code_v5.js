const products = $('li.order-best-product.prdt-unit').map((_, li) => {
    const $li = $(li);
    const prdtNo = $li.find('input[name="prdtNo"]').val() || null;
    const korName = $li.find('input[name="korPrdtName"]').val() || null;
    const engName = $li.find('input[name="prdtName"]').val() || null;
    const index = parseInt($li.find('input[name="prdtIndex"]').val(), 10);
    const rank = parseInt($li.find('.rank-badge span').text_sane(), 10) || (index + 1);
    const brand = $li.find('dl.brand-info dt').text_sane() || null;
    const original_price = $li.find('.unit-desc .price-info span:not(.point):not(.set-value)').first().text_sane() || null;
    const sale_price = $li.find('.unit-desc .price-info strong.point').text_sane() || null;
    const ratingText = $li.find('.rating-info span').text_sane();
    const rating = ratingText ? parseFloat(ratingText) : null;
    const imgEl = $li.find('.unit-thumb img');
    const image = imgEl.attr('data-src') || imgEl.attr('src') || null;
    const out_of_stock = $li.hasClass('out-of-stock');

    return {
        rank,
        prdtNo,
        brand,
        name: engName,
        name_kr: korName,
        original_price,
        sale_price,
        rating,
        image,
        out_of_stock,
    };
}).get();

return { products };