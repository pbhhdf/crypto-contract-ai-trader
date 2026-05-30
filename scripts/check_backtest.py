from __future__ import annotations

import base64
import json
import os
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BASE_URL = os.getenv("TRADER_BASE_URL", "http://127.0.0.1:8787").rstrip("/")
SYMBOL = os.getenv("TRADER_SYMBOL", "BTCUSDT")
INTERVAL = os.getenv("TRADER_BACKTEST_INTERVAL", "15m")
BARS = int(os.getenv("TRADER_BACKTEST_BARS", "160"))
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


def main() -> int:
    try:
        created = request_json(
            "POST",
            "/api/backtests",
            {"symbol": SYMBOL, "interval": INTERVAL, "bars": BARS},
        )
        backtest = created.get("backtest") or {}
        metrics = backtest.get("metrics") or {}
        trades = created.get("trades") or []
        if backtest.get("status") != "completed":
            return fail(f"backtest status is {backtest.get('status')!r}")
        for key in ["total_return_pct", "max_drawdown_pct", "trade_count", "win_rate_pct"]:
            if key not in metrics:
                return fail(f"missing metric {key}")
        if metrics.get("bars", 0) < 80:
            return fail("backtest used too few bars")
        if metrics.get("trade_count", 0) != len(trades):
            return fail("trade_count does not match returned trades")
        summary = {
            "backtest_id": backtest.get("id"),
            "symbol": metrics.get("symbol"),
            "interval": metrics.get("interval"),
            "bars": metrics.get("bars"),
            "strategy": metrics.get("strategy"),
            "trade_count": metrics.get("trade_count"),
            "win_rate_pct": metrics.get("win_rate_pct"),
            "total_return_pct": metrics.get("total_return_pct"),
            "max_drawdown_pct": metrics.get("max_drawdown_pct"),
            "net_pnl_usdt": metrics.get("net_pnl_usdt"),
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    except HTTPError as exc:
        return fail(f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}")
    except (URLError, TimeoutError, OSError) as exc:
        return fail(f"could not reach {BASE_URL}: {exc}")


if __name__ == "__main__":
    raise SystemExit(main())
