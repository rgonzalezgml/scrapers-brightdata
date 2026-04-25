"""Cliente HTTP del middleware IMPI.

Flujo:
    1. GET  /marcas/search/quick                          → cookie XSRF-TOKEN
    2. POST /marcas/search/internal/record                → searchId
    3. POST /marcas/search/internal/result  (paginado)    → filas del listado
    4. GET  /marcas/search/internal/view/{id}  (opcional) → detalle por marca
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from impi_scraper_mx.errors import (
    IMPIAPIError,
    SearchIdMissingError,
    TimeoutError,
    XSRFMissingError,
)
from impi_scraper_mx.models import Marca, SearchInputs, SearchResult

logger = logging.getLogger("impi_scraper_mx.client")

BASE_URL = "https://marcia.impi.gob.mx"
HOME_PATH = "/marcas/search/quick"
RECORD_PATH = "/marcas/search/internal/record"
RESULT_PATH = "/marcas/search/internal/result"
VIEW_PATH = "/marcas/search/internal/view/{id}"


class IMPIClient:
    def __init__(self, timeout: float = 30.0, base_url: str = BASE_URL) -> None:
        self.core_url = base_url.rstrip("/")
        self._http = httpx.Client(
            base_url=self.core_url,
            timeout=timeout,
            follow_redirects=True,
        )
        self._xsrf: str | None = None

    def __enter__(self) -> "IMPIClient":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------
    def search(self, inputs: SearchInputs) -> SearchResult:
        self._ensure_xsrf()
        search_id = self._post_record(inputs)
        rows_raw, total, pages = self._fetch_all_pages(
            search_id, inputs.page_size, inputs.max_marks
        )

        scraped_date = datetime.now(timezone.utc).date().isoformat()
        marcas = [self._map_row(item, inputs.owner, scraped_date) for item in rows_raw]

        if inputs.fetch_details and marcas:
            self._enrich_with_details(marcas, inputs.detail_concurrency)

        return SearchResult(
            rows=marcas,
            total=total,
            search_id=search_id,
            fetched=len(marcas),
            pages=pages,
        )

    def get_detail(self, mark_id: str) -> dict[str, Any]:
        """GET /marcas/search/internal/view/{id} — detalle del expediente."""
        self._ensure_xsrf()
        path = VIEW_PATH.format(id=mark_id)
        return self._safe_request("GET", path)

    # ------------------------------------------------------------------
    # Hops
    # ------------------------------------------------------------------
    def _ensure_xsrf(self) -> str:
        if self._xsrf:
            return self._xsrf
        self._safe_get(HOME_PATH)
        xsrf = self._http.cookies.get("XSRF-TOKEN") or ""
        if not xsrf:
            self._safe_get(HOME_PATH)
            xsrf = self._http.cookies.get("XSRF-TOKEN") or ""
        if not xsrf:
            raise XSRFMissingError("XSRF-TOKEN no emitida tras GET /quick")
        self._xsrf = xsrf
        return xsrf

    def _post_record(self, inputs: SearchInputs) -> str:
        payload = self._build_payload(inputs.owner, inputs.expires_within_days)
        data = self._safe_request("POST", RECORD_PATH, json_body=payload)
        search_id = data.get("id") or data.get("searchId")
        if not search_id:
            raise SearchIdMissingError(
                f"record no devolvió id/searchId: keys={list(data)[:10]}"
            )
        return str(search_id)

    def _fetch_all_pages(
        self, search_id: str, page_size: int, max_marks: int | None
    ) -> tuple[list[dict[str, Any]], int, int]:
        acc: list[dict[str, Any]] = []
        page = 0
        total = 0
        while True:
            body = {
                "searchId": search_id,
                "pageNumber": page,
                "pageSize": page_size,
                "statusFilter": [],
                "viennaCodeFilter": [],
                "niceClassFilter": [],
            }
            data = self._safe_request("POST", RESULT_PATH, json_body=body)
            page_rows = data.get("resultPage") or []
            total = int(data.get("totalResults") or total)
            if not page_rows:
                break
            acc.extend(page_rows)
            logger.debug(
                "page %d → +%d rows (acc=%d / total=%d)",
                page, len(page_rows), len(acc), total,
            )
            if max_marks is not None and len(acc) >= max_marks:
                acc = acc[:max_marks]
                break
            if len(acc) >= total:
                break
            page += 1
        return acc, total, page + 1

    def _enrich_with_details(self, marcas: list[Marca], concurrency: int) -> None:
        # Iterar por posición — robusto frente a ids duplicados.
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = {
                pool.submit(self.get_detail, m.id): i
                for i, m in enumerate(marcas) if m.id
            }
            for f in as_completed(futures):
                i = futures[f]
                m = marcas[i]
                try:
                    m.detalle = self.shape_detail(f.result())
                except IMPIAPIError as e:
                    m.scraper_flags.append(f"detail_http_{e.status_code}")
                except Exception as e:  # noqa: BLE001 — prototipo, flag y seguí
                    m.scraper_flags.append("detail_error")
                    logger.warning("detail failed for %s: %s", m.id, e)

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------
    def _safe_get(self, path: str) -> httpx.Response:
        try:
            r = self._http.get(path)
        except httpx.TimeoutException as exc:
            raise TimeoutError(f"Timeout GET {path}: {exc}") from exc
        self._raise_for_status(r)
        return r

    def _safe_request(
        self,
        method: str,
        path: str,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self._xsrf:
            self._ensure_xsrf()
        headers = {
            "Accept": "application/json",
            "X-XSRF-TOKEN": self._xsrf or "",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"{self.core_url}{HOME_PATH}",
        }
        if json_body is not None:
            headers["Content-Type"] = "application/json;charset=UTF-8"
        try:
            r = self._http.request(method, path, headers=headers, json=json_body)
        except httpx.TimeoutException as exc:
            raise TimeoutError(f"Timeout {method} {path}: {exc}") from exc
        self._raise_for_status(r)
        try:
            return r.json()
        except ValueError as exc:
            raise IMPIAPIError(
                status_code=r.status_code, body=r.text, url=str(r.request.url)
            ) from exc

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if 200 <= response.status_code < 300:
            return
        raise IMPIAPIError(
            status_code=response.status_code,
            body=response.text,
            url=str(response.request.url),
        )

    # ------------------------------------------------------------------
    # Payload
    # ------------------------------------------------------------------
    @staticmethod
    def _build_payload(owner: str, days: int | None) -> dict[str, Any]:
        query: dict[str, Any] = {
            "number": None,
            "classes": None,
            "codes": None,
            "title": None,
            "titleOption": None,
            "goodsAndServices": None,
            "name": {"types": ["OWNERS"], "name": owner},
            "date": None,
            "indicators": None,
            "status": None,
            "markType": None,
            "appType": ["REGISTRO DE MARCA"],
            "wordSet": None,
        }
        if days is not None:
            today = datetime.now(timezone.utc).date()
            query["date"] = {
                "types": ["DATE_EXPIRY"],
                "date": {
                    "from": today.isoformat(),
                    "to": (today + timedelta(days=days)).isoformat(),
                },
            }
        return {"_type": "Search$Structured", "query": query, "images": []}

    # ------------------------------------------------------------------
    # Mapping
    # ------------------------------------------------------------------
    @staticmethod
    def _map_row(item: dict[str, Any], owner: str, scraped_date: str) -> Marca:
        owners = item.get("owners") or []
        titular = owners[0] if owners else None
        dates = item.get("dates") or {}
        classes = item.get("classes") or []

        flags: list[str] = []
        if titular is None or owner.lower() not in titular.lower():
            flags.append("owner_mismatch")

        return Marca(
            id=item.get("id"),
            denominacion=item.get("title"),
            expediente=item.get("applicationNumber"),
            registro=item.get("registrationNumber"),
            estatus=item.get("status"),
            tipo_solicitud=item.get("appType"),
            titular=titular,
            clases=[c for c in classes if isinstance(c, int)],
            productos_servicios=item.get("goodsAndServices") or None,
            fecha_solicitud=dates.get("application"),
            fecha_terminacion=dates.get("expiry"),
            fecha_cancelacion=dates.get("cancellation"),
            imagen=item.get("images"),
            scraped_date=scraped_date,
            scraper_flags=flags,
        )

    @staticmethod
    def shape_detail(raw: dict[str, Any]) -> dict[str, Any]:
        details = raw.get("details") or {}
        history = raw.get("historyData") or {}
        trademark = details.get("trademark") or {}
        return {
            "general_information": details.get("generalInformation"),
            "products_and_services": details.get("productsAndServices") or [],
            "vienna_codes": trademark.get("viennaCodes"),
            "trademark_image": trademark.get("image"),
            "owner_information": details.get("ownerInformation"),
            "prioridad": details.get("prioridad") or [],
            "history_records": history.get("historyRecords") or [],
        }
