"""ServiceRegistry minimal — replica el patron shared/middleware.py de David.

Mapea ``tool_use.name`` (del schema pasado al modelo) a un callable async que
resuelve la llamada. En `AGENT_MODE=live` delega al middleware real; en
`AGENT_MODE=fixture` (default) sirve el snapshot congelado para iterar sin
costes ni esperas de BrightData.

Multi-middleware
----------------
El módulo descubre al arranque los paquetes bajo ``middlewares/`` que exportan
``TOOL_SCHEMA``, ``trigger`` y ``get_result`` (excluye ``core``). El app le
pasa a ``build_registry(middleware)`` el nombre elegido en el ``POST /chat`` y
sólo las dos tools de ese middleware quedan registradas — así el LLM no tiene
la tentación de mezclar scrapers.

Live mode: ``<name>_get_result`` polea internamente hasta que el job queda
``done``/``failed`` (o se supera el wall-clock). De esta forma el LLM sólo ve
3 turnos (trigger → get_result bloqueante → texto final) en lugar de saturar
MAX_TURNS con polls que siempre devuelven ``running``.
"""

from __future__ import annotations

import asyncio
import importlib
import json
import os
import pkgutil
from pathlib import Path
from typing import Any, Awaitable, Callable

import middlewares as _middlewares_pkg

# -----------------------------------------------------------------------------
# Auto-discovery
# -----------------------------------------------------------------------------

_EXCLUDED_PACKAGES = {"core"}


def _discover_middlewares() -> list[str]:
    """Encuentra paquetes bajo ``middlewares/`` que exponen el contrato público.

    Requiere que el paquete exporte los tres símbolos: ``TOOL_SCHEMA``,
    ``trigger``, ``get_result``. Excluye ``core`` (utilidades compartidas).
    Devuelve la lista ordenada alfabéticamente.
    """
    found: list[str] = []
    for mod in pkgutil.iter_modules(_middlewares_pkg.__path__):
        if not mod.ispkg:
            continue
        name = mod.name
        if name in _EXCLUDED_PACKAGES or name.startswith("_"):
            continue
        try:
            pkg = importlib.import_module(f"middlewares.{name}")
        except Exception:  # noqa: BLE001
            # Un middleware roto no debería tirar al harness entero — lo
            # saltamos en silencio. El error real surgirá cuando alguien
            # lo seleccione.
            continue
        if all(hasattr(pkg, attr) for attr in ("TOOL_SCHEMA", "trigger", "get_result")):
            found.append(name)
    return sorted(found)


AVAILABLE_MIDDLEWARES: list[str] = _discover_middlewares()


# -----------------------------------------------------------------------------
# Tool schema
# -----------------------------------------------------------------------------


def build_tool_schema(middleware: str) -> list[dict[str, Any]]:
    """Devuelve el ``TOOL_SCHEMA`` del middleware elegido.

    Lanza ``ValueError`` si el nombre no corresponde a un middleware conocido.
    """
    if middleware not in AVAILABLE_MIDDLEWARES:
        raise ValueError(
            f"unknown middleware {middleware!r}. "
            f"Available: {AVAILABLE_MIDDLEWARES}"
        )
    pkg = importlib.import_module(f"middlewares.{middleware}")
    return list(pkg.TOOL_SCHEMA)


# -----------------------------------------------------------------------------
# Fixture mode — genérico por middleware
# -----------------------------------------------------------------------------

_MIDDLEWARES_DIR = Path(__file__).resolve().parent.parent / "middlewares"

# Contador por job para simular un ciclo "running → done" en fixture mode.
# Clave: job_id (incluye el nombre del middleware para no colisionar).
_fixture_poll_counts: dict[str, int] = {}

# Mapping job_id → (middleware, rows_path) poblado por _fixture_trigger.
# El lifetime es el del proceso del harness; en tests se resetea con
# ``reset_fixture_state()``.
_fixture_jobs: dict[str, tuple[str, Path]] = {}


def _fixture_path_for(middleware: str) -> Path | None:
    """Devuelve el primer ``<middleware>_snapshot_*.json`` o None."""
    fixtures_dir = _MIDDLEWARES_DIR / middleware / "tests" / "fixtures"
    if not fixtures_dir.is_dir():
        return None
    candidates = sorted(fixtures_dir.glob(f"{middleware}_snapshot_*.json"))
    return candidates[0] if candidates else None


def _fixture_job_id_for(middleware: str) -> str:
    return f"fixture_{middleware}_s_demo01"


