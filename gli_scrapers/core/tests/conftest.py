"""Pytest config for ``gli_scrapers/core/tests/``.

Provides a shared fixtures dir and a helper for building
``httpx.MockTransport`` instances that simulate BrightData responses.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

import httpx
import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> Any:
    with (FIXTURES_DIR / name).open("r", encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture
def load_fixture() -> Callable[[str], Any]:
    return _load_fixture


def _mock_client(
    handler: Callable[[httpx.Request], httpx.Response],
) -> httpx.AsyncClient:
    """Build an ``httpx.AsyncClient`` backed by an in-process mock transport.

    Using ``httpx.MockTransport`` (as opposed to ``unittest.mock.patch``) keeps
    the tests at the transport boundary — we exercise real URL routing and
    real header handling, we just intercept the wire.
    """
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.fixture
def mock_client() -> Callable[[Callable[[httpx.Request], httpx.Response]], httpx.AsyncClient]:
    return _mock_client
