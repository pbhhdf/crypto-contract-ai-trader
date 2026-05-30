from __future__ import annotations

import base64
import json
import os
import sys
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BASE_URL = os.getenv("TRADER_BASE_URL", "http://127.0.0.1:8787").rstrip("/")
SYMBOL = os.getenv("TRADER_SYMBOL", "BTCUSDT")
HTTP_TIMEOUT_SECONDS = float(os.getenv("TRADER_HTTP_TIMEOUT_SECONDS", "45"))
AUTH_USER = os.getenv("TRADER_AUTH_USER", "")
AUTH_PASSWORD = os.getenv("TRADER_AUTH_PASSWORD", "")


def request_json(method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
    body = None
    headers = {"Accept": "application/json"}
    if AUTH_USER and AUTH_PASSWORD:
        token = base64.b64encode(f"{AUTH_USER}:{AUTH_PASSWORD}".encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {token}"
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(f"{BASE_URL}{path}", data=body, headers=headers, method=method)
    with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def fail(message: str) -> int:
    print(f"FAILED: {message}", file=sys.stderr)
    return 1


def find_run(run_id: str) -> dict[str, Any] | None:
    runs = request_json("GET", "/api/runs?limit=20").get("runs") or []
    return next((run for run in runs if run.get("id") == run_id), None)


def wait_for_idle(timeout_seconds: int = 30) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        scheduler = request_json("GET", "/api/scheduler").get("scheduler") or {}
        if not scheduler.get("active_runs"):
            return True
        time.sleep(1)
    return False


def wait_for_run(run_id: str, timeout_seconds: int = 120) -> dict[str, Any] | None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        run = find_run(run_id)
        if run and run.get("status") in {"completed", "failed"}:
            return run
        time.sleep(1)
    return find_run(run_id)


def disable_scheduler() -> dict[str, Any] | None:
    try:
        return request_json(
            "POST",
            "/api/scheduler",
            {"enabled": False, "symbol": SYMBOL, "mode": "paper", "interval_seconds": 3600},
        )
    except Exception:  # noqa: BLE001 - this is a best-effort cleanup path.
        return None


def main() -> int:
    try:
        if not wait_for_idle():
            return fail("another run is still active")

        configured = request_json(
            "POST",
            "/api/scheduler",
            {"enabled": True, "symbol": SYMBOL, "mode": "paper", "interval_seconds": 3600},
        ).get("scheduler") or {}
        if not configured.get("enabled"):
            return fail("scheduler did not enable")
        if configured.get("symbol") != SYMBOL:
            return fail(f"scheduler symbol is {configured.get('symbol')!r}")

        triggered = request_json("POST", "/api/scheduler/run-now")
        run = triggered.get("run") or {}
        run_id = run.get("id")
        if not run_id:
            return fail("run-now did not create a run")

        finished = wait_for_run(run_id)
        disabled = disable_scheduler()
        scheduler = (disabled or request_json("GET", "/api/scheduler")).get("scheduler") or {}

        if not finished:
            return fail(f"run {run_id} was not found after trigger")
        if finished.get("status") != "completed":
            return fail(f"run {run_id} ended with status {finished.get('status')!r}")
        if scheduler.get("last_run_id") != run_id:
            return fail("scheduler last_run_id does not match triggered run")
        if scheduler.get("enabled"):
            return fail("scheduler cleanup did not disable the schedule")

        summary = {
            "run_id": run_id,
            "run_status": finished.get("status"),
            "symbol": finished.get("symbol"),
            "mode": finished.get("mode"),
            "scheduler_enabled_after_check": scheduler.get("enabled"),
            "last_run_at": scheduler.get("last_run_at"),
            "last_error": scheduler.get("last_error"),
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    except HTTPError as exc:
        disable_scheduler()
        return fail(f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}")
    except (URLError, TimeoutError, OSError) as exc:
        disable_scheduler()
        return fail(f"could not reach {BASE_URL}: {exc}")


if __name__ == "__main__":
    raise SystemExit(main())
