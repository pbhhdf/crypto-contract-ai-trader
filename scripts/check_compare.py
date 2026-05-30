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
HTTP_TIMEOUT_SECONDS = float(os.getenv("TRADER_HTTP_TIMEOUT_SECONDS", "60"))
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
            "/api/backtests/compare",
            {"symbol": SYMBOL, "interval": INTERVAL, "bars": BARS},
        )
        comparison = created.get("comparison") or {}
        results = comparison.get("results") or []
        if not comparison.get("id", "").startswith("CMP-"):
            return fail("comparison id missing")
        if comparison.get("tested_count", 0) < 100:
            return fail("too few parameter sets were tested")
        if len(results) < 3:
            return fail("too few leaderboard rows returned")
        top = results[0]
        for key in ["rank_score", "metrics", "params"]:
            if key not in top:
                return fail(f"top result missing {key}")
        metrics = top["metrics"]
        params = top["params"]
        for key in ["total_return_pct", "max_drawdown_pct", "trade_count", "win_rate_pct"]:
            if key not in metrics:
                return fail(f"top metrics missing {key}")
        for key in ["signal_type", "fast_ma", "slow_ma", "lookback", "stop_pct", "take_pct", "threshold_pct"]:
            if key not in params:
                return fail(f"top params missing {key}")
        summary = {
            "comparison_id": comparison["id"],
            "symbol": comparison.get("symbol"),
            "interval": comparison.get("interval"),
            "bars": comparison.get("bars"),
            "tested_count": comparison.get("tested_count"),
            "top_rank_score": top.get("rank_score"),
            "top_return_pct": metrics.get("total_return_pct"),
            "top_drawdown_pct": metrics.get("max_drawdown_pct"),
            "top_win_rate_pct": metrics.get("win_rate_pct"),
            "top_params": params,
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    except HTTPError as exc:
        return fail(f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}")
    except (URLError, TimeoutError, OSError) as exc:
        return fail(f"could not reach {BASE_URL}: {exc}")


if __name__ == "__main__":
    raise SystemExit(main())
