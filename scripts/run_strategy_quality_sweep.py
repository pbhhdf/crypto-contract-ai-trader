from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT_DIR = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT_DIR / "reports"


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
AUTH_USER = os.getenv("TRADER_AUTH_USER", os.getenv("APP_BASIC_AUTH_USER", ""))
AUTH_PASSWORD = os.getenv("TRADER_AUTH_PASSWORD", os.getenv("APP_BASIC_AUTH_PASSWORD", ""))
HTTP_TIMEOUT_SECONDS = float(os.getenv("TRADER_HTTP_TIMEOUT_SECONDS", "180"))
DEFAULT_THRESHOLDS = {
    "min_folds": 2,
    "min_total_return_pct": 0.0,
    "min_positive_fold_rate_pct": 50.0,
    "max_fold_drawdown_pct": 10.0,
}


def utc_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def auth_headers() -> dict[str, str]:
    headers = {"Accept": "application/json"}
    if AUTH_USER and AUTH_PASSWORD:
        token = base64.b64encode(f"{AUTH_USER}:{AUTH_PASSWORD}".encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {token}"
    return headers


def request_json(method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
    body = None
    headers = auth_headers()
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(f"{BASE_URL}{path}", data=body, headers=headers, method=method)
    with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def parse_csv(value: str) -> list[str]:
    return [item.strip().upper() if item.strip().endswith("USDT") else item.strip() for item in value.split(",") if item.strip()]


def fetch_thresholds() -> dict[str, float]:
    try:
        gate = (request_json("GET", "/api/go-live-gate").get("go_live_gate") or {})
        thresholds = gate.get("walkforward_thresholds") or {}
        return {
            "min_folds": int(thresholds.get("min_folds", DEFAULT_THRESHOLDS["min_folds"])),
            "min_total_return_pct": float(
                thresholds.get("min_total_return_pct", DEFAULT_THRESHOLDS["min_total_return_pct"])
            ),
            "min_positive_fold_rate_pct": float(
                thresholds.get(
                    "min_positive_fold_rate_pct",
                    DEFAULT_THRESHOLDS["min_positive_fold_rate_pct"],
                )
            ),
            "max_fold_drawdown_pct": float(
                thresholds.get("max_fold_drawdown_pct", DEFAULT_THRESHOLDS["max_fold_drawdown_pct"])
            ),
        }
    except Exception:  # noqa: BLE001 - fall back to conservative defaults when the server is not available.
        return dict(DEFAULT_THRESHOLDS)


def passes_thresholds(wf: dict[str, Any], thresholds: dict[str, float]) -> tuple[bool, list[str]]:
    failures: list[str] = []
    fold_count = int(float(wf.get("fold_count") or 0))
    total_return = float(wf.get("total_return_pct") or 0)
    positive_rate = float(wf.get("positive_fold_rate_pct") or 0)
    drawdown = float(wf.get("max_fold_drawdown_pct") or 0)
    if fold_count < int(thresholds["min_folds"]):
        failures.append(f"fold_count {fold_count} < {int(thresholds['min_folds'])}")
    if total_return < thresholds["min_total_return_pct"]:
        failures.append(f"total_return_pct {total_return:.2f} < {thresholds['min_total_return_pct']:.2f}")
    if positive_rate < thresholds["min_positive_fold_rate_pct"]:
        failures.append(
            f"positive_fold_rate_pct {positive_rate:.2f} < {thresholds['min_positive_fold_rate_pct']:.2f}"
        )
    if drawdown > thresholds["max_fold_drawdown_pct"]:
        failures.append(f"max_fold_drawdown_pct {drawdown:.2f} > {thresholds['max_fold_drawdown_pct']:.2f}")
    return not failures, failures


def score_result(result: dict[str, Any]) -> tuple[int, float, float, float, int]:
    wf = result.get("walkforward") or {}
    passed = 1 if result.get("passed") else 0
    total_return = float(wf.get("total_return_pct") or -999999.0)
    positive_rate = float(wf.get("positive_fold_rate_pct") or 0.0)
    drawdown = float(wf.get("max_fold_drawdown_pct") or 999999.0)
    trades = int(float(wf.get("test_trade_count") or 0))
    return (passed, total_return, positive_rate, -drawdown, trades)


def run_candidate(symbol: str, interval: str, bars: int, thresholds: dict[str, float]) -> dict[str, Any]:
    started = time.time()
    payload = request_json(
        "POST",
        "/api/backtests/walkforward",
        {"symbol": symbol, "interval": interval, "bars": bars},
    )
    wf = payload.get("walkforward") or {}
    passed, failures = passes_thresholds(wf, thresholds)
    return {
        "symbol": symbol,
        "interval": interval,
        "bars": bars,
        "ok": bool(wf.get("id")),
        "passed": passed,
        "failures": failures,
        "duration_seconds": round(time.time() - started, 2),
        "walkforward": {
            "id": wf.get("id"),
            "fold_count": wf.get("fold_count"),
            "tested_params_per_fold": wf.get("tested_params_per_fold"),
            "total_return_pct": wf.get("total_return_pct"),
            "positive_fold_rate_pct": wf.get("positive_fold_rate_pct"),
            "max_fold_drawdown_pct": wf.get("max_fold_drawdown_pct"),
            "test_trade_count": wf.get("test_trade_count"),
            "test_win_rate_pct": wf.get("test_win_rate_pct"),
        },
    }


def write_report(report: dict[str, Any], prefix: str) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"{prefix}-{utc_slug()}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run multi-symbol, multi-interval walk-forward validation and report whether any "
            "candidate satisfies the current go-live strategy-quality thresholds."
        )
    )
    parser.add_argument("--symbols", default=os.getenv("TRADER_SWEEP_SYMBOLS", "BTCUSDT,ETHUSDT,SOLUSDT"))
    parser.add_argument("--intervals", default=os.getenv("TRADER_SWEEP_INTERVALS", "5m,15m,1h"))
    parser.add_argument("--bars", type=int, default=int(os.getenv("TRADER_SWEEP_BARS", "240")))
    parser.add_argument("--max-candidates", type=int, default=int(os.getenv("TRADER_SWEEP_MAX_CANDIDATES", "0")))
    parser.add_argument("--promote-best", action="store_true", help="Re-run the best passing candidate last for UI/go-live gate use.")
    parser.add_argument("--dry-run", action="store_true", help="Only render the planned candidate grid and write a report.")
    parser.add_argument("--report-prefix", default="strategy-quality-sweep")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    symbols = parse_csv(args.symbols)
    intervals = parse_csv(args.intervals)
    candidates = [(symbol, interval, args.bars) for symbol in symbols for interval in intervals]
    if args.max_candidates > 0:
        candidates = candidates[: args.max_candidates]
    if not candidates:
        print("FAILED: no strategy-quality sweep candidates", file=sys.stderr)
        return 1

    thresholds = fetch_thresholds()
    report: dict[str, Any] = {
        "ok": True,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "base_url": BASE_URL,
        "dry_run": args.dry_run,
        "thresholds": thresholds,
        "candidate_count": len(candidates),
        "candidates": [
            {"symbol": symbol, "interval": interval, "bars": bars}
            for symbol, interval, bars in candidates
        ],
        "results": [],
        "best": None,
        "promoted": None,
    }

    if not args.dry_run:
        for symbol, interval, bars in candidates:
            try:
                report["results"].append(run_candidate(symbol, interval, bars, thresholds))
            except HTTPError as exc:
                report["results"].append(
                    {
                        "symbol": symbol,
                        "interval": interval,
                        "bars": bars,
                        "ok": False,
                        "passed": False,
                        "failures": [f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}"],
                    }
                )
            except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
                report["results"].append(
                    {
                        "symbol": symbol,
                        "interval": interval,
                        "bars": bars,
                        "ok": False,
                        "passed": False,
                        "failures": [f"{exc.__class__.__name__}: {exc}"],
                    }
                )
        passed_results = [item for item in report["results"] if item.get("passed")]
        ranked = sorted(report["results"], key=score_result, reverse=True)
        report["best"] = ranked[0] if ranked else None
        report["passed_count"] = len(passed_results)
        report["ok"] = all(item.get("ok") for item in report["results"])
        if args.promote_best and passed_results:
            best = sorted(passed_results, key=score_result, reverse=True)[0]
            report["promoted"] = run_candidate(
                str(best["symbol"]),
                str(best["interval"]),
                int(best["bars"]),
                thresholds,
            )

    path = write_report(report, args.report_prefix)
    summary = {
        "ok": report["ok"],
        "dry_run": report["dry_run"],
        "candidate_count": report["candidate_count"],
        "passed_count": report.get("passed_count"),
        "best": report.get("best"),
        "promoted": report.get("promoted"),
        "report_path": str(path),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
