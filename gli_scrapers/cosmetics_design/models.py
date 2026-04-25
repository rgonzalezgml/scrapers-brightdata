"""Pydantic v2 models for the ``cosmetics_design`` middleware.

- ``CosmeticsDesignInputs`` — public inputs validated *before* calling
  BrightData. Validation failure = ``INVALID_INPUTS`` (no API call made).
- ``Article`` — schema for each item in ``envelope["data"]``. Mirrors §2 + §4
  of ``docs/specs/scrapers/cosmetics-design.md`` exactly. The schema is
  **immutable** and matches what ``scrapers/cosmetics-design/sc_code/parser_code_v1.js``
  emits per row.

The middleware is a thin wrapper: we validate the *shape* of each row but
never reinterpret semantics — if BrightData omits a field, we surface it as
``null`` (or empty list for list-typed fields) per spec §8.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

# ---- Public inputs ----------------------------------------------------------

# Region tags as emitted by the JS parser_code_v1.js (region_tags derived from
# section_paths with ``/Regions/`` prefix; see spec §6 and parser code line ~195).
RegionFilter = Literal[
    "North-America",
    "Europe",
    "Asia-Pacific",
    "Latin-America",
]


class CosmeticsDesignInputs(BaseModel):
    """Public inputs accepted by ``trigger()``.

    These are the *agent-facing* knobs (see handoff §2.3). They are translated
    to the JS scraper's runtime inputs (``max_pages``, ``supplier``) inside
    ``CosmeticsDesignClient._build_brightdata_inputs``.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    window_days: Annotated[int, Field(ge=1, le=365)] = 180
    """Days back from now to keep articles, computed on ``display_date``
    (spec §7). Out-of-window articles are *counted* but not emitted, except
    when ``mode == "full-refresh"``."""

    max_articles: Annotated[int, Field(ge=1, le=5000)] = 1000
    """Hard cap on emitted rows (spec §7 — also bounded by BrightData's own
    5000-request / 90-minute global cap)."""

    region_filter: RegionFilter | None = None
    """Optional. If set, the consumer (agents repo) filters the envelope's
    ``data[]`` to articles whose ``region_tags`` include this value. Note:
    the JS scraper does NOT pre-filter by region (the landing covers all
    regions; region is derived per-article from CMS taxonomy)."""

    mode: Literal["incremental", "full-refresh"] = "incremental"
    """``incremental`` honors ``window_days``; ``full-refresh`` emits every
    article regardless of ``display_date``. Translation to JS-scraper input
    happens via ``max_pages`` heuristic (see config.ARTICLES_PER_PAGE)."""


# ---- Article (envelope.data[N]) ---------------------------------------------

# These are the 26 keys emitted by sc_code/parser_code_v1.js (20 from spec §2
# + 6 additional from spec §4). Order mirrors the parser's ``return {...}``.


class Article(BaseModel):
    """One item in ``envelope["data"]``. Schema fixed by spec §2 + §4.

    Pydantic intentionally allows ``None`` for almost every field: the parser
    emits explicit ``null`` rather than dropping the key (spec §8). List-typed
    fields default to empty list, never ``None`` (also spec §8).
    """

    # ``extra="forbid"`` would be too strict — the JS parser may add new flags
    # over time and we want the middleware to forward those without breaking.
    # We use ``extra="allow"`` to forward unknown keys verbatim, so the agents
    # repo can opt into them.
    model_config = ConfigDict(extra="allow")

    # ---- §2 strict (always present, may be null/[]) ------------------------
    article_id: str | None = None
    url: str | None = None
    slug: str | None = None
    headline: str | None = None
    display_date: str | None = None
    publish_date: str | None = None
    last_updated_date: str | None = None
    website: str | None = None
    supplier: str | None = None
    subtype: str | None = None
    author_names: list[str] = Field(default_factory=list)
    primary_section_path: str | None = None
    section_paths: list[str] = Field(default_factory=list)
    region_tags: list[str] = Field(default_factory=list)
    topic_tags: list[str] = Field(default_factory=list)
    body_text: str | None = None
    body_word_count: int | None = None
    promo_image_url: str | None = None
    paywalled: bool = False
    scraped_date: str | None = None

    # ---- §4 additional (frequent, null when missing) -----------------------
    subheadline: str | None = None
    description: str | None = None
    author_slugs: list[str] = Field(default_factory=list)
    promo_image_caption: str | None = None
    first_publish_date: str | None = None
    scraper_flags: list[str] = Field(default_factory=list)


# Canonical ordered tuple of field names — used by the client to guarantee
# all keys are emitted on every row (spec §8: "todas las claves presentes con
# null explicito cuando falten").
ARTICLE_FIELDS: tuple[str, ...] = tuple(Article.model_fields.keys())

# Fields that must be a list (never null) on the wire (spec §8).
ARTICLE_LIST_FIELDS: frozenset[str] = frozenset(
    {
        "author_names",
        "section_paths",
        "region_tags",
        "topic_tags",
        "author_slugs",
        "scraper_flags",
    }
)