def _envelope_for_rows(
    middleware: str, rows: list[dict[str, Any]]
) -> dict[str, Any]:
    """Llama al ``build_envelope_for_rows`` del client del middleware.

    Si el middleware no tuviera el helper (defensivo), envuelve las rows en el
    shape mínimo del envelope.
    """
    try:
        pkg = importlib.import_module(f"middlewares.{middleware}")
    except ImportError:
        return _minimal_envelope(middleware, rows)

    client_cls = _resolve_client_class(pkg)
    if client_cls is None:
        return _minimal_envelope(middleware, rows)
    try:
        client = client_cls()
    except Exception:  # noqa: BLE001
        return _minimal_envelope(middleware, rows)
    build = getattr(client, "build_envelope_for_rows", None)
    if build is None:
        return _minimal_envelope(middleware, rows)
    try:
        return build(rows, public_inputs={})
    except Exception:  # noqa: BLE001
        return _minimal_envelope(middleware, rows)


def _resolve_client_class(pkg: Any) -> type | None:
    """Heurística: el paquete expone exactamente una subclase con sufijo
    ``Client`` en ``__all__``. Si no, devolvemos None.
    """
    names = getattr(pkg, "__all__", None) or []
    for attr in names:
        if attr.endswith("Client"):
            candidate = getattr(pkg, attr, None)
            if isinstance(candidate, type):
                return candidate
    # Fallback: escanear el namespace.
    for attr in dir(pkg):
        if attr.endswith("Client") and attr != "BaseScraperClient":
            candidate = getattr(pkg, attr, None)
            if isinstance(candidate, type):
                return candidate
    return None


