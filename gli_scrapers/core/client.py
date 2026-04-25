"""``BaseScraperClient`` — thin async wrapper around BrightData.

Every scraper-specific client (e.g. ``CosmeticsDesignClient``) inherits from
this. Subclasses provide:

    - ``SOURCE_NAME`` (str): scraper name as it appears in the envelope.
    - ``API_MODE`` (``"v3"`` | ``"dca"``): picks the BrightData transport.
      Default is ``"v3"`` — override in ``__init__`` of the subclass if the
      scraper lives in the DCA legacy API.
    - ``_build_brightdata_inputs(public_inputs)``: translation from public
      inputs (the pydantic model) to the JS scraper's runtime inputs (what
      ``input.<key>`` reads inside ``sc_browser/`` / ``sc_code/``).
    - ``_build_envelope(snapshot_payload, public_inputs)``: normalize the raw
      BrightData snapshot into the project envelope.

This base only implements the BrightData REST plumbing (trigger, poll,
download) via a pluggable :class:`BaseTransport`. It does NOT manage cache,
DB, or retries — that lives in the agents repo. See
``docs/fase3/README.md`` "Regla de oro".

For the dual-mode design see ``docs/fase3/middleware-dual-mode.md``.
"""

from __future__ import annotations

import os
from typing import Any, ClassVar, Literal

import httpx

from gli_scrapers.core.errors import ScraperError
from gli_scrapers.core.transports import (
    BaseTransport,
    DCATransport,
    TransportError,
    V3Transport,
)

# Default BrightData Datasets v3 base URL — used when ``API_MODE == "v3"``
# and the subclass does not override ``APIcore``.
DEFAULT_APIcore = "https://api.brightdata.com/datasets/v3"

# Default BrightData DCA legacy base URL — used when ``API_MODE == "dca"``.
DEFAULT_DCA_APIcore = "https://api.brightdata.com/dca"

# Default request timeout for individual HTTP calls (NOT the wall-time budget
# of a snapshot, which is a BrightData-side concern). 60s is conservative for
# the trigger/progress endpoints which typically respond in <2s.
DEFAULT_HTTP_TIMEOUT = 60.0


# Class-level cache of stateless transport instances. One per mode — safe to
# share across subclasses because transports hold no mutable state.
_TRANSPORTS: dict[str, BaseTransport] = {
    "v3": V3Transport(),
    "dca": DCATransport(),
}


ApiMode = Literal["v3", "dca"]


