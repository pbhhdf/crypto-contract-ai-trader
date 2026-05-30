from __future__ import annotations

import json
import os
import base64
import sys
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BASE_URL = os.getenv("TRADER_BASE_URL", "http://127.0.0.1:8787").rstrip("/")
SYMBOL = os.getenv("TRADER_SYMBOL", "BTCUSDT")
MODE = os.getenv("TRADER_MODE", "paper")
HTTP_TIMEOUT_SECONDS = float(os.getenv("TRADER_HTTP_TIMEOUT_SECONDS", "30"))
RUN_TIMEOUT_SECONDS = float(os.getenv("TRADER_RUN_TIMEOUT_SECONDS", "45"))
AUTH_USER = os.getenv("TRADER_AUTH_USER", "")
AUTH_PASSWORD = os.getenv("TRADER_AUTH_PASSWORD", "")
CLOSE_POSITION = os.getenv("TRADER_CLOSE_POSITION", "false").lower() == "true"


def request_json(method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
    body = None
    headers = {"Accept": "application/json"}
    if AUTH_USER and AUTH_PASSWORD:
        token = base64.b64encode(f"{AUTH_USER}:{AUTH_PASSWORD}".encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {token}"
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = Request(
        f"{BASE_URL}{path}",
        data=body,
        headers=headers,
        method=method,
    )
    with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def latest_payload(events: list[dict[str, Any]], actor: str) -> dict[str, Any] | None:
    for event in reversed(events):
        if event.get("actor") == actor:
            payload = event.get("payload")
            return payload if isinstance(payload, dict) else None
    return None


def fail(message: str) -> int:
    print(f"FAILED: {message}", file=sys.stderr)
    return 1


def main() -> int:
    try:
        health = request_json("GET", "/api/health")
        if health.get("ok") is not True and health.get("status") != "ok":
            return fail(f"health check returned {health!r}")

        created = request_json("POST", "/api/runs", {"symbol": SYMBOL, "mode": MODE})
        run_id = created.get("run_id") or (created.get("run") or {}).get("id")
        if not run_id:
            return fail(f"run creation did not return a run_id: {created!r}")

        deadline = time.time() + RUN_TIMEOUT_SECONDS
        state: dict[str, Any] = {}
        while time.time() < deadline:
            state = request_json("GET", "/api/state")
            latest_run = state.get("latest_run") or {}
            if latest_run.get("id") == run_id and latest_run.get("status") in {"completed", "failed"}:
                break
            time.sleep(1)
        else:
            return fail(f"run {run_id} did not complete within {RUN_TIMEOUT_SECONDS:.0f}s")

        latest_run = state.get("latest_run") or {}
        if latest_run.get("status") != "completed":
            return fail(f"run {run_id} ended with status {latest_run.get('status')!r}")

        events = state.get("events") or []
        market = latest_payload(events, "Market Data")
        risk = latest_payload(events, "Risk Engine")
        trader = latest_payload(events, "Trader Agent")
        if not market:
            return fail("missing Market Data event payload")
        if not risk:
            return fail("missing Risk Engine event payload")
        if not trader:
            return fail("missing Trader Agent event payload")

        source = market.get("data_source")
        if source not in {"binance_public", "synthetic"}:
            return fail(f"unexpected market data source {source!r}")

        account = state.get("account") or {}
        positions = state.get("positions") or []
        if "equity_usdt" not in account:
            return fail("missing paper account equity")
        run_position = next(
            (position for position in positions if position.get("run_id") == run_id),
            None,
        )
        if latest_run.get("final_action") != "HOLD" and latest_run.get("risk_status") != "rejected":
            if not run_position:
                return fail(f"missing open paper position for run {run_id}")

        close_result = None
        if CLOSE_POSITION and run_position:
            close_result = request_json(
                "POST",
                f"/api/positions/{run_position['id']}/close",
                {"reason": "smoke_test_close"},
            )
            state = request_json("GET", "/api/state")
            account = state.get("account") or account

        summary = {
            "run_id": run_id,
            "symbol": market.get("symbol"),
            "market_data_source": source,
            "fallback": market.get("fallback"),
            "mark_price": market.get("mark_price"),
            "funding_rate_pct": market.get("funding_rate_pct"),
            "open_interest_change_pct": market.get("open_interest_change_pct"),
            "long_short_ratio": market.get("long_short_ratio"),
            "final_action": latest_run.get("final_action"),
            "risk_status": latest_run.get("risk_status"),
            "event_count": len(events),
            "order_count": len(state.get("orders") or []),
            "open_position_count": account.get("open_position_count"),
            "equity_usdt": account.get("equity_usdt"),
            "unrealized_pnl_usdt": account.get("unrealized_pnl_usdt"),
            "closed_position_id": (close_result or {}).get("position", {}).get("id"),
            "realized_pnl_usdt": account.get("realized_pnl_usdt"),
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    except HTTPError as exc:
        return fail(f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}")
    except (URLError, TimeoutError, OSError) as exc:
        return fail(f"could not reach {BASE_URL}: {exc}")


if __name__ == "__main__":
    raise SystemExit(main())
