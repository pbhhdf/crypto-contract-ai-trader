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
RUN_TIMEOUT_SECONDS = float(os.getenv("TRADER_RUN_TIMEOUT_SECONDS", "60"))
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


def wait_for_idle(timeout_seconds: int = 30) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        scheduler = request_json("GET", "/api/scheduler").get("scheduler") or {}
        scheduler_active_runs = scheduler.get("active_runs") or []
        if not scheduler_active_runs:
            return True
        time.sleep(1)
    return False


def wait_for_run(run_id: str) -> dict[str, Any]:
    deadline = time.time() + RUN_TIMEOUT_SECONDS
    state: dict[str, Any] = {}
    while time.time() < deadline:
        state = request_json("GET", "/api/state")
        latest_run = state.get("latest_run") or {}
        if latest_run.get("id") == run_id and latest_run.get("status") in {"completed", "failed"}:
            return state
        time.sleep(1)
    raise TimeoutError(f"run {run_id} did not finish in time")


def latest_payload(events: list[dict[str, Any]], actor: str) -> dict[str, Any] | None:
    for event in reversed(events):
        if event.get("actor") == actor:
            payload = event.get("payload")
            return payload if isinstance(payload, dict) else None
    return None


def restore(original_risk: dict[str, Any] | None) -> None:
    try:
        request_json("POST", "/api/reset-emergency-stop")
    except Exception:  # noqa: BLE001 - cleanup should not hide the original failure.
        pass
    if original_risk:
        try:
            request_json("POST", "/api/risk", original_risk)
        except Exception:  # noqa: BLE001 - cleanup should not hide the original failure.
            pass


def main() -> int:
    original_risk: dict[str, Any] | None = None
    try:
        if not wait_for_idle():
            return fail("another run is still active")

        original_risk = request_json("GET", "/api/risk").get("risk") or {}
        configured = request_json(
            "POST",
            "/api/risk",
            {
                "max_leverage": 3,
                "max_position_pct": 0.05,
                "max_order_notional_usdt": 1000,
                "max_daily_loss_pct": 0.03,
                "max_open_positions": 8,
                "max_consecutive_losses": 3,
                "allowed_symbols": [SYMBOL, "ETHUSDT", "SOLUSDT"],
            },
        ).get("risk") or {}
        if configured.get("allowed_symbols", [None])[0] != SYMBOL:
            return fail("risk allowed symbols did not save correctly")
        if configured.get("max_position_pct") != 0.05:
            return fail("risk max_position_pct did not save correctly")
        if configured.get("max_order_notional_usdt") != 1000:
            return fail("risk max_order_notional_usdt did not save correctly")

        before_orders = len((request_json("GET", "/api/state").get("orders") or []))
        request_json("POST", "/api/emergency-stop")
        created = request_json("POST", "/api/runs", {"symbol": SYMBOL, "mode": "paper"})
        run_id = (created.get("run") or {}).get("id")
        if not run_id:
            return fail("emergency-stop run did not return an id")

        state = wait_for_run(run_id)
        latest_run = state.get("latest_run") or {}
        if latest_run.get("status") != "completed":
            return fail(f"run ended with status {latest_run.get('status')!r}")
        if latest_run.get("risk_status") != "rejected":
            return fail(f"emergency stop did not force risk rejection: {latest_run.get('risk_status')!r}")

        risk_payload = latest_payload(state.get("events") or [], "Risk Engine") or {}
        emergency_check = next(
            (check for check in risk_payload.get("checks", []) if check.get("name") == "Emergency stop"),
            {},
        )
        if emergency_check.get("status") != "fail":
            return fail("risk event did not record Emergency stop failure")

        after_orders = len(state.get("orders") or [])
        if after_orders != before_orders:
            return fail("emergency stop created a new order")

        restore(original_risk)
        final_state = request_json("GET", "/api/state")
        if (final_state.get("system") or {}).get("emergency_stop"):
            return fail("emergency stop cleanup failed")

        summary = {
            "run_id": run_id,
            "risk_status": latest_run.get("risk_status"),
            "emergency_check": emergency_check.get("status"),
            "orders_before": before_orders,
            "orders_after": after_orders,
            "restored_max_leverage": (final_state.get("risk") or {}).get("max_leverage"),
            "emergency_stop_after_check": (final_state.get("system") or {}).get("emergency_stop"),
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    except HTTPError as exc:
        restore(original_risk)
        return fail(f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}")
    except (URLError, TimeoutError, OSError) as exc:
        restore(original_risk)
        return fail(f"could not validate risk controls: {exc}")


if __name__ == "__main__":
    raise SystemExit(main())
