"""DCATransport unit tests (``httpx.MockTransport`` at the wire boundary)."""

from __future__ import annotations

import json

import httpx
import pytest

from gli_scrapers.core.transports import DCATransport, TransportError

pytestmark = pytest.mark.asyncio

APIcore = "https://api.brightdata.com/dca"
API_KEY = "test-api-key"
COLLECTOR_ID = "c_test_collector"
JOB_ID = "j_demo_dca_0001"


# ---------------------------------------------------------------------------
# trigger
# ---------------------------------------------------------------------------


async def test_dca_trigger_ok(load_fixture, mock_client) -> None:
    body = load_fixture("dca_trigger_ok.json")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/dca/trigger"
        assert request.url.params["collector"] == COLLECTOR_ID
        # queue_next=1 is a DCATransport default (apéndice A §1).
        assert request.url.params["queue_next"] == "1"
        assert request.headers["authorization"] == f"Bearer {API_KEY}"
        sent = json.loads(request.content.decode("utf-8"))
        assert sent == [{"keyword": "foo"}]
        return httpx.Response(200, json=body)

    async with mock_client(handler) as http:
        out = await DCATransport().trigger(
            api_key=API_KEY,
            resource_id=COLLECTOR_ID,
            inputs=[{"keyword": "foo"}],
            http=http,
            apicore=APIcore,
        )
    assert out == JOB_ID


async def test_dca_trigger_4xx_invalid_inputs(mock_client) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text="bad seed")

    async with mock_client(handler) as http:
        with pytest.raises(TransportError) as exc_info:
            await DCATransport().trigger(
                api_key=API_KEY,
                resource_id=COLLECTOR_ID,
                inputs=[],
                http=http,
                apicore=APIcore,
            )
    assert exc_info.value.code == "INVALID_INPUTS"


async def test_dca_trigger_5xx_brightdata_error(mock_client) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="down")

    async with mock_client(handler) as http:
        with pytest.raises(TransportError) as exc_info:
            await DCATransport().trigger(
                api_key=API_KEY,
                resource_id=COLLECTOR_ID,
                inputs=[],
                http=http,
                apicore=APIcore,
            )
    assert exc_info.value.code == "BRIGHTDATA_ERROR"


async def test_dca_trigger_response_missing_collection_id(mock_client) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"oops": "no id"})

    async with mock_client(handler) as http:
        with pytest.raises(TransportError) as exc_info:
            await DCATransport().trigger(
                api_key=API_KEY,
                resource_id=COLLECTOR_ID,
                inputs=[],
                http=http,
                apicore=APIcore,
            )
    assert exc_info.value.code == "BRIGHTDATA_ERROR"


# NOTE: per dual-mode spec apéndice A §5 and task brief decision 5, we do NOT
# add ``test_dca_trigger_451`` — DCA does not document a 451 path. The generic
# 451 mapping in ``_raise_for_status_trigger`` still applies if it ever shows
# up, but we skip fabricating a test for it rather than inventing behaviour.


# ---------------------------------------------------------------------------
# poll
# ---------------------------------------------------------------------------


async def test_dca_poll_building_means_running(load_fixture, mock_client) -> None:
    body = load_fixture("dca_dataset_building.json")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/dca/dataset"
        assert request.url.params["id"] == JOB_ID
        return httpx.Response(200, json=body)

    async with mock_client(handler) as http:
        out = await DCATransport().poll(
            api_key=API_KEY,
            job_id=JOB_ID,
            http=http,
            apicore=APIcore,
        )
    assert out["status"] == "running"


async def test_dca_poll_array_means_ready(load_fixture, mock_client) -> None:
    body = load_fixture("dca_dataset_ready.json")

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    async with mock_client(handler) as http:
        out = await DCATransport().poll(
            api_key=API_KEY,
            job_id=JOB_ID,
            http=http,
            apicore=APIcore,
        )
    assert out["status"] == "ready"


async def test_dca_poll_failed(mock_client) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "failed", "message": "dca-boom"})

    async with mock_client(handler) as http:
        out = await DCATransport().poll(
            api_key=API_KEY,
            job_id=JOB_ID,
            http=http,
            apicore=APIcore,
        )
    assert out["status"] == "failed"
    assert "dca-boom" in out["message"]


async def test_dca_poll_empty_means_failed(mock_client) -> None:
    """``status=empty`` after a successful trigger means BrightData aborted
    the run without processing the seed (observed 2026-04-22 when the wire
    profile of the trigger is rejected). Must surface as ``failed``, not
    as "unknown dict → running" (which would loop the caller forever)."""
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "empty"})

    async with mock_client(handler) as http:
        out = await DCATransport().poll(
            api_key=API_KEY,
            job_id=JOB_ID,
            http=http,
            apicore=APIcore,
        )
    assert out["status"] == "failed"
    assert "empty" in out["message"].lower()
    assert "aborted" in out["message"].lower()


async def test_dca_poll_expired_is_invalid_inputs(mock_client) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "expired"})

    async with mock_client(handler) as http:
        with pytest.raises(TransportError) as exc_info:
            await DCATransport().poll(
                api_key=API_KEY,
                job_id=JOB_ID,
                http=http,
                apicore=APIcore,
            )
    assert exc_info.value.code == "INVALID_INPUTS"


async def test_dca_poll_404_invalid_inputs(mock_client) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="not found")

    async with mock_client(handler) as http:
        with pytest.raises(TransportError) as exc_info:
            await DCATransport().poll(
                api_key=API_KEY,
                job_id=JOB_ID,
                http=http,
                apicore=APIcore,
            )
    assert exc_info.value.code == "INVALID_INPUTS"


# ---------------------------------------------------------------------------
# download
# ---------------------------------------------------------------------------


async def test_dca_download_array(load_fixture, mock_client) -> None:
    body = load_fixture("dca_dataset_ready.json")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/dca/dataset"
        assert request.url.params["id"] == JOB_ID
        assert request.url.params["format"] == "json"
        return httpx.Response(200, json=body)

    async with mock_client(handler) as http:
        rows = await DCATransport().download(
            api_key=API_KEY,
            job_id=JOB_ID,
            http=http,
            apicore=APIcore,
        )
    assert isinstance(rows, list) and len(rows) == 2
    assert rows[0]["article_id"] == "FAKE_dca_row1"


async def test_dca_download_wrapped_defensive(mock_client) -> None:
    """DCA natively returns bare arrays but accept the v3-style wrap too."""
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"x": 1}]})

    async with mock_client(handler) as http:
        rows = await DCATransport().download(
            api_key=API_KEY,
            job_id=JOB_ID,
            http=http,
            apicore=APIcore,
        )
    assert rows == [{"x": 1}]


async def test_dca_download_still_building_errors(mock_client) -> None:
    """If download is called before ready, DCA returns dict → surface as error."""
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "building"})

    async with mock_client(handler) as http:
        with pytest.raises(TransportError) as exc_info:
            await DCATransport().download(
                api_key=API_KEY,
                job_id=JOB_ID,
                http=http,
                apicore=APIcore,
            )
    assert exc_info.value.code == "BRIGHTDATA_ERROR"
