"""V3Transport unit tests (``httpx.MockTransport`` at the wire boundary)."""

from __future__ import annotations

import json
from typing import Any, Callable

import httpx
import pytest

from middlewares.core.transports import TransportError, V3Transport

pytestmark = pytest.mark.asyncio

APIcore = "https://api.brightdata.com/datasets/v3"
API_KEY = "test-api-key"
DATASET_ID = "gd_test_dataset"
SNAPSHOT_ID = "s_demo_v3_0001"


# ---------------------------------------------------------------------------
# trigger
# ---------------------------------------------------------------------------


async def test_v3_trigger_ok(load_fixture, mock_client) -> None:
    """200 with ``{"snapshot_id": ...}`` → returns that id."""
    body = load_fixture("v3_trigger_ok.json")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/datasets/v3/trigger"
        assert request.url.params["dataset_id"] == DATASET_ID
        assert request.headers["authorization"] == f"Bearer {API_KEY}"
        # Body is the seeds list.
        sent = json.loads(request.content.decode("utf-8"))
        assert sent == [{"url": "https://example.com"}]
        return httpx.Response(200, json=body)

    async with mock_client(handler) as http:
        out = await V3Transport().trigger(
            api_key=API_KEY,
            resource_id=DATASET_ID,
            inputs=[{"url": "https://example.com"}],
            http=http,
            apicore=APIcore,
        )
    assert out == SNAPSHOT_ID


async def test_v3_trigger_4xx_invalid_inputs(mock_client) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text="bad payload")

    async with mock_client(handler) as http:
        with pytest.raises(TransportError) as exc_info:
            await V3Transport().trigger(
                api_key=API_KEY,
                resource_id=DATASET_ID,
                inputs=[],
                http=http,
                apicore=APIcore,
            )
    assert exc_info.value.code == "INVALID_INPUTS"


async def test_v3_trigger_5xx_brightdata_error(mock_client) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(502, text="bad gateway")

    async with mock_client(handler) as http:
        with pytest.raises(TransportError) as exc_info:
            await V3Transport().trigger(
                api_key=API_KEY,
                resource_id=DATASET_ID,
                inputs=[],
                http=http,
                apicore=APIcore,
            )
    assert exc_info.value.code == "BRIGHTDATA_ERROR"


async def test_v3_trigger_451_site_blocked(mock_client) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(451, text="blocked for legal reasons")

    async with mock_client(handler) as http:
        with pytest.raises(TransportError) as exc_info:
            await V3Transport().trigger(
                api_key=API_KEY,
                resource_id=DATASET_ID,
                inputs=[],
                http=http,
                apicore=APIcore,
            )
    assert exc_info.value.code == "SITE_BLOCKED"


async def test_v3_trigger_response_missing_snapshot_id(mock_client) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"oops": "no id"})

    async with mock_client(handler) as http:
        with pytest.raises(TransportError) as exc_info:
            await V3Transport().trigger(
                api_key=API_KEY,
                resource_id=DATASET_ID,
                inputs=[],
                http=http,
                apicore=APIcore,
            )
    assert exc_info.value.code == "BRIGHTDATA_ERROR"


# ---------------------------------------------------------------------------
# poll
# ---------------------------------------------------------------------------


async def test_v3_poll_running(load_fixture, mock_client) -> None:
    body = load_fixture("v3_progress_running.json")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == f"/datasets/v3/progress/{SNAPSHOT_ID}"
        return httpx.Response(200, json=body)

    async with mock_client(handler) as http:
        out = await V3Transport().poll(
            api_key=API_KEY,
            job_id=SNAPSHOT_ID,
            http=http,
            apicore=APIcore,
        )
    assert out["status"] == "running"
    assert isinstance(out["progress_pct"], int)
    assert 0 <= out["progress_pct"] <= 100


async def test_v3_poll_ready(load_fixture, mock_client) -> None:
    body = load_fixture("v3_progress_ready.json")

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    async with mock_client(handler) as http:
        out = await V3Transport().poll(
            api_key=API_KEY,
            job_id=SNAPSHOT_ID,
            http=http,
            apicore=APIcore,
        )
    assert out["status"] == "ready"


async def test_v3_poll_failed(mock_client) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "failed", "message": "boom"})

    async with mock_client(handler) as http:
        out = await V3Transport().poll(
            api_key=API_KEY,
            job_id=SNAPSHOT_ID,
            http=http,
            apicore=APIcore,
        )
    assert out["status"] == "failed"
    assert "boom" in out["message"]


async def test_v3_poll_404_invalid_inputs(mock_client) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="not found")

    async with mock_client(handler) as http:
        with pytest.raises(TransportError) as exc_info:
            await V3Transport().poll(
                api_key=API_KEY,
                job_id=SNAPSHOT_ID,
                http=http,
                apicore=APIcore,
            )
    assert exc_info.value.code == "INVALID_INPUTS"


async def test_v3_poll_unknown_status_keeps_running(mock_client) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "WhateverNewState"})

    async with mock_client(handler) as http:
        out = await V3Transport().poll(
            api_key=API_KEY,
            job_id=SNAPSHOT_ID,
            http=http,
            apicore=APIcore,
        )
    assert out["status"] == "running"


# ---------------------------------------------------------------------------
# download
# ---------------------------------------------------------------------------


async def test_v3_download_array(load_fixture, mock_client) -> None:
    body = load_fixture("v3_snapshot.json")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == f"/datasets/v3/snapshot/{SNAPSHOT_ID}"
        assert request.url.params["format"] == "json"
        return httpx.Response(200, json=body)

    async with mock_client(handler) as http:
        rows = await V3Transport().download(
            api_key=API_KEY,
            job_id=SNAPSHOT_ID,
            http=http,
            apicore=APIcore,
        )
    assert isinstance(rows, list) and len(rows) == 2
    assert rows[0]["article_id"] == "FAKE_v3_row1"


async def test_v3_download_wrapped(mock_client) -> None:
    """v3 sometimes wraps rows as ``{"data": [...]}``; transport unwraps."""
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"x": 1}, {"x": 2}]})

    async with mock_client(handler) as http:
        rows = await V3Transport().download(
            api_key=API_KEY,
            job_id=SNAPSHOT_ID,
            http=http,
            apicore=APIcore,
        )
    assert rows == [{"x": 1}, {"x": 2}]


async def test_v3_download_non_list_errors(mock_client) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "shape"})

    async with mock_client(handler) as http:
        with pytest.raises(TransportError) as exc_info:
            await V3Transport().download(
                api_key=API_KEY,
                job_id=SNAPSHOT_ID,
                http=http,
                apicore=APIcore,
            )
    assert exc_info.value.code == "BRIGHTDATA_ERROR"
