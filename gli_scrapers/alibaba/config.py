"""Static configuration for the ``alibaba`` middleware.

Mirrors the pattern of ``gli_scrapers/cosmetics_design/config.py`` and
``gli_scrapers/cosme/config.py``. All secret/environment values are resolved
lazily via env vars (see ``BaseScraperClient._ensure_credentials``). This
module only exposes constant defaults — never read ``os.getenv`` at import
time for required secrets, so downstream code (tests, type checkers) can
import without crashing.

Dual-mode resolution
--------------------

alibaba can run against either BrightData transport:

    - **Datasets v3** (modern, ``gd_...``) — the target once the scraper is
      migrated to Scraper Studio in the dashboard.
    - **DCA legacy** (``c_.../j_...``) — the state described in the spec (the
      genomma lab §2 prose names ``BRIGHTDATA_COLLECTOR_ID`` explicitly as the
      DCA collector the Python connector uses today).

The middleware picks the mode based on which env var the user has populated.
See ``docs/fase3/middleware-dual-mode.md`` §3.
"""

from __future__ import annotations

import os
from typing import Literal

# ---- BrightData --------------------------------------------------------------

# Source name as it appears in the envelope (matches scrapers/<name>/ folder).
SOURCE_NAME: str = "alibaba"

# Env var that holds the BrightData **dataset id** for this scraper (v3 mode).
DATASET_ID_ENV_VAR: str = "BRIGHTDATA_DATASET_ID_ALIBABA"

# Env var that holds the BrightData **collector id** for this scraper (DCA
# legacy mode). Spec genomma lab §2 calls this ``BRIGHTDATA_COLLECTOR_ID`` but
# for consistency with every other middleware we use the scraper-qualified
# name. The agents repo is responsible for populating one of these.
COLLECTOR_ID_ENV_VAR: str = "BRIGHTDATA_COLLECTOR_ID_ALIBABA"


def get_dataset_id() -> str | None:
    """Resolve the BrightData dataset id (v3) from the environment.

    Returns ``None`` if the env var is unset; the client surfaces this as an
    ``INVALID_INPUTS`` error at trigger time (never at import time).
    """
    return os.getenv(DATASET_ID_ENV_VAR)


def get_collector_id() -> str | None:
    """Resolve the BrightData collector id (DCA legacy) from the environment.

    Returns ``None`` if the env var is unset.
    """
    return os.getenv(COLLECTOR_ID_ENV_VAR)


ApiMode = Literal["v3", "dca"]


def resolve_mode_and_id() -> tuple[ApiMode | None, str | None]:
    """Decide ``(api_mode, resource_id)`` based on the populated env vars.

    Precedence (per dual-mode spec §3.3):

        1. If ``DATASET_ID`` is set → ``("v3", dataset_id)``. v3 wins over DCA
           when both are populated — that means the user migrated to Studio
           and the DCA leftover should be ignored.
        2. Else if ``COLLECTOR_ID`` is set → ``("dca", collector_id)``.
        3. Else → ``(None, None)`` — let the client raise ``INVALID_INPUTS``
           at trigger time with a hint that names both env vars.

    No prefix validation on the resource id (treated as an opaque string).
    """
    ds = get_dataset_id()
    col = get_collector_id()
    if ds:
        return ("v3", ds)
    if col:
        return ("dca", col)
    return (None, None)


# Human-readable hint used in the INVALID_INPUTS error message when neither
# env var is populated (surfaced via ``BaseScraperClient.CREDENTIAL_HINT``).
CREDENTIAL_HINT: str = (
    "Set one of:\n"
    f"  {DATASET_ID_ENV_VAR}   (for Datasets v3, gd_...)\n"
    f"  {COLLECTOR_ID_ENV_VAR} (for DCA legacy, c_...)"
)

# ---- Scraper-side defaults ---------------------------------------------------

# Spec genomma lab §3: the canonical listing URL template.
SEARCH_URL_TMPL: str = (
    "https://www.alibaba.com/trade/search?SearchText={term}&has4Tab=true"
)


