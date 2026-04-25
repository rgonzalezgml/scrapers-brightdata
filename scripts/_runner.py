"""Shared async runner for the per-middleware scripts in this folder.

Each ``scripts/run_<name>.py`` wires up the middleware's public ``trigger`` /
``get_result`` entry points and hands them to :func:`run` together with a
dict of inputs. This module owns the poll loop, timing, stdout reporting and
JSON dump so the per-middleware files stay tiny.

Also ensures the workspace root is on ``sys.path`` so that
``python scripts/run_<name>.py`` works without requiring ``-m scripts.run_<name>``
or an editable install.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import types
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    load_dotenv = None  # type: ignore[assignment]

if load_dotenv is not None:
    load_dotenv(_ROOT / ".env")


TriggerFn = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]
GetResultFn = Callable[[str], Awaitable[dict[str, Any]]]


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def _output_path(name: str) -> Path:
    return Path(__file__).parent / f"last_run_{name}.json"


def _disable_saturation_guards(client_module: types.ModuleType | None) -> list[str]:
    """Replace every ``_maybe_*`` guard in the middleware's client module
    with a pass-through so the raw envelope surfaces even when the middleware
    would normally flip it to ``failed`` (PAYWALL_SATURATION, BLOCK_SATURATION,
    PRICE_MISSING_SATURATION, REGION_BLOCKED, STRUCTURE_* ...).

    Debug-only: this defeats the middleware's correctness guards. Used by the
    ``scripts/run_*.py`` runners to inspect raw rows during development.

    Returns the list of patched guard names (for logging).
    """
    if client_module is None:
        return []
    patched: list[str] = []
    for attr in dir(client_module):
        if not attr.startswith("_maybe_"):
            continue
        fn = getattr(client_module, attr, None)
        if callable(fn):
            setattr(client_module, attr, lambda env: env)
            patched.append(attr)
    return patched


def _install_raw_snapshot_dump(
    name: str, client_module: types.ModuleType | None
) -> str | None:
    """Wrap the middleware's client ``build_envelope_for_rows`` so the raw
    BrightData snapshot rows are written verbatim to ``last_run_<name>.raw.json``
    *before* pydantic coercion / filtering / envelope construction.

    The file has the shape:
        {
            "count": <n>,
            "keys_seen": {<key>: <rows_with_non_null_count>, ...},
            "rows": [ <raw dict>, ... ]
        }

    ``keys_seen`` is a quick histogram so you can spot at a glance which
    fields the scraper populated and which are systematically null — that's
    what distinguishes "RFQ gating" (price field present but ``null`` for
    most rows) from "selector drift" (price key just missing).
    """
    if client_module is None:
        return None

    try:
        from gli_scrapers.core.client import BaseScraperClient
    except Exception:  # noqa: BLE001
        return None

    client_cls: type | None = None
    for attr in dir(client_module):
        val = getattr(client_module, attr, None)
        if (
            isinstance(val, type)
            and issubclass(val, BaseScraperClient)
            and val is not BaseScraperClient
        ):
            client_cls = val
            break
    if client_cls is None or not hasattr(client_cls, "build_envelope_for_rows"):
        return None

    raw_path = _output_path(name).with_suffix(".raw.json")
    original = client_cls.build_envelope_for_rows

    def wrapped(self: Any, rows: Any, public_inputs: Any) -> Any:
        try:
            _dump_raw(raw_path, rows)
        except Exception as e:  # noqa: BLE001 — never break the run on dump failure
            print(f"[raw-dump] WARN: could not write {raw_path}: {e}")
        return original(self, rows, public_inputs)

    client_cls.build_envelope_for_rows = wrapped  # type: ignore[assignment]
    return str(raw_path)


def _dump_raw(path: Path, rows: Any) -> None:
    if not isinstance(rows, list):
        payload: dict[str, Any] = {"count": 0, "keys_seen": {}, "rows": rows}
    else:
        keys_seen: dict[str, int] = {}
        for r in rows:
            if not isinstance(r, dict):
                continue
            for k, v in r.items():
                if v not in (None, "", [], {}):
                    keys_seen[k] = keys_seen.get(k, 0) + 1
        payload = {
            "count": len(rows),
            "keys_seen": dict(sorted(keys_seen.items(), key=lambda kv: -kv[1])),
            "rows": rows,
        }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))


async def run(
    *,
    name: str,
    trigger: TriggerFn,
    get_result: GetResultFn,
    inputs: dict[str, Any],
    poll_interval_s: int = 30,
    max_wait_min: int = 90,
    env_hints: list[str] | None = None,
    client_module: types.ModuleType | None = None,
) -> int:
    """Trigger a middleware, poll until terminal, dump envelope/error to JSON.

    Returns an exit code: ``0`` on done, ``1`` on trigger/poll error, ``2`` on
    ``failed``, ``3`` on timeout.
    """
    output_file = _output_path(name)
    print(f"[{_ts()}] ====== run_{name} (debug) ======")
    print(f"[{_ts()}] API_KEY: {'set' if os.getenv('BRIGHTDATA_API_KEY') else 'missing'}")
    for hint in env_hints or []:
        val = os.getenv(hint)
        print(f"[{_ts()}] {hint}: {val or '(empty)'}")
    print(f"[{_ts()}] inputs: {json.dumps(inputs, ensure_ascii=False)}")

    patched = _disable_saturation_guards(client_module)
    if patched:
        print(f"[{_ts()}] debug: saturation guards disabled ({', '.join(patched)})")
    raw_path = _install_raw_snapshot_dump(name, client_module)
    if raw_path:
        print(f"[{_ts()}] debug: raw snapshot will be dumped to {raw_path}")
    print()

    try:
        job = await trigger(inputs)
    except Exception as e:  # noqa: BLE001
        print(f"[{_ts()}] trigger() raised: {type(e).__name__}: {e}")
        output_file.write_text(
            json.dumps({"stage": "trigger", "error": str(e)}, indent=2, ensure_ascii=False)
        )
        return 1

    if "error" in job and "job_id" not in job:
        print(f"[{_ts()}] trigger() returned error: {job['error']}")
        output_file.write_text(
            json.dumps({"stage": "trigger", "response": job}, indent=2, ensure_ascii=False)
        )
        return 2

    job_id = job["job_id"]
    eta = job.get("eta_seconds")
    print(f"[{_ts()}] trigger() OK — job_id={job_id} eta~{eta}s")
    print()

    deadline = asyncio.get_event_loop().time() + max_wait_min * 60
    poll_count = 0
    last_status: str | None = None

    while True:
        poll_count += 1
        try:
            res = await get_result(job_id)
        except Exception as e:  # noqa: BLE001
            print(f"[{_ts()}] poll #{poll_count} raised: {type(e).__name__}: {e}")
            output_file.write_text(
                json.dumps(
                    {"stage": "poll", "job_id": job_id, "error": str(e)},
                    indent=2,
                    ensure_ascii=False,
                )
            )
            return 1

        status = res.get("status")
        if status != last_status:
            print(f"[{_ts()}] poll #{poll_count} → status={status}")
            last_status = status

        if status == "done":
            env = res["data"]
            rows = env.get("data", [])
            meta = env.get("meta", {})
            print()
            print(f"[{_ts()}] ====== DONE ======")
            print(f"[{_ts()}] source:     {env.get('source')}")
            print(f"[{_ts()}] scraped_at: {env.get('scraped_at')}")
            print(f"[{_ts()}] rows:       {len(rows)}")
            print(f"[{_ts()}] meta.rows:    {meta.get('rows')}")
            print(f"[{_ts()}] meta.emitted: {meta.get('emitted')}")
            print(f"[{_ts()}] meta.errors:  {meta.get('errors')}")
            if rows:
                print(f"[{_ts()}] first row keys: {sorted(rows[0].keys())[:8]}...")
            output_file.write_text(
                json.dumps(
                    {"stage": "done", "job_id": job_id, "envelope": env},
                    indent=2,
                    ensure_ascii=False,
                )
            )
            print(f"[{_ts()}] full envelope written to {output_file}")
            return 0

        if status == "failed":
            err = res.get("error", {})
            print(f"[{_ts()}] ====== FAILED ======")
            print(f"[{_ts()}] error: {err}")
            output_file.write_text(
                json.dumps(
                    {"stage": "failed", "job_id": job_id, "error": err},
                    indent=2,
                    ensure_ascii=False,
                )
            )
            return 2

        if asyncio.get_event_loop().time() > deadline:
            print(f"[{_ts()}] ====== TIMEOUT after {max_wait_min}min ======")
            output_file.write_text(
                json.dumps(
                    {"stage": "timeout", "job_id": job_id, "waited_min": max_wait_min},
                    indent=2,
                    ensure_ascii=False,
                )
            )
            return 3

        await asyncio.sleep(poll_interval_s)
