// impi — sc_browser/interaction_code_v1.js
// Browser worker (Chromium remoto con JS habilitado). Camino A del blueprint.
//
// Igual flujo de 3 hops que sc_code, pero con Browser worker para cuando el
// endpoint HTTP puro sea bloqueado (WAF con JS challenge, fingerprinting, etc).
//
// Flujo:
//   1. navigate("/marcas/search/quick") — el browser carga la home, guarda
//      la cookie XSRF-TOKEN en su jar y ejecuta cualquier bootstrap JS.
//      Leemos Set-Cookie desde response_headers() (BrightData lo expone en
//      ambos workers).
//   2. request(POST /record)  con headers X-XSRF-TOKEN + Cookie para crear la
//      búsqueda y obtener searchId.
//   3. request(POST /result)  con searchId para traer resultPage[].
//
// Inputs runtime:
//   input.owner                 string, default "Genomma"
//   input.expires_within_days   int,    default 90
//   input.page_size             int,    default 50
//
// Schema §2 emitido por collect() (idéntico al sc_code).
//
// Reglas del skill:
// - R1: navigate() plano top-level.
// - R5: timeouts 30s default para wait().
// - No hay parser_code real porque el payload es JSON; parse() NO se llama.
//   Se mantiene parser_code_v1.js como stub por convención.

const BASE_URL = 'https://marcia.impi.gob.mx';

// ---------- 0. Inputs + defaults --------------------------------------------

const owner       = (input && input.owner !== undefined)               ? input.owner               : 'Genomma';
const daysAhead   = (input && input.expires_within_days !== undefined) ? input.expires_within_days : 90;
const pageSize    = (input && input.page_size !== undefined)           ? input.page_size           : 50;

if (!owner || typeof owner !== 'string') bad_input('owner must be a non-empty string');
if (!Number.isInteger(daysAhead) || daysAhead < 0) bad_input('expires_within_days must be a non-negative integer');
if (!Number.isInteger(pageSize) || pageSize <= 0)  bad_input('page_size must be a positive integer');

function isoDate(d) { return d.toISOString().slice(0, 10); }
const today  = new Date();
const future = new Date(today.getTime() + daysAhead * 86400 * 1000);
const dateFrom = isoDate(today);
const dateTo   = isoDate(future);
const scrapedDate = dateFrom;

// ---------- 1. Init session: cargar la home en el browser -------------------

navigate(BASE_URL + '/marcas/search/quick');
// Esperar que el body tenga contenido (cualquier elemento común del SPA).
// Multi-selector 1-trip (R2): si el servicio responde con la home normal,
// veremos <app-root> o al menos <body>. Si responde con un challenge WAF,
// veremos elementos distintos — se documenta como E# si ocurre.
wait('app-root, body, main, #app, .search-container', { timeout: 30000 });

// Extraer XSRF-TOKEN del Set-Cookie de la respuesta del navigate.
const respHeaders = response_headers() || {};
const rawSetCookie = respHeaders['set-cookie'] || respHeaders['Set-Cookie'] || [];
const setCookieList = Array.isArray(rawSetCookie) ? rawSetCookie : [rawSetCookie];

let xsrfToken = null;
for (const raw of setCookieList) {
    if (!raw || typeof raw !== 'string') continue;
    const m = raw.match(/XSRF-TOKEN=([^;]+)/);
    if (m && m[1]) { xsrfToken = decodeURIComponent(m[1]); break; }
}

const flags = [];
if (!xsrfToken) {
    flags.push('xsrf_missing');
    // En browser worker el WAF puede hacer refresh silencioso; si no tenemos
    // token, mejor marcar blocked y dejar que la plataforma retire con nueva
    // peer session.
    blocked('xsrf_token_not_in_set_cookie');
}

// ---------- 2. POST /marcas/search/internal/record → searchId ---------------

function buildSearchPayload() {
    return {
        _type: 'Search$Structured',
        query: {
            number: null,
            classes: null,
            codes: null,
            title: null,
            titleOption: null,
            goodsAndServices: null,
            name: { types: ['OWNERS'], name: owner },
            date: { types: ['DATE_EXPIRY'], date: { from: dateFrom, to: dateTo } },
            indicators: null,
            status: ['REGISTRADO'],
            markType: null,
            appType: ['REGISTRO DE MARCA'],
            wordSet: null,
        },
        images: [],
    };
}

const commonHeaders = {
    'Content-Type':     'application/json;charset=UTF-8',
    'Accept':           'application/json, text/plain, */*',
    'X-XSRF-TOKEN':     xsrfToken,
    'X-Requested-With': 'XMLHttpRequest',
    'Cookie':           'XSRF-TOKEN=' + encodeURIComponent(xsrfToken),
    'Referer':          BASE_URL + '/marcas/search/quick',
    'Origin':           BASE_URL,
};

function parseJsonBody(resp) {
    if (!resp) return null;
    const raw = resp.body !== undefined ? resp.body : resp;
    if (raw === null || raw === undefined) return null;
    if (typeof raw === 'object') return raw;
    if (typeof raw === 'string') {
        const trimmed = raw.trim();
        if (!trimmed) return null;
        return JSON.parse(trimmed);
    }
    return null;
}

const recordResp = request({
    url:     BASE_URL + '/marcas/search/internal/record',
    method:  'POST',
    headers: commonHeaders,
    body:    JSON.stringify(buildSearchPayload()),
});

const recordData = parseJsonBody(recordResp);
const searchId   = recordData?.id ?? recordData?.searchId ?? null;

if (!searchId) {
    flags.push('record_no_search_id');
    blocked('record_endpoint_returned_no_search_id');
}

// ---------- 3. POST /marcas/search/internal/result → resultPage[] -----------

const resultResp = request({
    url:     BASE_URL + '/marcas/search/internal/result',
    method:  'POST',
    headers: commonHeaders,
    body:    JSON.stringify({ searchId: searchId, page: 0, size: pageSize }),
});

const resultData = parseJsonBody(resultResp);
const items = Array.isArray(resultData?.resultPage) ? resultData.resultPage : [];

if (!items.length) flags.push('result_page_empty');

const total = resultData?.totalElements ?? resultData?.total ?? null;
if (Number.isInteger(total) && total > items.length) flags.push('paginated');

// ---------- 4. Emit rows con schema §2 --------------------------------------

for (const item of items) {
    const rowFlags = flags.slice();
    const expectedOwner = owner.toLowerCase();
    const itemOwners = Array.isArray(item?.owners) ? item.owners : [];
    const firstOwner = itemOwners.length ? itemOwners[0] : null;
    if (firstOwner && typeof firstOwner === 'string'
        && firstOwner.toLowerCase().indexOf(expectedOwner) === -1) {
        rowFlags.push('owner_mismatch');
    }

    collect({
        denominacion:      item?.title ?? null,
        expediente:        item?.applicationNumber ?? null,
        registro:          item?.registrationNumber ?? null,
        titular:           firstOwner,
        fecha_terminacion: item?.dates?.expiry ?? null,
        fecha_cancelacion: item?.dates?.cancellation ?? null,
        fecha_solicitud:   item?.dates?.application ?? null,
        imagen:            item?.images ?? null,
        scraped_date:      scrapedDate,
        scraper_flags:     rowFlags,
    });
}

if (!items.length) {
    collect({
        denominacion:      null,
        expediente:        null,
        registro:          null,
        titular:           null,
        fecha_terminacion: null,
        fecha_cancelacion: null,
        fecha_solicitud:   null,
        imagen:            null,
        scraped_date:      scrapedDate,
        scraper_flags:     flags.concat(['no_results']),
    });
}