def search_url(term: str) -> str:
    """Build the canonical Alibaba trade-search URL for a keyword.

    The JS Stage 1 interaction code accepts the URL directly via ``input.url``
    or derives it from ``input.search_keyword`` (vendor interaction code
    lines 3-8). Passing the full URL is more predictable than trusting the
    scraper's own URL-building logic, so we build it here and send it as
    ``input.url``.
    """
    # Alibaba uses ``+`` (space-as-plus) rather than ``%20`` in its own
    # querystrings; match that exactly so downstream analytics / deduplication
    # by URL works predictably.
    encoded = str(term).strip().replace(" ", "+")
    return SEARCH_URL_TMPL.format(term=encoded)


# Spec genomma lab §3: the 5 default seed keywords spanning chemicals +
# packaging. Kept in code (not configurable via env) so the default run shape
# is reproducible. Caller can override with ``search_terms=[...]``.
DEFAULT_SEARCH_TERMS: tuple[str, ...] = (
    "industrial chemicals",
    "industrial packaging drums barrels",
    "sodium hydroxide industrial",
    "hydrochloric acid industrial",
    "chemical packaging containers",
)

# Spec genomma lab §3: connector-Python default is max_pages=3; Stage 1 JS is
# max_pages=5. The middleware takes the Stage-1 default so we match what the
# deployed scraper does on a default trigger.
DEFAULT_MAX_PAGES: int = 5
MAX_PAGES_HARD_CAP: int = 10
"""JS interaction code caps at ``Math.min(input.max_pages || 5, 10)``
(scrapers/alibaba/vendor/sc_browser/interaction_code.js line 32). The
middleware mirrors that upper bound rather than letting callers send a value
the scraper will silently clamp."""

# Spec genomma lab §3: default proxy / supplier_country is CN. We forward it
# as an explicit field so downstream filtering (``input.supplier_country``
# consumed by the Stage 1 filter) has a deterministic default.
DEFAULT_SUPPLIER_COUNTRY: str = "CN"

# Spec genomma lab §3: price-range defaults used by the Stage 1 filter
# (``input.min_price`` / ``input.max_price``). The vendor interaction code
# reads them and skips cards outside the range. Exposing as middleware
# constants (rather than env vars) keeps the default run reproducible; a
# caller that wants a narrower band can pass them explicitly.
DEFAULT_MIN_PRICE: float = 1.0
DEFAULT_MAX_PRICE: float = 10000.0

# ---- Country → ISO-2 mapping (spec §4 "supplier_country string ISO-2") -------

# The scraper-side interaction code emits ISO-2 from the country flag img
# (src matches ``/<iso>.png``; see vendor/sc_browser/interaction_code.js line
# 51-53). But the detail-page scraper is looser: it reads text labels like
# ``"China"``, ``"United States"``. The spec §4 mandates ISO-2, so the
# middleware normalizes the text labels with a small local table (no external
# dependency — we stay stateless). Unmapped countries emit ``null`` and
# ``country_unmapped`` lands in ``scraper_flags`` so Stage 3 fixers can expand
# this table later.
#
# This table covers the majority of Alibaba supplier countries by volume. It
# is NOT exhaustive — unknown labels fall through to ``null``.
COUNTRY_TO_ISO2: dict[str, str] = {
    # lower-cased keys; we .strip().lower() before the lookup
    "china": "CN",
    "china mainland": "CN",
    "people's republic of china": "CN",
    "prc": "CN",
    "taiwan": "TW",
    "hong kong": "HK",
    "hong kong sar": "HK",
    "india": "IN",
    "united states": "US",
    "usa": "US",
    "u.s.a.": "US",
    "united kingdom": "GB",
    "uk": "GB",
    "germany": "DE",
    "france": "FR",
    "italy": "IT",
    "spain": "ES",
    "netherlands": "NL",
    "belgium": "BE",
    "poland": "PL",
    "turkey": "TR",
    "turkiye": "TR",
    "vietnam": "VN",
    "thailand": "TH",
    "malaysia": "MY",
    "singapore": "SG",
    "indonesia": "ID",
    "philippines": "PH",
    "japan": "JP",
    "south korea": "KR",
    "korea, republic of": "KR",
    "korea": "KR",
    "pakistan": "PK",
    "bangladesh": "BD",
    "russia": "RU",
    "russian federation": "RU",
    "brazil": "BR",
    "mexico": "MX",
    "canada": "CA",
    "australia": "AU",
    "new zealand": "NZ",
    "uae": "AE",
    "united arab emirates": "AE",
    "saudi arabia": "SA",
    "egypt": "EG",
    "south africa": "ZA",
    "chile": "CL",
    "colombia": "CO",
    "argentina": "AR",
    "peru": "PE",
    "ukraine": "UA",
    "switzerland": "CH",
    "austria": "AT",
    "czech republic": "CZ",
    "czechia": "CZ",
    "sweden": "SE",
    "norway": "NO",
    "finland": "FI",
    "denmark": "DK",
    "ireland": "IE",
    "portugal": "PT",
    "greece": "GR",
}


