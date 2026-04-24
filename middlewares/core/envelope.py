"""Normalized response envelope shared by every middleware.

Shape (per ``docs/specs/memory.md`` Etapa 3 and ``docs/fase3/README.md``):

    {
      "source": "<name>",
      "scraped_at": "YYYY-MM-DDTHH:MM:SSZ",
      "inputs": {...},
      "data":   [...],
      "meta":   {"rows": int, "emitted": int, ...}
    }

``data[]`` is **not** validated here — its shape lives in
``docs/specs/scrapers/<name>.md`` §2 and is the responsibility of each
scraper-specific ``models.py``. We pass it through as ``list[dict]`` to keep
``core`` agnostic of any single scraper schema.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def _utc_now_iso() -> str:
    """ISO 8601 UTC string with second precision and trailing ``Z``."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Envelope(BaseModel):
    """Uniform envelope returned by ``get_result`` when ``status == "done"``.

    The set of keys is fixed (see test ``test_envelope_shape``). Adding new
    top-level keys is a contract change — coordinate with the agents repo.
    """

    model_config = ConfigDict(extra="forbid")

    source: str
    scraped_at: str = Field(default_factory=_utc_now_iso)
    inputs: dict[str, Any]
    data: list[dict[str, Any]]
    meta: dict[str, Any] = Field(default_factory=dict)
