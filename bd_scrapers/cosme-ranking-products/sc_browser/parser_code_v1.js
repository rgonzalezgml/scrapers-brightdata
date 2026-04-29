// ============================================================================
// STAGE 1 — PARSER CODE: Extraer lista de productos del ranking
// ============================================================================
// page = 0 → ranks 1-10
// page = 1 → ranks 11-20
// ============================================================================

const page = input.page || 0;
const base = 'https://www.cosme.net';

// ---- Período de agregación ----
const period_text = $('#nav-rank-header p').text();
const period_match = period_text.match(/(\d{4}\/\d{1,2}\/\d{1,2})\s*[～~]\s*(\d{4}\/\d{1,2}\/\d{1,2})/);
const period_start = period_match ? period_match[1] : '';
const period_end = period_match ? period_match[2] : '';

// ---- Paginación ----
const paging_text = $('.cmn-modules-paging p').text_sane();
const total_match = paging_text.match(/(\d+)件中/);
const total = total_match ? parseInt(total_match[1], 10) : 0;
const range_match = paging_text.match(/(\d+)-(\d+)件を/);
const min = range_match ? parseInt(range_match[1], 10) : 0;
const max = range_match ? parseInt(range_match[2], 10) : 0;

// Total de páginas (del paginador)
let total_pages = 1;
$('.cmn-modules-paging li').each(function () {
    if ($(this).hasClass('back') || $(this).hasClass('next')) return;
    const num = parseInt($(this).text(), 10);
    if (num > total_pages) total_pages = num;
});

// ---- Productos ----
const items = [];

$('#list-item dl').each(function (i) {
    const $dl = $(this);

    // Product
    const $prodLink = $dl.find('dd.summary span.item a');
    const product_name = $prodLink.text_sane();
    const prod_href = $prodLink.attr('href') || '';
    const product_id = (prod_href.match(/\/products\/(\d+)/) || [])[1] || '';
    if (!product_id) return;
    const prod_url = new URL(prod_href, base).href;

    // Brand
    const $brandLink = $dl.find('dd.summary span.brand a').first();
    const brand_href = new URL($brandLink.attr('href') || '', base).href;
    const brand_id = (brand_href.match(/\/brands\/(\d+)/) || [])[1] || '';
    const brand_name = $brandLink.text_sane();

    // Rating from CSS class (arg-5_5 → 5.5)
    let rating = null;
    const rating_cls = $dl.find('p.rating').attr('class') || '';
    const rating_cls_match = rating_cls.match(/arg-(\d+)(?:_(\d+))?/);
    if (rating_cls_match) {
        rating = rating_cls_match[2]
            ? parseFloat(rating_cls_match[1] + '.' + rating_cls_match[2])
            : parseFloat(rating_cls_match[1]);
    }

    // Rank
    let rank;
    if ($dl.hasClass('top3')) {
        const rank_alt = $dl.find('dt span.rank-num img').attr('alt') || '';
        rank = parseInt(rank_alt.replace(/\D/g, ''), 10) || 0;
    } else {
        const rank_text = $dl.find('dt span.rank-num span.num').text_sane();
        rank = parseInt(rank_text.replace(/\D/g, ''), 10) || 0;
    }

    // Fallback: calcular rank por posición
    if (!rank) {
        rank = (page * 10) + (i + 1);
    }

    // Category
    const $categoryLink = $dl.find('dd.summary .category a');
    const category = $categoryLink.text_sane();
    const category_href = new URL($categoryLink.attr('href') || '', base).href;

    // Rank change
    let rank_change = 'same';
    const icon_src = $dl.find('dt span.status img').attr('src') || '';
    if (icon_src.indexOf('ico_up') !== -1) rank_change = 'up';
    if (icon_src.indexOf('ico_down') !== -1) rank_change = 'down';
    if (icon_src.indexOf('ico_hot') !== -1) rank_change = 'hot';
    if (icon_src.indexOf('ico_new') !== -1) rank_change = 'new';

    // Image
    const image_url = $dl.find('dd.pic img').attr('src') || '';

    // Badges
    const is_best_cosme = $dl.find('span.icon-cmn-bestcosme').length > 0;
    const is_new = $dl.find('span.icon-cmn-new').length > 0;

    // Price
    const price_raw = $dl.find('p.price').text_sane();
    const yen_match = price_raw.match(/([\d,]+)\s*円/);
    const price_yen = yen_match ? parseInt(yen_match[1].replace(/,/g, ''), 10) : null;
    const size_match = price_raw.match(/([\d,.]+\s*(?:mL|ml|g|kg|個入り|枚|本))/i);
    const size = size_match ? size_match[1] : '';
    const is_open_price = /オープン価格|open/i.test(price_raw);
    const tax_included = /税込/.test(price_raw);

    // Reviews
    const review_text = $dl.find('p.votes a.count').text();
    const review_count = parseInt((review_text || '').replace(/[^\d]/g, ''), 10) || 0;

    // Release date
    const release_date = $dl.find('p.onsale').text_sane();

    // Shop URL
    const shop_url = $dl.find('a.btn-cmn-buy').attr('href') || '';

    items.push({
        product_id,
        product_name,
        url: prod_url,
        prod_img_url: image_url,

        page,
        // max_pages,

        category,
        category_href,

        price_text: price_raw,
        price_yen,
        size,
        is_open_price,
        tax_included,

        rank,
        rank_change,
        rating,
        review_count,
        release_date,
        shop_url,

        is_best_cosme,
        is_new,

        brand_name,
        brand_id,
        brand_href,

        meta_period_start: period_start,
        meta_period_end: period_end,
        meta_total: total,
        meta_range_start: min,
        meta_range_end: max,
    });
});

return { items, total_pages };