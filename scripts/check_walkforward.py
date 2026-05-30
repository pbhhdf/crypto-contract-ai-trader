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
BARS = int(os.getenv("TRADER_BACKTEST_BARS", "240"))
HTTP_TIMEOUT_SECONDS = float(os.getenv("TRADER_HTTP_TIMEOUT_SECONDS", "90"))
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
            "/api/backtests/walkforward",
            {"symbol": SYMBOL, "interval": INTERVAL, "bars": BARS},
        )
        wf = created.get("walkforward") or {}
        folds = wf.get("folds") or []
        if not wf.get("id", "").startswith("WF-"):
            return fail("walk-forward id missing")
        if wf.get("fold_count") != len(folds) or not folds:
            return fail("fold_count does not match returned folds")
        if int(wf.get("tested_params_per_fold") or 0) < 100:
            return fail("walk-forward did not test the multi-signal strategy grid")
        for key in [
            "total_return_pct",
            "max_fold_drawdown_pct",
            "positive_fold_rate_pct",
            "test_trade_count",
            "tested_params_per_fold",
        ]:
            if key not in wf:
                return fail(f"walk-forward missing {key}")
        first = folds[0]
        for key in ["selected_params", "train_metrics", "test_metrics"]:
            if key not in first:
                return fail(f"fold missing {key}")
        if not (first.get("selected_params") or {}).get("signal_type"):
            return fail("fold selected_params missing signal_type")
        summary = {
            "walkforward_id": wf.get("id"),
            "symbol": wf.get("symbol"),
            "interval": wf.get("interval"),
            "bars": wf.get("bars"),
            "fold_count": wf.get("fold_count"),
            "tested_params_per_fold": wf.get("tested_params_per_fold"),
            "total_return_pct": wf.get("total_return_pct"),
            "positive_fold_rate_pct": wf.get("positive_fold_rate_pct"),
            "max_fold_drawdown_pct": wf.get("max_fold_drawdown_pct"),
            "test_trade_count": wf.get("test_trade_count"),
            "first_fold_params": first.get("selected_params"),
            "first_fold_test_return_pct": first.get("test_metrics", {}).get("total_return_pct"),
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    except HTTPError as exc:
        return fail(f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}")
    except (URLError, TimeoutError, OSError) as exc:
        return fail(f"could not reach {BASE_URL}: {exc}")


if __name__ == "__main__":
    raise SystemExit(main())
