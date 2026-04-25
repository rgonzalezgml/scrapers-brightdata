"""BrightData Datasets v3 transport.

Direct extraction of the REST plumbing that used to live inline in
:class:`BaseScraperClient`. No semantic change — the base client used to
perform these same calls, now delegated through the :class:`BaseTransport`
interface so a sibling ``DCATransport`` can live next to it.

Reference (handoff §3 / ``docs/fase3/cosmetics-design-handoff.md``):

    POST  /datasets/v3/trigger?dataset_id=<id>          → {"snapshot_id": ...}
    GET   /datasets/v3/progress/<snapshot_id>            → {"status": ..., ...}
    GET   /datasets/v3/snapshot/<snapshot_id>?format=json → list of rows
"""

from __future__ import annotations

from typing import Any

import httpx

from gli_scrapers.core.transports.base import (
    BaseTransport,
    TransportError,
    auth_headers,
    safe_text,
)


class V3Transport(BaseTransport):
    """Transport for BrightData Datasets v3."""

    MODE = "v3"

    async def trigger(
        self,
        *,
        api_key: str,
        resource_id: str,
        inputs: list[dict[str, Any]],
        http: httpx.AsyncClient,
        apicore: str,
    ) -> str:
        url = f"{apicore}/trigger"
        params = {"dataset_id": resource_id}
        try:
            resp = await http.post(
                url,
                params=params,
                headers=auth_headers(api_key),
                json=inputs,
            )
        except httpx.HTTPError as e:
            raise TransportError(
                "BRIGHTDATA_ERROR",
                f"Transport error calling BrightData v3 trigger: {e!s}",
            ) from e

        _raise_for_status_trigger(resp, mode="v3")

        try:
            data = resp.json()
        except ValueError as e:
            raise TransportError(
                "BRIGHTDATA_ERROR",
                f"BrightData v3 trigger returned non-JSON body: {safe_text(resp)}",
            ) from e

        snapshot_id = data.get("snapshot_id")
        if not snapshot_id:
            raise TransportError(
                "BRIGHTDATA_ERROR",
                f"BrightData v3 trigger response missing snapshot_id: {data!r}",
            )
        return str(snapshot_id)

    async def poll(
        self,
        *,
        api_key: str,
        job_id: str,
        http: httpx.AsyncClient,
        apicore: str,
    ) -> dict[str, Any]:
        url = f"{apicore}/progress/{job_id}"
        try:
            resp = await http.get(url, headers=auth_headers(api_key))
        except httpx.HTTPError as e:
            raise TransportError(
                "BRIGHTDATA_ERROR",
                f"Transport error calling BrightData v3 progress: {e!s}",
            ) from e

        _raise_for_status_poll(resp, mode="v3")

        try:
            raw = resp.json()
        except ValueError as e:
            raise TransportError(
                "BRIGHTDATA_ERROR",
                f"BrightData v3 progress returned non-JSON body: {safe_text(resp)}",
            ) from e

        return _normalize_v3_progress(raw)

    async def download(
        self,
        *,
        api_key: str,
        job_id: str,
        http: httpx.AsyncClient,
        apicore: str,
    ) -> list[dict[str, Any]]:
        url = f"{apicore}/snapshot/{job_id}"
        try:
            resp = await http.get(
                url,
                params={"format": "json"},
                headers=auth_headers(api_key),
            )
        except httpx.HTTPError as e:
            raise TransportError(
                "BRIGHTDATA_ERROR",
                f"Transport error calling BrightData v3 snapshot: {e!s}",
            ) from e

        if resp.status_code >= 500:
            raise TransportError(
                "BRIGHTDATA_ERROR",
                f"BrightData v3 snapshot returned {resp.status_code}",
                details={"body": safe_text(resp)},
            )
        if resp.status_code >= 400:
            raise TransportError(
                "BRIGHTDATA_ERROR",
                f"BrightData v3 snapshot returned {resp.status_code}: {safe_text(resp)}",
            )

        try:
            payload = resp.json()
        except ValueError as e:
            raise TransportError(
                "BRIGHTDATA_ERROR",
                f"BrightData v3 snapshot returned non-JSON body: {safe_text(resp)}",
            ) from e

        # Defensive: some v3 endpoints wrap rows in {"data": [...]}.
        if isinstance(payload, dict) and "data" in payload:
            payload = payload["data"]
        if not isinstance(payload, list):
            raise TransportError(
                "BRIGHTDATA_ERROR",
                f"BrightData v3 snapshot payload is not a list: {type(payload).__name__}",
            )
        return payload


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