class BaseScraperClient:
    """Subclass per scraper. Stateless — safe to instantiate per call."""

    # ---- subclass overrides -------------------------------------------------

    SOURCE_NAME: ClassVar[str] = ""
    """Scraper name used in the envelope's ``source`` field. Hyphenated (e.g.
    ``"cosmetics-design"``) — matches ``scrapers/<name>/`` folder name."""

    API_MODE: ClassVar[ApiMode] = "v3"
    """Which BrightData transport to use. ``"v3"`` (Datasets v3 REST) is the
    default. ``"dca"`` selects the legacy Data Collectors Archive API. See
    ``docs/fase3/middleware-dual-mode.md``.

    Subclasses whose mode depends on the environment (e.g. cosmetics-design,
    which runs in whichever mode the user populates) should leave this as
    ``"v3"`` and pass ``api_mode=...`` to :meth:`__init__` instead.
    """

    APIcore: ClassVar[str | None] = None
    """Optional override for the BrightData base URL. Leave as ``None`` to use
    the default that matches :attr:`API_MODE` (``/datasets/v3`` or ``/dca``).
    """

    HTTP_TIMEOUT: ClassVar[float] = DEFAULT_HTTP_TIMEOUT

    CREDENTIAL_HINT: ClassVar[str] = ""
    """Free-form message shown in the INVALID_INPUTS error when no resource id
    is configured. Each subclass is encouraged to set this to a two-line hint
    naming the scraper-specific env vars. Optional — if empty the base emits a
    generic fallback message.
    """

    # Legacy: subclasses that hard-code a dataset id as a class attribute still
    # work because we fall back to this when ``resource_id`` is not provided.
    # New subclasses should NOT set this — pass the id through ``__init__``.
    DATASET_ID: ClassVar[str | None] = None

    DCA_TRIGGER_PARAMS: ClassVar[dict[str, str] | None] = None
    """Optional override for the query-string params appended to the DCA
    trigger URL. ``None`` (default) tells :class:`DCATransport` to use its
    built-in default ``{"queue_next": "1"}``. Set to e.g.
    ``{"confirm_cancel": "1"}`` in a subclass to swap the param for that
    scraper only.
    """

    # ---- construction -------------------------------------------------------

    def __init__(
        self,
        api_key: str | None = None,
        resource_id: str | None = None,
        *,
        api_mode: ApiMode | None = None,
        http_client: httpx.AsyncClient | None = None,
        # Backwards-compat alias for ``resource_id``. Silent (no warning) per
        # the dual-mode spec §7 item 5 and apéndice A §3. Remove in a future
        # release after auditing downstream callers.
        dataset_id: str | None = None,
    ) -> None:
        # Resolve credentials lazily: missing values are tolerated at
        # construction time so importing the module never blows up; we only
        # raise when the caller actually tries to ``trigger``.
        self._api_key = api_key if api_key is not None else os.getenv("BRIGHTDATA_API_KEY")

        # ``dataset_id=`` is a silent alias for ``resource_id=`` during the
        # v3→dual transition. Explicit ``resource_id=`` wins if both are
        # passed; otherwise use ``dataset_id=`` if given, else the class-level
        # ``DATASET_ID`` as a last-resort fallback (legacy subclasses only).
        if resource_id is None:
            resource_id = dataset_id if dataset_id is not None else self.DATASET_ID
        self._resource_id = resource_id

        # Resolve API mode: explicit __init__ argument wins; otherwise fall
        # back to the class-level default.
        effective_mode: ApiMode = api_mode if api_mode is not None else self.API_MODE
        if effective_mode not in _TRANSPORTS:
            raise ValueError(
                f"Unknown api_mode={effective_mode!r}; expected one of {sorted(_TRANSPORTS)}."
            )
        self._api_mode: ApiMode = effective_mode
        self._transport: BaseTransport = _TRANSPORTS[effective_mode]

        # Resolve API base URL: explicit class override wins; otherwise pick
        # the default that matches the mode.
        if self.APIcore is not None:
            self._apicore = self.APIcore
        else:
            self._apicore = (
                DEFAULT_APIcore if effective_mode == "v3" else DEFAULT_DCA_APIcore
            )

        self._external_client = http_client is not None
        self._http_client = http_client

    # ---- public accessors (handy for tests) --------------------------------

    @property
    def api_mode(self) -> ApiMode:
        return self._api_mode

    @property
    def resource_id(self) -> str | None:
        return self._resource_id

    # ---- public hooks (subclasses MUST implement) ---------------------------

    def _build_brightdata_inputs(self, public_inputs: Any) -> list[dict[str, Any]]:
        """Translate validated public inputs to the JS scraper's runtime inputs.

        The list returned here is sent as-is in the BrightData trigger body.
        Each element in the list represents one "seed" the scraper will
        process. For cosmetics-design we send a single seed (the landing page
        URL) — other scrapers may send N seeds.
        """
        raise NotImplementedError

    def _build_envelope(
        self,
        rows: list[dict[str, Any]],
        public_inputs: dict[str, Any],
    ) -> dict[str, Any]:
        """Convert raw BrightData rows into the normalized envelope dict."""
        raise NotImplementedError

    # ---- BrightData REST plumbing ------------------------------------------

    async def _ensure_credentials(self) -> None:
        """Fail fast and loud when env vars are missing.

        We deliberately raise *here* (not at import time) so unit tests that
        do not need credentials can still import the module.
        """
        if not self._api_key:
            raise ScraperError(
                "INVALID_INPUTS",
                "BRIGHTDATA_API_KEY env var is not set.",
            )
        if not self._resource_id:
            hint = self.CREDENTIAL_HINT or (
                f"Set the BrightData resource id for source={self.SOURCE_NAME!r} "
                "(DATASET_ID env var for v3 or COLLECTOR_ID env var for DCA)."
            )
            raise ScraperError(
                "INVALID_INPUTS",
                (
                    f"No BrightData resource id configured for source={self.SOURCE_NAME!r} "
                    f"(api_mode={self._api_mode!r}).\n{hint}"
                ),
            )

    async def _client(self) -> httpx.AsyncClient:
        if self._http_client is not None:
            return self._http_client
        # Lazy: avoid building a client if the caller never makes a request.
        self._http_client = httpx.AsyncClient(timeout=self.HTTP_TIMEOUT)
        return self._http_client

    async def aclose(self) -> None:
        if self._http_client is not None and not self._external_client:
            await self._http_client.aclose()
            self._http_client = None

    async def _trigger_brightdata(
        self, brightdata_inputs: list[dict[str, Any]]
    ) -> str:
        """Delegate to the transport; map transport errors to ScraperError."""
        await self._ensure_credentials()
        try:
            kwargs: dict[str, Any] = dict(
                api_key=self._api_key,  # type: ignore[arg-type]
                resource_id=self._resource_id,  # type: ignore[arg-type]
                inputs=brightdata_inputs,
                http=await self._client(),
                apicore=self._apicore,
            )
            if self._api_mode == "dca" and self.DCA_TRIGGER_PARAMS is not None:
                kwargs["trigger_params"] = self.DCA_TRIGGER_PARAMS
            return await self._transport.trigger(**kwargs)
        except TransportError as e:
            raise ScraperError(e.code, e.message, details=e.details) from e

    async def _get_progress(self, job_id: str) -> dict[str, Any]:
        """Poll for progress. Returns the **normalized** poll dict:

        ``{"status": "running"|"ready"|"failed", ...}``

        Subclasses consume this directly — the v3-specific string switch that
        used to live in ``CosmeticsDesignClient.get_result`` is now obsolete.
        """
        await self._ensure_credentials()
        try:
            return await self._transport.poll(
                api_key=self._api_key,  # type: ignore[arg-type]
                job_id=job_id,
                http=await self._client(),
                apicore=self._apicore,
            )
        except TransportError as e:
            raise ScraperError(e.code, e.message, details=e.details) from e

    async def _fetch_snapshot(self, job_id: str) -> list[dict[str, Any]]:
        """Delegate to the transport; map transport errors to ScraperError."""
        await self._ensure_credentials()
        try:
            return await self._transport.download(
                api_key=self._api_key,  # type: ignore[arg-type]
                job_id=job_id,
                http=await self._client(),
                apicore=self._apicore,
            )
        except TransportError as e:
            raise ScraperError(e.code, e.message, details=e.details) from e
