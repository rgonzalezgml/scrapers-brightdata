// impi — sc_code/interaction_code_v1.js
// Code worker (HTTP puro, sin browser). Traduce el blueprint XHR del compañero
// al DSL de BrightData Scraper Studio.
//
// Flujo (3 HTTP hops):
//   1. navigate(BASE + "/marcas/search/quick")       → server setea cookie XSRF-TOKEN
//      Leemos response_headers()['set-cookie'] y extraemos XSRF-TOKEN.
//   2. request(POST /marcas/search/internal/record)  → crea búsqueda estructurada
//      Body: payload tipo Search$Structured con titular + rango de fechas.
//      Response JSON: {id | searchId, ...}.
//   3. request(POST /marcas/search/internal/result)  → devuelve resultPage[].
//      Iteramos y collect() una fila por marca con el schema §2 del mini-spec.
//
// Inputs runtime (con defaults del mini-spec):
//   input.owner                 string, default "Genomma"
//   input.expires_within_days   int,    default 90
//   input.page_size             int,    default 50
//
// Schema §2 emitido por collect():
//   denominacion, expediente, registro, titular, fecha_terminacion,
//   fecha_cancelacion, fecha_solicitud, imagen, scraped_date, scraper_flags
//
// Notas DSL:
// - R1: navigate() plano top-level.
// - R7/R11/R12: parser sin try/catch, text_sane, toArray().map — no aplica
//   acá porque NO hay parser_code (el payload es JSON puro, no HTML).
//   Incluimos parser_code_v1.js stub por convención del módulo (para cuando
//   BrightData exija su existencia).
// - request() retorno asumido: {body, headers, status_code}. Si el runtime
//   devuelve un shape distinto (ej. body ya parseado como string/object),
//   el try-safe acceso vía ?. y el JSON.parse defensivo cubren las variantes.

const BASE_URL = 'https://marcia.impi.gob.mx';

// ---------- 0. Inputs + defaults --------------------------------------------

const owner       = (input && input.owner !== undefined)               ? input.owner               : 'Genomma';
const daysAhead   = (input && input.expires_within_days !== undefined) ? input.expires_within_days : 90;
const pageSize    = (input && input.page_size !== undefined)           ? input.page_size           : 50;

if (!owner || typeof owner !== 'string') bad_input('owner must be a non-empty string');
if (!Number.isInteger(daysAhead) || daysAhead < 0) bad_input('expires_within_days must be a non-negative integer');
if (!Number.isInteger(pageSize) || pageSize <= 0)  bad_input('page_size must be a positive integer');

// Fecha helpers (YYYY-MM-DD, UTC).
function isoDate(d) { return d.toISOString().slice(0, 10); }
const today  = new Date();
const future = new Date(today.getTime() + daysAhead * 86400 * 1000);
const dateFrom = isoDate(today);
const dateTo   = isoDate(future);
const scrapedDate = dateFrom;

// ---------- 1. Init session (GET /marcas/search/quick) ----------------------

navigate(BASE_URL + '/marcas/search/quick');

// Extraer cookie XSRF-TOKEN del Set-Cookie del servidor.
// response_headers() retorna un objeto; el valor de set-cookie puede venir
// como string o array (varía por implementación). Normalizamos a lista.
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
    // Sin XSRF el sitio rechaza el POST con 403. Bloquear el run: puede ser
    // anti-bot, cambio de scheme, o que la cookie llega en un segundo hop
    // (redirect). Los runs posteriores con nueva peer pueden cubrirlo.
    flags.push('xsrf_missing');
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

const recordResp = request({
    url:     BASE_URL + '/marcas/search/internal/record',
    method:  'POST',
    headers: commonHeaders,
    body:    JSON.stringify(buildSearchPayload()),
});

// Normalizar body (puede venir como string o como objeto ya parseado).
function parseJsonBody(resp) {
    if (!resp) return null;
    const raw = resp.body !== undefined ? resp.body : resp;
    if (raw === null || raw === undefined) return null;
    if (typeof raw === 'object') return raw;
    if (typeof raw === 'string') {
        const trimmed = raw.trim();
        if (!trimmed) return null;
        // JSON.parse puede arrojar — lo dejamos tirar el run; v2 puede sofistificar.
        return JSON.parse(trimmed);
    }
    return null;
}

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

// Flag paginado si hay más páginas pero no las estamos trayendo en v1.
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

// Si no se emitió ninguna fila pero la búsqueda fue exitosa, dejamos una fila
// diagnóstica con solo flags. Útil para ver que el pipeline corrió y que no
// hay matches (owner sin marcas próximas a vencer).
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
