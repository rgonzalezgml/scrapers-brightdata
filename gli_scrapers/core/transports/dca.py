"""BrightData DCA (Data Collectors Archive) legacy transport.

DCA is the API that precedes Datasets v3. BrightData still supports it for
scrapers published via the legacy Collectors interface (``c_...`` ids), and
some of the project's scrapers live there because they were set up before
Scraper Studio existed.

Reference — ``docs/fase3/middleware-dual-mode.md`` §4.1 and the legacy
smoke test ``scripts/test_connector.py``:

    POST /dca/trigger?collector=<c_...>&queue_next=1   → {"collection_id": ...}
    GET  /dca/dataset?id=<collection_id>               → {"status": "building"}
                                                         | [...rows]
                                                         | {"status": "failed", ...}
    GET  /dca/dataset?id=<collection_id>&format=json   → [...rows]

Quirks handled here:

- DCA does NOT expose a separate ``progress`` endpoint. The same URL
  (``/dca/dataset?id=...``) responds with a dict while the job is still
  building and with a bare array once ready.
- ``queue_next=1`` is set by default at trigger time (apéndice A §1 in the
  spec: "OK poner queue_next=1 como default").
- ``collection_id`` is treated as an opaque string — no prefix validation.
  BrightData has returned both ``c_...`` and ``j_...`` ids in the wild.
- **Header overrides (CRÍTICO — reconfirmado 2026-04-22)**. Observado
  2026-04-22 (primera observación): BrightData DCA rechazaba silenciosamente
  los triggers disparados con ``httpx.AsyncClient`` (y también ``httpx.Client``
  sync). El run se creaba, pero BrightData lo abortaba en ~1 minuto sin
  procesar la seed — aparecía como ``{"status": "empty"}`` en ``/dca/dataset``.
  El mismo trigger via ``curl`` se procesaba normalmente (51 pages). El fix
  original combinó dos cambios: (a) migrar producción a ``requests`` (sync,
  envuelto en ``asyncio.to_thread``) y (b) spoofear headers tipo curl
  (``User-Agent: curl/...``, ``Accept: */*``, ``Accept-Encoding: identity``,
  ``Connection: close``) — ver ``_DCA_COMPAT_HEADERS`` más abajo.

  El 2026-04-22 (tarde) se intentó remover el header spoofing bajo la
  hipótesis de que la migración a ``requests`` con sus headers default
  alcanzaba por sí sola. Se validó con un trigger real contra el collector
  de cosmetics-design (``c_mo7zv65x2914uyi2n4``): el trigger devolvía 200 OK
  con ``collection_id=j_moag1jkp2ihvtl5c3r``, el poll a los 30s respondía
  ``{"status": "building"}``, pero a los 60s y 120s respondía
  ``{"status": "empty"}`` — exactamente el mismo bug que el fix original
  buscaba neutralizar. Conclusión: **ambos** cambios son necesarios,
  ``requests`` solo NO alcanza. BrightData parece inspeccionar el wire
  profile del cliente y rechaza los defaults tanto de ``httpx`` como de
  ``requests``. No tocar ``_DCA_COMPAT_HEADERS`` de nuevo sin un test E2E
  contra BrightData real (con collector vivo y validación del dataset al
  menos ~90s post-trigger).

  Los tests siguen sobre ``httpx.AsyncClient`` + ``MockTransport`` porque
  ese path nunca tocó la red real; los compat headers son transparentes
  al mock.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import requests

from gli_scrapers.core.transports.base import (
    BaseTransport,
    TransportError,
    auth_headers,
    safe_text,
)


def _is_mock(http: httpx.AsyncClient) -> bool:
    """True when the AsyncClient is backed by ``httpx.MockTransport``.

    In test mode we stick to the async client so the existing mock harness
    keeps intercepting requests. In production we route DCA calls through
    ``requests`` (sync, wrapped in ``asyncio.to_thread``) because
    ``httpx.AsyncClient`` triggers get aborted by BrightData DCA (see module
    docstring for the empirical evidence)."""
    return isinstance(getattr(http, "_transport", None), httpx.MockTransport)


_SYNC_TIMEOUT = 30.0


# Compat headers spoofing a ``curl`` wire profile. See the module docstring
# (section "Header overrides") for the empirical evidence. BrightData DCA
# aborts runs whose trigger request carries the default User-Agent /
# Accept-Encoding of either ``httpx`` or ``requests``; sending these four
# keys is what makes the collector actually process the seed. Do NOT remove
# without running an E2E test against BrightData real.
_DCA_COMPAT_HEADERS: dict[str, str] = {
    "User-Agent": "curl/8.14.1",
    "Accept": "*/*",
    "Accept-Encoding": "identity",
    "Connection": "close",
}


def _dca_headers(api_key: str, *, extra: dict[str, str] | None = None) -> dict[str, str]:
    """Build the headers used by every DCA request.

    Merge order (later keys win): ``_DCA_COMPAT_HEADERS`` → ``auth_headers``
    → ``extra``. ``auth_headers`` sets ``Content-Type: application/json`` as
    a side effect; that's benign for GETs and intentional for the POST
    trigger.
    """
    return {**_DCA_COMPAT_HEADERS, **auth_headers(api_key), **(extra or {})}


def _req_post(
    url: str, *, params: dict[str, Any], headers: dict[str, str], json_body: Any
) -> requests.Response:
    return requests.post(url, params=params, headers=headers, json=json_body, timeout=_SYNC_TIMEOUT)


def _req_get(
    url: str, *, params: dict[str, Any], headers: dict[str, str]
) -> requests.Response:
    return requests.get(url, params=params, headers=headers, timeout=_SYNC_TIMEOUT)


def _log_request(
    tag: str,
    method: str,
    url: str,
    params: dict[str, Any],
    headers: dict[str, str],
    body: Any,
) -> None:
    """Log request details. Authorization value redacted."""
    safe_headers = {
        k: (v if k.lower() != "authorization" else f"Bearer <{len(v.split()[-1])}ch>")
        for k, v in headers.items()
    }
    import json as _json
    body_preview = _json.dumps(body, ensure_ascii=False) if body is not None else "<none>"
    print(
        f"[DCA/{tag}] {method} {url}\n"
        f"         params:  {params}\n"
        f"         headers: {safe_headers}\n"
        f"         body:    {body_preview}",
        flush=True,
    )


def _log_response(tag: str, resp: Any) -> None:
    """Works for both ``httpx.Response`` (tests) and ``requests.Response`` (prod)."""
    text = resp.text
    preview = text if len(text) <= 400 else text[:400] + f"...<truncated, total {len(text)}ch>"
    client = "httpx" if isinstance(resp, httpx.Response) else "requests"
    print(
        f"[DCA/{tag}] response {resp.status_code} via {client} "
        f"({resp.headers.get('content-type', '?')}, "
        f"{resp.headers.get('content-length', '?')} bytes)\n"
        f"         body: {preview}",
        flush=True,
    )


class DCATransport(BaseTransport):
    """Transport for BrightData DCA legacy API."""

    MODE = "dca"

    async def trigger(
        self,
        *,
        api_key: str,
        resource_id: str,
        inputs: list[dict[str, Any]],
        http: httpx.AsyncClient,
        apicore: str,
        trigger_params: dict[str, str] | None = None,
    ) -> str:
        url = f"{apicore}/trigger"
        extra = trigger_params if trigger_params is not None else {"queue_next": "1"}
        params = {"collector": resource_id, **extra}
        headers = _dca_headers(api_key, extra={"Content-Type": "application/json"})
        _log_request("TRIGGER", "POST", url, params, headers, inputs)
        try:
            if _is_mock(http):
                resp = await http.post(url, params=params, headers=headers, json=inputs)
            else:
                resp = await asyncio.to_thread(
                    _req_post, url, params=params, headers=headers, json_body=inputs
                )
        except (httpx.HTTPError, requests.RequestException) as e:
            print(f"[DCA] TRIGGER transport error: {e!s}", flush=True)
            raise TransportError(
                "BRIGHTDATA_ERROR",
                f"Transport error calling BrightData dca trigger: {e!s}",
            ) from e
        _log_response("TRIGGER", resp)

        _raise_for_status_trigger(resp, mode="dca")

        try:
            data = resp.json()
        except ValueError as e:
            raise TransportError(
                "BRIGHTDATA_ERROR",
                f"BrightData dca trigger returned non-JSON body: {safe_text(resp)}",
            ) from e

        collection_id = data.get("collection_id")
        if not collection_id:
            raise TransportError(
                "BRIGHTDATA_ERROR",
                f"BrightData dca trigger response missing collection_id: {data!r}",
            )
        return str(collection_id)

    async def poll(
        self,
        *,
        api_key: str,
        job_id: str,
        http: httpx.AsyncClient,
        apicore: str,
    ) -> dict[str, Any]:
        url = f"{apicore}/dataset"
        params = {"id": job_id}
        headers = _dca_headers(api_key)
        _log_request("POLL", "GET", url, params, headers, None)
        try:
            if _is_mock(http):
                resp = await http.get(url, params=params, headers=headers)
            else:
                resp = await asyncio.to_thread(
                    _req_get, url, params=params, headers=headers
                )
        except (httpx.HTTPError, requests.RequestException) as e:
            print(f"[DCA] POLL transport error: {e!s}", flush=True)
            raise TransportError(
                "BRIGHTDATA_ERROR",
                f"Transport error calling BrightData dca dataset (poll): {e!s}",
            ) from e
        _log_response("POLL", resp)

        _raise_for_status_poll(resp, mode="dca")

        try:
            raw = resp.json()
        except ValueError as e:
            raise TransportError(
                "BRIGHTDATA_ERROR",
                f"BrightData dca dataset returned non-JSON body: {safe_text(resp)}",
            ) from e

        return _normalize_dca_dataset(raw)

    async def download(
        self,
        *,
        api_key: str,
        job_id: str,
        http: httpx.AsyncClient,
        apicore: str,
    ) -> list[dict[str, Any]]:
        url = f"{apicore}/dataset"
        params = {"id": job_id, "format": "json"}
        headers = _dca_headers(api_key)
        _log_request("DOWNLOAD", "GET", url, params, headers, None)
        try:
            if _is_mock(http):
                resp = await http.get(url, params=params, headers=headers)
            else:
                resp = await asyncio.to_thread(
                    _req_get, url, params=params, headers=headers
                )
        except (httpx.HTTPError, requests.RequestException) as e:
            print(f"[DCA] DOWNLOAD transport error: {e!s}", flush=True)
            raise TransportError(
                "BRIGHTDATA_ERROR",
                f"Transport error calling BrightData dca dataset (download): {e!s}",
            ) from e
        _log_response("DOWNLOAD", resp)

        if resp.status_code >= 500:
            raise TransportError(
                "BRIGHTDATA_ERROR",
                f"BrightData dca dataset returned {resp.status_code}",
                details={"body": safe_text(resp)},
            )
        if resp.status_code >= 400:
            raise TransportError(
                "BRIGHTDATA_ERROR",
                f"BrightData dca dataset returned {resp.status_code}: {safe_text(resp)}",
            )

        try:
            payload = resp.json()
        except ValueError as e:
            raise TransportError(
                "BRIGHTDATA_ERROR",
                f"BrightData dca dataset returned non-JSON body: {safe_text(resp)}",
            ) from e

        # Defensive guard: DCA natively returns a bare array when the run is
        # ready, but accept the v3-style wrapping too in case BrightData
        # homogenizes the shape in the future.
        if isinstance(payload, dict) and "data" in payload:
            payload = payload["data"]
        if not isinstance(payload, list):
            # A dict here typically means the job is still building or has
            # failed — surface as a normalized transport error rather than
            # returning a malformed list.
            raise TransportError(
                "BRIGHTDATA_ERROR",
                f"BrightData dca dataset (download) is not a list: {type(payload).__name__} — {safe_text(resp)}",
            )
        return payload


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

_DCA_RUNNING = {"building", "running", "processing", "queued", "collecting"}
_DCA_READY = {"ready", "done", "completed", "success"}
_DCA_FAILED = {"failed", "error"}
_DCA_EXPIRED = {"expired", "deleted"}
# ``empty`` after a successful trigger means BrightData aborted the run
# without processing the seed (observed 2026-04-22 — see module docstring).
# Treat it as a terminal failure rather than letting the "unknown dict"
# fallback report it as ``running`` forever.
_DCA_EMPTY = {"empty"}


def _normalize_dca_dataset(raw: Any) -> dict[str, Any]:
    """Translate a DCA ``/dca/dataset`` payload to the cross-transport shape.

    The DCA dataset endpoint doubles as the progress endpoint. Shapes:

        - ``{"status": "building"}`` → running
        - ``{"status": "failed", "message": ...}`` → failed
        - ``{"status": "empty"}`` → failed (run aborted without processing
          the seed; observed 2026-04-22 when BrightData rejects the wire
          profile of the trigger — see module docstring)
        - ``{"status": "expired"|"deleted"}`` → INVALID_INPUTS (raised, not returned)
        - a JSON array of rows → ready
    """
    if isinstance(raw, list):
        return {"status": "ready", "raw": raw}
    if isinstance(raw, dict):
        status = str(raw.get("status", "")).lower()
        if status in _DCA_EXPIRED:
            raise TransportError(
                "INVALID_INPUTS",
                f"BrightData dca collection status={status!r} — job expired or deleted.",
            )
        if status in _DCA_FAILED:
            msg = raw.get("message") or raw.get("error") or "BrightData dca reported failure."
            return {"status": "failed", "message": str(msg), "raw": raw}
        if status in _DCA_EMPTY:
            return {
                "status": "failed",
                "message": "BrightData DCA dataset status=empty (run aborted without processing the seed)",
                "raw": raw,
            }
        if status in _DCA_RUNNING:
            return {"status": "running", "progress_pct": None, "raw": raw}
        if status in _DCA_READY:
            return {"status": "ready", "raw": raw}
        # Unknown dict → running with 0% so caller keeps polling.
        return {"status": "running", "progress_pct": 0, "raw": raw}
    # Anything else (scalar, None) is a contract violation.
    raise TransportError(
        "BRIGHTDATA_ERROR",
        f"BrightData dca dataset returned unexpected payload type: {type(raw).__name__}",
    )


def _raise_for_status_trigger(resp: httpx.Response, *, mode: str) -> None:
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
    code = resp.status_code
    if code >= 500:
        raise TransportError(
            "BRIGHTDATA_ERROR",
            f"BrightData {mode} dataset (poll) returned {code}",
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
            f"BrightData {mode} dataset (poll) returned {code} (auth): {safe_text(resp)}",
        )
    if code >= 400:
        raise TransportError(
            "BRIGHTDATA_ERROR",
            f"BrightData {mode} dataset (poll) returned {code}: {safe_text(resp)}",
        )
