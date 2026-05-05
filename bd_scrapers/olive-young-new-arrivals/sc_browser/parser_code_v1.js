// ============================================================
// STAGE 1 — PARSER CODE
// Extrae la lista de productos del New Arrivals.
// Retorna campos básicos + url para Stage 2.
// ============================================================

const BASE_URL = 'https://global.oliveyoung.com';
const scraped_date = new Date().toISOString().slice(0, 10);

function parsePrice(text) {
    if (!text) return null;
    const m = text.replace(/,/g, '').match(/[\d.]+/);
    return m ? m[0] : null;
}

const seen = new Set();
const products = [];

$('.unit-box').each((i, box) => {
    const corner_name = $(box).find('.unit-title h3.notranslate').text().trim() || null;
    const cornerImg = $(box).find('.unit-visual img').first();
    const rawSrc = cornerImg.attr('src') || '';
    const brand_image_url = cornerImg.attr('data-src') || (!rawSrc.includes('load.png') ? rawSrc : null) || null;

    $(box).find('.unit-list li').each((j, li) => {
        const prdt_no = $(li).find('input[name="prdtNo"]').val() || '';
        if (!prdt_no || seen.has(prdt_no)) return;
        seen.add(prdt_no);

        const product_name_en = $(li).find('input[name="prdtName"]').val() || null;
        const product_name_kr = $(li).find('input[name="korPrdtName"]').val() || null;
        const brand_name_en = $(li).find('.brand-info dt').text().trim() || null;

        const hrefRelative = $(li).find('a[href*="prdtNo"]').first().attr('href') || '';
        const url = new URL(hrefRelative, BASE_URL).href;

        const img = $(li).find('img.lazy').first();
        const image_url = img.attr('data-src') || img.attr('src') || null;

        const strongPoint = $(li).find('strong.point');
        const strongPlain = $(li).find('strong:not(.point)');
        const saleText = strongPoint.length
            ? strongPoint.text().trim()
            : strongPlain.first().text().trim();
        const sale_amt = parsePrice(saleText);

        const nrmlSpan = $(li).find('.price-info span:not(.set-value)').first();
        const nrml_amt = nrmlSpan.length ? parsePrice(nrmlSpan.text()) : null;

        const has_gift = $(li).find('.txt-gift').length > 0;

        products.push({
            prdt_no,
            url,
            product_name_en,
            product_name_kr,
            brand_name_en,
            brand_image_url,
            sale_amt,
            nrml_amt,
            image_url,
            has_gift,
            corner_name,
            scraped_date,
        });
    });
});

return { products };