_V3_RUNNING = {"running", "processing", "queued", "collecting", "ready_to_run"}
_V3_READY = {"ready", "done", "completed", "success"}
_V3_FAILED = {"failed", "error"}


def _normalize_v3_progress(raw: dict[str, Any]) -> dict[str, Any]:
    """Translate a v3 ``progress`` payload to the cross-transport shape."""
    status = str(raw.get("status", "")).lower()
    if status in _V3_RUNNING:
        return {"status": "running", "progress_pct": _coerce_pct(raw), "raw": raw}
    if status in _V3_FAILED:
        msg = raw.get("message") or raw.get("error") or "BrightData v3 reported failure."
        return {"status": "failed", "message": str(msg), "raw": raw}
    if status in _V3_READY:
        return {"status": "ready", "raw": raw}
    # Unknown state: treat as still running (0%), consistent with legacy
    # behaviour in CosmeticsDesignClient.get_result.
    return {"status": "running", "progress_pct": 0, "raw": raw}


def _coerce_pct(progress: dict[str, Any]) -> int | None:
    for key in ("progress", "progress_pct", "percent", "percentage"):
        v = progress.get(key)
        if isinstance(v, (int, float)):
            return max(0, min(100, int(v)))
    rows = progress.get("rows") or progress.get("rows_collected")
    expected = progress.get("expected_rows") or progress.get("rows_expected")
    if (
        isinstance(rows, (int, float))
        and isinstance(expected, (int, float))
        and expected > 0
    ):
        return max(0, min(100, int(rows * 100 / expected)))
    return None


def _raise_for_status_trigger(resp: httpx.Response, *, mode: str) -> None:
    """Map trigger HTTP status codes to normalized transport errors (§4.3)."""
    code = resp.status_code
    if code >= 500:
        raise TransportError(
            "BRIGHTDATA_ERROR",
            f"BrightData {mode} trigger returned {code}",
            details={"body": safe_text(resp)},
        )
    if code == 451:
        raise TransportError(
            "SITE_BLOCKED",
            f"BrightData {mode} trigger returned 451 (legal/block): {safe_text(resp)}",
        )
    if code in (401, 403):
        raise TransportError(
            "INVALID_INPUTS",
            f"BrightData {mode} trigger returned {code} (auth): {safe_text(resp)}",
        )
    if code >= 400:
        raise TransportError(
            "INVALID_INPUTS",
            f"BrightData {mode} trigger returned {code}: {safe_text(resp)}",
        )


def _raise_for_status_poll(resp: httpx.Response, *, mode: str) -> None:
    """Map poll HTTP status codes to normalized transport errors (§4.3)."""
    code = resp.status_code
    if code >= 500:
        raise TransportError(
            "BRIGHTDATA_ERROR",
            f"BrightData {mode} progress returned {code}",
            details={"body": safe_text(resp)},
        )
    if code == 404:
        raise TransportError(
            "INVALID_INPUTS",
            f"job_id not found on BrightData {mode} (404).",
        )
    if code in (401, 403):
        raise TransportError(
            "INVALID_INPUTS",
            f"BrightData {mode} progress returned {code} (auth): {safe_text(resp)}",
        )
    if code >= 400:
        raise TransportError(
            "BRIGHTDATA_ERROR",
            f"BrightData {mode} progress returned {code}: {safe_text(resp)}",
        )