def country_to_iso2(value: str | None) -> tuple[str | None, bool]:
    """Map a free-text country name to ISO-2.

    Returns ``(iso_code, unmapped_flag)``:
        - If ``value`` is already a plausible ISO-2 (two uppercase letters), we
          pass it through verbatim (``(value, False)``) — the Stage 1 flag
          extractor emits ISO-2 directly.
        - If ``value`` matches an entry in :data:`COUNTRY_TO_ISO2`, return the
          mapped code.
        - If ``value`` is ``None``/empty/whitespace, return ``(None, False)``
          (missing data, not an unmapped country).
        - Otherwise return ``(None, True)`` — the caller adds the
          ``country_unmapped`` flag to ``scraper_flags``.
    """
    if not value or not isinstance(value, str):
        return (None, False)
    stripped = value.strip()
    if not stripped:
        return (None, False)
    # Fast path: already ISO-2.
    if len(stripped) == 2 and stripped.isalpha() and stripped.isupper():
        return (stripped, False)
    key = stripped.lower()
    mapped = COUNTRY_TO_ISO2.get(key)
    if mapped:
        return (mapped, False)
    return (None, True)


# ---- Saturation thresholds (per-scraper errors) ------------------------------

# Spec §10 flags include ``captcha_detected``, ``rate_limit_blocked``,
# ``schema_change``. If a majority of rows emit a blocking flag or miss a
# price, the run is materially useless and the middleware surfaces a
# domain-specific error (analogous to cosmetics-design's PAYWALL_SATURATION
# and cosme's BLOCK_SATURATION).
BLOCK_SATURATION_THRESHOLD: float = 0.5
"""Fraction of emitted product rows with ``captcha_detected`` or
``rate_limit_blocked`` above which BLOCK_SATURATION fires."""

MISSING_PRICE_SATURATION_THRESHOLD: float = 0.7
"""Fraction of emitted product rows with ``price_min_usd is None`` above
which PRICE_MISSING_SATURATION fires. Alibaba's value proposition is price
data — a run where >70% of products lack price is effectively empty and
should fail loud rather than be cached by the agents repo."""

# ---- Misc --------------------------------------------------------------------

# Estimated runtime, surfaced in ``trigger()`` as ``eta_seconds``. Spec §3
# (genomma lab) gives timeout_minutes=15 as the hard budget; a typical 5-term
# run at max_pages=5 sits around 8-10 minutes (Stage 1 listing is fast; Stage
# 2 detail fetch is the bottleneck at ~1-2s/card x 5 pages x ~40 cards x 5
# terms). 10 minutes is a safe middle estimate.
DEFAULT_ETA_SECONDS: int = 60 * 10


# ---- Snowflake mapper --------------------------------------------------------

from gli_scrapers.snowflake import SnowflakeMapper  # noqa: E402

_DB     = os.getenv("SNOWFLAKE_DATABASE", "DEV_STG")
_SCHEMA = os.getenv("SNOWFLAKE_SCHEMA", "GNM_MEX")

MAPPER = SnowflakeMapper(
    table=f"{_DB}.{_SCHEMA}.SRC_ALIBABA_PROV_HIST",
    source="alibaba",
    field_map={
        "product_url":           "URL_PRODUCTO",
        "product_name_original":  "NM_PRODUCTO",
        "cleaned_product_name":   "NM_PRODUCTO",
        "supplier_name":         "NM_PROVEEDOR",
        "price_raw":             "TX_PRECIO_RAW",
        "price_min_usd":         "NU_PRECIO_MIN_USD",
        "price_max_usd":         "NU_PRECIO_MAX_USD",
        "price_unit":            "TX_UNIDAD_PRECIO",
        "minimum_order_quantity": "TX_MOQ",
        "cas_number":            "TX_CAS",
        "purity":                "TX_PUREZA",
        "status_code":           "NU_STATUS_CODE",
        "input":                 "DS_INPUT",
    },
    variant_fields={"DS_INPUT"},
)
