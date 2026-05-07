// interaction_code_v4.js — sc_browser (Browser worker)
// Cambio vs v3 (sc_code): Stage 1 migra de Rankings API (bloqueada, E8) a HTML
// listing https://global.oliveyoung.com/display/page/best-seller con Cloudflare
// bypass nativo del Browser worker. Stage 2 (product detail enrichment) es
// idéntico a v2. Arregla: E8.
//
// Arquitectura:
//   input.url contiene '/product/detail' → Stage 2 (igual que interaction_code_v2.js)
//   input.url vacío o apunta al listing → Stage 1 HTML listing (nuevo en v4)
//
// Stage 1 flujo:
//   1. navigate best-seller listing
//   2. Guard Cloudflare challenge iframe → flag cloudflare_challenge, detener
//   3. wait para que cargue cualquier tab de contenido
//   4. Tab USA: ya activo por defecto — extraer con $() inline → collect rows
//   5. Tab Korea: click #pillsTab1Nav2 → wait activo → extraer → collect rows
//   6. Deduplicar prdt_no (misma URL puede estar en ambos tabs) para enrichment
//   7. next_stage({url}) para productos vistos en ambos tabs, máx 10 enrichments
//
// Nota Stage 1 parser: la extracción se hace inline con $() en interaction code
// porque parse() resuelve contra el DOM en ese momento; no es posible pasar
// contexto entre dos navigate() en el mismo execution (R9, R8). parser_code_v4
// solo maneja Stage 2 (product detail).

const LISTING_URL = 'https://global.oliveyoung.com/display/page/best-seller';
const PRDT_NO_RE = /^GA\d{8,12}$/;
const MAX_ENRICHMENTS = 20;

// ── Stage dispatch ────────────────────────────────────────────────────────────