def _minimal_envelope(middleware: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Shape mínimo del envelope consistente con ``Envelope`` del core.

    Usado sólo si no logramos instanciar el client del middleware (raro — sólo
    debería pasar si un middleware rompe su contrato).
    """
    from middlewares.core.envelope import Envelope, _utc_now_iso

    now = _utc_now_iso()
    env = Envelope(
        source=middleware,
        inputs={},
        data=list(rows),
        meta={
            "rows": len(rows),
            "emitted": len(rows),
            "skipped_by_reason": {},
            "started_at": now,
            "ended_at": now,
        },
    )
    return {"status": "done", "data": env.model_dump()}


def _fixture_for(middleware: str) -> dict[str, Any]:
    """Carga el snapshot del fixture y devuelve un envelope ``done``.

    Devuelve ``{"status": "failed", "error": {"code": "FIXTURE_MISSING", ...}}``
    si no hay snapshot para ese middleware.
    """
    path = _fixture_path_for(middleware)
    if path is None:
        return {
            "status": "failed",
            "error": {
                "code": "FIXTURE_MISSING",
                "message": (
                    f"No hay snapshot para middleware={middleware!r} "
                    f"en middlewares/{middleware}/tests/fixtures/."
                ),
                "retriable": False,
            },
        }
    try:
        rows = json.loads(path.read_text())
    except Exception as e:  # noqa: BLE001
        return {
            "status": "failed",
            "error": {
                "code": "FIXTURE_MISSING",
                "message": (
                    f"Fixture ilegible para {middleware!r} "
                    f"({path.name}): {type(e).__name__}: {e}"
                ),
                "retriable": False,
            },
        }
    return _envelope_for_rows(middleware, rows)


def _make_fixture_trigger(middleware: str) -> Callable[..., Awaitable[dict[str, Any]]]:
    async def _fixture_trigger(**kwargs: Any) -> dict[str, Any]:
        path = _fixture_path_for(middleware)
        if path is None:
            return {
                "status": "failed",
                "error": {
                    "code": "FIXTURE_MISSING",
                    "message": (
                        f"No hay snapshot para middleware={middleware!r}; "
                        f"trigger en fixture mode no puede responder."
                    ),
                    "retriable": False,
                },
            }
        job_id = _fixture_job_id_for(middleware)
        _fixture_jobs[job_id] = (middleware, path)
        return {"job_id": job_id, "eta_seconds": 5}

    _fixture_trigger.__name__ = f"_fixture_trigger__{middleware}"
    return _fixture_trigger


def _make_fixture_get_result(
    middleware: str,
) -> Callable[..., Awaitable[dict[str, Any]]]:
    async def _fixture_get_result(job_id: str) -> dict[str, Any]:
        # Simular running → done: el primer poll devuelve running, el segundo
        # devuelve el envelope final. Usamos el job_id como llave del contador
        # (incluye el middleware para no colisionar entre ejecuciones
        # paralelas).
        _fixture_poll_counts[job_id] = _fixture_poll_counts.get(job_id, 0) + 1
        if _fixture_poll_counts[job_id] < 2:
            return {"status": "running", "progress_pct": 40}
        # El trigger grabó qué middleware creó este job. Si no está, cae al
        # nombre que le tocó al registry (cuando se invoca directo sin pasar
        # por trigger — p.ej., en tests legacy).
        mw = _fixture_jobs.get(job_id, (middleware, None))[0]
        return _fixture_for(mw)

    _fixture_get_result.__name__ = f"_fixture_get_result__{middleware}"
    return _fixture_get_result


# -----------------------------------------------------------------------------
# Backwards-compat: los tests existentes importan ``_fixture_get_result`` y
# ``_fixture_trigger`` como símbolos del módulo; los mantenemos apuntando al
# middleware original (cosmetics_design).
# -----------------------------------------------------------------------------

_DEFAULT_FIXTURE_MIDDLEWARE = "cosmetics_design"
_FIXTURE_JOB_ID = _fixture_job_id_for(_DEFAULT_FIXTURE_MIDDLEWARE)


async def _fixture_trigger(**kwargs: Any) -> dict[str, Any]:
    fn = _make_fixture_trigger(_DEFAULT_FIXTURE_MIDDLEWARE)
    return await fn(**kwargs)


async def _fixture_get_result(job_id: str) -> dict[str, Any]:
    fn = _make_fixture_get_result(_DEFAULT_FIXTURE_MIDDLEWARE)
    return await fn(job_id)


# -----------------------------------------------------------------------------
# Live mode
# -----------------------------------------------------------------------------

# Defaults del polling en live mode. Se pueden sobrescribir por env var para
# tests y para despliegues con SLAs distintos.
#   LIVE_POLL_INTERVAL_SECONDS   — intervalo entre polls (default 30s).
#   LIVE_POLL_TIMEOUT_SECONDS    — wall-clock máximo (default 1800s = 30 min).
_DEFAULT_LIVE_POLL_INTERVAL_S = 30.0
_DEFAULT_LIVE_POLL_TIMEOUT_S = 30 * 60.0


def _live_poll_interval_seconds() -> float:
    raw = os.getenv("LIVE_POLL_INTERVAL_SECONDS")
    if raw is None or raw == "":
        return _DEFAULT_LIVE_POLL_INTERVAL_S
    try:
        return float(raw)
    except ValueError:
        return _DEFAULT_LIVE_POLL_INTERVAL_S


def _live_poll_timeout_seconds() -> float:
    raw = os.getenv("LIVE_POLL_TIMEOUT_SECONDS")
    if raw is None or raw == "":
        return _DEFAULT_LIVE_POLL_TIMEOUT_S
    try:
        return float(raw)
    except ValueError:
        return _DEFAULT_LIVE_POLL_TIMEOUT_S


def _make_live_trigger(
    middleware: str,
) -> Callable[..., Awaitable[dict[str, Any]]]:
    pkg = importlib.import_module(f"middlewares.{middleware}")
    live_trigger = pkg.trigger

    async def _live_trigger(**kwargs: Any) -> dict[str, Any]:
        print(
            f"[REGISTRY/live] {middleware} trigger called with kwargs={kwargs}",
            flush=True,
        )
        result = await live_trigger(kwargs)
        print(f"[REGISTRY/live] {middleware} trigger returned: {result}", flush=True)
        return result

    _live_trigger.__name__ = f"_live_trigger__{middleware}"
    return _live_trigger


async def _live_get_result(
    job_id: str,
    *,
    poll_fn: Callable[[str], Awaitable[dict[str, Any]]] | None = None,
    interval_seconds: float | None = None,
    timeout_seconds: float | None = None,
    sleep: Callable[[float], Awaitable[None]] | None = None,
) -> dict[str, Any]:
    """Polea internamente hasta que el middleware devuelve done/failed.

    El LLM llama esto una sola vez y recibe un envelope terminal. Así el loop
    de tool-use converge en 3 turnos incluso cuando el run real de BrightData
    tarda 10-30 minutos.

    - ``interval_seconds``: tiempo entre polls (default env / 30s).
    - ``timeout_seconds``: wall-clock máximo (default env / 30 min).
    - ``poll_fn`` / ``sleep``: inyectables sólo para tests — no usar en prod.

    Nota: este wrapper es genérico. ``poll_fn`` debe ser el ``get_result`` del
    middleware correcto (lo provee ``_make_live_get_result``). Para los tests
    existentes de ``cosmetics_design`` el default (``poll_fn=None``) usa el
    middleware de cosmetics_design — preservamos backwards-compat.
    """
    interval = interval_seconds if interval_seconds is not None else _live_poll_interval_seconds()
    timeout = timeout_seconds if timeout_seconds is not None else _live_poll_timeout_seconds()
    if poll_fn is None:
        # Default backwards-compat: cosmetics_design.
        from middlewares.cosmetics_design import get_result as _default_get_result
        poll = _default_get_result
    else:
        poll = poll_fn
    sleeper = sleep or asyncio.sleep

    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    poll_n = 0

    print(
        f"[REGISTRY/live] get_result polling started job_id={job_id} "
        f"interval={interval}s timeout={timeout}s",
        flush=True,
    )
    while True:
        poll_n += 1
        result = await poll(job_id)
        status = result.get("status") if isinstance(result, dict) else None
        print(
            f"[REGISTRY/live] poll #{poll_n} job_id={job_id} status={status!r}",
            flush=True,
        )
        if status in ("done", "failed"):
            print(
                f"[REGISTRY/live] get_result terminal after {poll_n} polls: status={status!r}",
                flush=True,
            )
            return result

        now = loop.time()
        remaining = deadline - now
        if remaining <= 0:
            print(
                f"[REGISTRY/live] get_result TIMEOUT after {poll_n} polls",
                flush=True,
            )
            return {
                "status": "failed",
                "error": {
                    "code": "TIMEOUT",
                    "message": (
                        f"get_result polling exceeded wall-clock of "
                        f"{timeout:.0f}s for job_id={job_id}; last status="
                        f"{status!r}"
                    ),
                    "retriable": True,
                },
            }
        await sleeper(min(interval, remaining))


def _make_live_get_result(
    middleware: str,
) -> Callable[..., Awaitable[dict[str, Any]]]:
    pkg = importlib.import_module(f"middlewares.{middleware}")
    mw_get_result = pkg.get_result

    async def _live_get_result_for_mw(
        job_id: str,
        *,
        poll_fn: Callable[[str], Awaitable[dict[str, Any]]] | None = None,
        interval_seconds: float | None = None,
        timeout_seconds: float | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> dict[str, Any]:
        return await _live_get_result(
            job_id,
            poll_fn=poll_fn if poll_fn is not None else mw_get_result,
            interval_seconds=interval_seconds,
            timeout_seconds=timeout_seconds,
            sleep=sleep,
        )

    _live_get_result_for_mw.__name__ = f"_live_get_result__{middleware}"
    return _live_get_result_for_mw


# -----------------------------------------------------------------------------
# Registry
# -----------------------------------------------------------------------------


class ToolRegistry:
    """Dispatcher por nombre de tool — equivalente funcional a ServiceRegistry."""

    def __init__(self) -> None:
        self._tools: dict[str, Callable[..., Awaitable[dict[str, Any]]]] = {}

    def register(
        self, name: str, fn: Callable[..., Awaitable[dict[str, Any]]]
    ) -> None:
        self._tools[name] = fn

    async def dispatch(self, name: str, params: dict[str, Any]) -> dict[str, Any]:
        fn = self._tools.get(name)
        if fn is None:
            return {
                "error": f"unknown tool: {name}",
                "available": sorted(self._tools.keys()),
            }
        try:
            return await fn(**params)
        except TypeError as e:
            return {"error": f"bad params for {name}: {e}", "received": params}


def build_registry(middleware: str = _DEFAULT_FIXTURE_MIDDLEWARE) -> ToolRegistry:
    """Construye un ``ToolRegistry`` con las 2 tools del middleware elegido.

    ``middleware`` defaultea a ``cosmetics_design`` para backwards-compat con
    los tests existentes que invocan ``build_registry()`` sin argumentos.
    """
    if middleware not in AVAILABLE_MIDDLEWARES:
        raise ValueError(
            f"unknown middleware {middleware!r}. "
            f"Available: {AVAILABLE_MIDDLEWARES}"
        )

    mode = os.getenv("AGENT_MODE", "fixture").lower()
    trigger_name = f"{middleware}_trigger"
    get_result_name = f"{middleware}_get_result"

    r = ToolRegistry()
    if mode == "live":
        r.register(trigger_name, _make_live_trigger(middleware))
        # Special-case cosmetics_design para preservar identidad del wrapper
        # (test histórico compara ``is registry_module._live_get_result``).
        if middleware == _DEFAULT_FIXTURE_MIDDLEWARE:
            r.register(get_result_name, _live_get_result)
        else:
            r.register(get_result_name, _make_live_get_result(middleware))
    else:
        r.register(trigger_name, _make_fixture_trigger(middleware))
        # Mismo special-case para cosmetics_design, test histórico compara
        # ``is registry_module._fixture_get_result``.
        if middleware == _DEFAULT_FIXTURE_MIDDLEWARE:
            r.register(get_result_name, _fixture_get_result)
        else:
            r.register(get_result_name, _make_fixture_get_result(middleware))
    return r


def reset_fixture_state() -> None:
    """Util para tests: reinicia el simulador running/done del fixture."""
    _fixture_poll_counts.clear()
    _fixture_jobs.clear()
