from __future__ import annotations

import json
import os
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from app import server  # noqa: E402


def fail(message: str) -> int:
    print(f"FAILED: {message}", file=sys.stderr)
    return 1


def main() -> int:
    status = server.safe_binance_time_drift_status("live_guarded")
    live_requested = bool(
        server.ENABLE_BINANCE_LIVE
        or server.BINANCE_PLACE_LIVE_ORDERS
        or server.EXCHANGE_MODE == "live_guarded"
        or server.BINANCE_LIVE_API_KEY
        or server.BINANCE_LIVE_API_SECRET
    )
    require_pass = os.getenv("BINANCE_TIME_DRIFT_REQUIRE_PASS", "").strip().lower() in {"1", "true", "yes", "on"}
    if status.get("status") != "pass" and (live_requested or require_pass):
        return fail(f"Binance time drift check failed: {status}")
    if "abs_drift_ms" not in status or "roundtrip_ms" not in status:
        if live_requested or require_pass:
            return fail(f"Binance time drift result is missing drift evidence: {status}")
        print(
            json.dumps(
                {
                    "ok": True,
                    "live_requested": live_requested,
                    "require_pass": require_pass,
                    "ready_for_live_time": False,
                    "warning": "Binance time drift evidence is unavailable; ignored only because live mode is not requested.",
                    "time_drift": status,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if (live_requested or require_pass) and int(status.get("abs_drift_ms") or 0) > int(status.get("max_drift_ms") or 0):
        return fail(f"Binance time drift exceeds threshold: {status}")

    print(
        json.dumps(
            {
                "ok": True,
                "live_requested": live_requested,
                "require_pass": require_pass,
                "ready_for_live_time": status.get("status") == "pass",
                "time_drift": status,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