if (input.url && /\/product\/detail/i.test(input.url)) {
  // ── Stage 2: product detail enrichment (idéntico a v2) ───────────────────

  // Guard: .co.kr out-of-scope (E1)
  if (/oliveyoung\.co\.kr/i.test(input.url)) {
    collect({
      entity: 'product',
      product_url: input.url,
      scraper_flags: ['source_gone'],
    });
  } else {
    navigate(input.url, { allow_status: [200, 400, 404, 410] });

    // Guard: Cloudflare challenge (E2)
    if (el_exists('iframe[src*="cdn-cgi/challenge-platform"]', 3000)) {
      collect({
        entity: 'product',
        product_url: input.url,
        scraper_flags: ['cloudflare_challenge'],
      });
    } else if (el_exists('.main.type-error.error-not-found', 2000)) {
      // Guard: 404 product not found
      dead_page('product_not_found');
    } else {
      // Wait for Vue to render the product name (up to 15s — spec §5 requires full Vue exec)
      if (!el_exists('[data-testid=product-name]', 15000)) {
        collect({
          entity: 'product',
          product_url: input.url,
          scraper_flags: ['product_enrich_failed'],
        });
      } else {
        collect(parse());
      }
    }
  }

} else {
  // ── Stage 1: HTML listing extraction ─────────────────────────────────────

  const listing_url = (input.url && input.url.trim()) ? input.url : LISTING_URL;
  const scraped_date = new Date().toISOString().slice(0, 10);

  // cap max_pages to [1, 10] — spec §8
  const raw_max = parseInt(input.max_pages, 10);
  const max_enrichments = (!isNaN(raw_max) && raw_max >= 1) ? Math.min(raw_max, MAX_ENRICHMENTS) : MAX_ENRICHMENTS;

  navigate(listing_url, { allow_status: [200, 404, 410] });

  // Guard: Cloudflare challenge (E2) — check before waiting for real content
  if (el_exists('iframe[src*="cdn-cgi/challenge-platform"]', 5000)) {
    collect({
      entity: 'ranking',
      site_code: 'oliveyoung-global',
      scraped_date,
      scraper_flags: ['cloudflare_challenge'],
    });
  } else {

    // Wait for listing content — either tab can be first
    if (!el_exists('#orderBestProduct, #koreaBestProduct', 15000)) {
      collect({
        entity: 'ranking',
        site_code: 'oliveyoung-global',
        scraped_date,
        scraper_flags: ['listing_load_failed'],
      });
    } else {

      // Track all prdt_no across both tabs for enrichment dedup
      // prdt_no → count of tabs it appeared in
      const seen = {};
      let enrichment_count = 0;

      // ── Tab USA ─────────────────────────────────────────────────────────
      // Tab USA (#pillsTab1Nav1) is active by default — no click needed.
      // Wait for its content container just in case JS deferred render.
      if (!el_exists('#pillsTab1Cont1', 10000)) {
        collect({
          entity: 'ranking',
          site_code: 'oliveyoung-global',
          region_code: 'USA',
          category_id: '1000000001',
          scraped_date,
          scraper_flags: ['listing_load_failed'],
        });
      } else {
        // Extract US products inline — .map() unsupported in interaction worker
        const us_lis = $('#orderBestProduct li');
        const us_items = [];
        for (let ii = 0; ii < us_lis.length; ii++) {
          const el = us_lis.eq(ii);
          const prdt_no_raw = el.find('input[name="prdtNo"]').attr('value') || '';
          const href = el.find('a[href*="/product/detail"]').attr('href') || '';
          const href_match = href.match(/[?&]prdtNo=([^&]+)/);
          const prdt_no = prdt_no_raw || (href_match ? href_match[1] : '');
          if (!PRDT_NO_RE.test(prdt_no)) continue;
          const product_url = 'https://global.oliveyoung.com/product/detail?prdtNo=' + prdt_no;
          const name_raw = el.find('.prd-name, .name, [class*="name"]').first().text_sane() || null;
          const brand_raw = el.find('.prd-brand, .brand, [class*="brand"]').first().text_sane() || null;
          const rate_raw = el.find('.rating, [class*="rating"], [class*="rate"]').first().text_sane() || null;
          const img_src = el.find('img').first().attr('src') || null;
          us_items.push({ prdt_no, product_url, name_raw, brand_raw, rate_raw, img_src });
        }

        for (let i = 0; i < us_items.length; i++) {
          const item = us_items[i];
          const rank = i + 1;
          const ranking_id = 'oliveyoung-global_USA_1000000001_' + rank + '_' + scraped_date;

          // Rate validation
          const rate_parsed = parseFloat(item.rate_raw);
          let rate = null;
          const rate_flags = [];
          if (item.rate_raw) {
            if (!isNaN(rate_parsed) && rate_parsed >= 0 && rate_parsed <= 5) {
              rate = rate_parsed;
            } else {
              rate_flags.push('rating_invalid');
            }
          }

          collect({
            entity: 'ranking',
            ranking_id,
            site_code: 'oliveyoung-global',
            region_code: 'USA',
            category_id: '1000000001',
            category_name: 'All',
            rank,
            prdt_no: item.prdt_no,
            product_url: item.product_url,
            product_name_en: item.name_raw || null,
            product_name_kr: null,
            brand_name_en: item.brand_raw || null,
            brand_name_kr: null,
            brand_no: null,
            rate,
            original_price: null,
            sale_price: null,
            is_soldout: null,
            has_coupon: null,
            has_gift: null,
            promotion_name: null,
            thumbnail_img_url_raw: item.img_src || null,
            thumbnail_img_url_full: null,
            scraped_date,
            scraper_flags: rate_flags,
          });

          // Track for enrichment
          seen[item.prdt_no] = (seen[item.prdt_no] || 0) + 1;
        }
      }

      // ── Tab Korea ────────────────────────────────────────────────────────
      // Click the Korea tab and wait for it to become active
      if (!el_exists('#pillsTab1Nav2', 5000)) {
        collect({
          entity: 'ranking',
          site_code: 'oliveyoung-global',
          region_code: 'KR',
          category_id: '1000000001',
          scraped_date,
          scraper_flags: ['listing_load_failed'],
        });
      } else {
        click('#pillsTab1Nav2');

        if (!el_exists('#pillsTab1Nav2.active', 10000)) {
          collect({
            entity: 'ranking',
            site_code: 'oliveyoung-global',
            region_code: 'KR',
            category_id: '1000000001',
            scraped_date,
            scraper_flags: ['listing_load_failed'],
          });
        } else if (!el_exists('#pillsTab1Cont2', 10000)) {
          collect({
            entity: 'ranking',
            site_code: 'oliveyoung-global',
            region_code: 'KR',
            category_id: '1000000001',
            scraped_date,
            scraper_flags: ['listing_load_failed'],
          });
        } else {
          // Extract KR products inline — .map() unsupported in interaction worker
          const kr_lis = $('#koreaBestProduct li');
          const kr_items = [];
          for (let ii = 0; ii < kr_lis.length; ii++) {
            const el = kr_lis.eq(ii);
            const prdt_no_raw = el.find('input[name="prdtNo"]').attr('value') || '';
            const href = el.find('a[href*="/product/detail"]').attr('href') || '';
            const href_match = href.match(/[?&]prdtNo=([^&]+)/);
            const prdt_no = prdt_no_raw || (href_match ? href_match[1] : '');
            if (!PRDT_NO_RE.test(prdt_no)) continue;
            const product_url = 'https://global.oliveyoung.com/product/detail?prdtNo=' + prdt_no;
            const name_raw = el.find('.prd-name, .name, [class*="name"]').first().text_sane() || null;
            const brand_raw = el.find('.prd-brand, .brand, [class*="brand"]').first().text_sane() || null;
            const rate_raw = el.find('.rating, [class*="rating"], [class*="rate"]').first().text_sane() || null;
            const img_src = el.find('img').first().attr('src') || null;
            kr_items.push({ prdt_no, product_url, name_raw, brand_raw, rate_raw, img_src });
          }

          for (let i = 0; i < kr_items.length; i++) {
            const item = kr_items[i];
            const rank = i + 1;
            const ranking_id = 'oliveyoung-global_KR_1000000001_' + rank + '_' + scraped_date;

            const rate_parsed = parseFloat(item.rate_raw);
            let rate = null;
            const rate_flags = [];
            if (item.rate_raw) {
              if (!isNaN(rate_parsed) && rate_parsed >= 0 && rate_parsed <= 5) {
                rate = rate_parsed;
              } else {
                rate_flags.push('rating_invalid');
              }
            }

            collect({
              entity: 'ranking',
              ranking_id,
              site_code: 'oliveyoung-global',
              region_code: 'KR',
              category_id: '1000000001',
              category_name: 'All',
              rank,
              prdt_no: item.prdt_no,
              product_url: item.product_url,
              product_name_en: item.name_raw || null,
              product_name_kr: null,
              brand_name_en: item.brand_raw || null,
              brand_name_kr: null,
              brand_no: null,
              rate,
              original_price: null,
              sale_price: null,
              is_soldout: null,
              has_coupon: null,
              has_gift: null,
              promotion_name: null,
              thumbnail_img_url_raw: item.img_src || null,
              thumbnail_img_url_full: null,
              scraped_date,
              scraper_flags: rate_flags,
            });

            // Track for enrichment — products in both tabs get next_stage
            seen[item.prdt_no] = (seen[item.prdt_no] || 0) + 1;
          }

          // ── Enrichment: next_stage for products appearing in both tabs ────
          // After both tabs processed, iterate seen and fire next_stage for
          // prdt_no with count >= 2 (appeared in both USA and KR), up to cap.
          const seen_keys = Object.keys(seen);
          for (let k = 0; k < seen_keys.length; k++) {
            const prdt_no = seen_keys[k];
            if (seen[prdt_no] >= 2 && enrichment_count < max_enrichments) {
              const product_url = 'https://global.oliveyoung.com/product/detail?prdtNo=' + prdt_no;
              rerun_stage({ url: product_url });
              enrichment_count++;
            }
          }
        }
      }
    }
  }
}
