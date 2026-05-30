from __future__ import annotations

import base64
import json
import os
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT_DIR = Path(__file__).resolve().parents[1]


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env_file(ROOT_DIR / ".env")

BASE_URL = os.getenv("TRADER_BASE_URL", "http://127.0.0.1:8787").rstrip("/")
SYMBOL = os.getenv("TRADER_SYMBOL", "BTCUSDT")
HTTP_TIMEOUT_SECONDS = float(os.getenv("TRADER_HTTP_TIMEOUT_SECONDS", "45"))
RUN_TIMEOUT_SECONDS = float(os.getenv("TRADER_RUN_TIMEOUT_SECONDS", "90"))
AUTH_USER = os.getenv("TRADER_AUTH_USER", os.getenv("APP_BASIC_AUTH_USER", ""))
AUTH_PASSWORD = os.getenv("TRADER_AUTH_PASSWORD", os.getenv("APP_BASIC_AUTH_PASSWORD", ""))


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


def wait_for_run(run_id: str) -> dict[str, Any]:
    deadline = time.time() + RUN_TIMEOUT_SECONDS
    state: dict[str, Any] = {}
    while time.time() < deadline:
        state = request_json("GET", "/api/state")
        latest_run = state.get("latest_run") or {}
        if latest_run.get("id") == run_id and latest_run.get("status") in {"completed", "failed"}:
            return state
        time.sleep(1)
    return state


def main() -> int:
    try:
        state = request_json("GET", "/api/state")
        config = state.get("config") or {}
        enabled_modes = config.get("enabled_modes") or []
        exchange = config.get("exchange") or {}
        if "binance_testnet_place_order" not in enabled_modes:
            return fail(
                "Binance testnet placement mode is not enabled. Set ENABLE_BINANCE_TESTNET=true, "
                "BINANCE_PLACE_TESTNET_ORDERS=true, EXCHANGE_MODE=binance_testnet_place_order, and testnet keys."
            )
        if not exchange.get("testnet_places_real_orders"):
            return fail("BINANCE_PLACE_TESTNET_ORDERS must be true for this check.")

        original_risk = (request_json("GET", "/api/risk").get("risk") or {}).copy()
        request_json(
            "POST",
            "/api/risk",
            {
                **original_risk,
                "emergency_stop": False,
                "max_open_positions": 0,
                "allowed_symbols": SYMBOL,
            },
        )
        try:
            created = request_json("POST", "/api/runs", {"symbol": SYMBOL, "mode": "binance_testnet_place_order"})
            run_id = created.get("run_id") or (created.get("run") or {}).get("id")
            if not run_id:
                return fail(f"run creation did not return a run_id: {created!r}")

            state = wait_for_run(run_id)
            latest_run = state.get("latest_run") or {}
            if latest_run.get("status") != "completed":
                return fail(f"run {run_id} ended with status {latest_run.get('status')!r}")

            orders = [order for order in (state.get("orders") or []) if order.get("run_id") == run_id]
            if not orders:
                return fail("testnet placement run completed without an order; final action was HOLD or risk rejected it")
            order = orders[0]
            if order.get("status") not in {"testnet_submitted", "testnet_filled", "testnet_canceled"}:
                return fail(f"expected testnet order lifecycle status, got {order.get('status')!r}")
            if order.get("status") == "testnet_submitted":
                canceled = request_json("POST", f"/api/orders/{order['id']}/cancel")
                order = canceled.get("order") or {}
                if order.get("status") not in {"testnet_canceled", "testnet_filled", "testnet_submitted"}:
                    return fail(f"cancel returned unexpected status {order.get('status')!r}")

            print(
                json.dumps(
                    {
                        "run_id": run_id,
                        "symbol": order.get("symbol"),
                        "client_order_id": order.get("client_order_id"),
                        "venue_order_id": order.get("venue_order_id"),
                        "status": order.get("status"),
                        "venue_status": order.get("venue_status"),
                        "reconcile_status": order.get("reconcile_status"),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0
        finally:
            if original_risk:
                request_json("POST", "/api/risk", original_risk)
    except HTTPError as exc:
        return fail(f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}")
    except (URLError, TimeoutError, OSError) as exc:
        return fail(f"could not reach {BASE_URL}: {exc}")


if __name__ == "__main__":
    raise SystemExit(main())
