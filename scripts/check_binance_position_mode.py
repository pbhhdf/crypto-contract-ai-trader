from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from app import server  # noqa: E402


def fail(message: str) -> int:
    print(f"FAILED: {message}", file=sys.stderr)
    return 1


def main() -> int:
    calls: list[dict[str, Any]] = []
    original_request = server.signed_binance_request_for_mode
    original_live_enabled = server.ENABLE_BINANCE_LIVE
    original_live_key = server.BINANCE_LIVE_API_KEY
    original_live_secret = server.BINANCE_LIVE_API_SECRET
    original_testnet_enabled = server.ENABLE_BINANCE_TESTNET
    original_testnet_key = server.BINANCE_API_KEY
    original_testnet_secret = server.BINANCE_API_SECRET

    def fake_one_way(method: str, path: str, params: dict[str, Any], mode: str) -> dict[str, Any]:
        calls.append({"method": method, "path": path, "params": dict(params), "mode": mode})
        return {"dualSidePosition": False}

    def fake_hedge(method: str, path: str, params: dict[str, Any], mode: str) -> dict[str, Any]:
        calls.append({"method": method, "path": path, "params": dict(params), "mode": mode})
        return {"dualSidePosition": "true"}

    try:
        server.ENABLE_BINANCE_LIVE = True
        server.BINANCE_LIVE_API_KEY = "live-key"
        server.BINANCE_LIVE_API_SECRET = "live-secret"
        server.ENABLE_BINANCE_TESTNET = True
        server.BINANCE_API_KEY = "testnet-key"
        server.BINANCE_API_SECRET = "testnet-secret"
        server.signed_binance_request_for_mode = fake_one_way
        one_way = server.fetch_binance_position_mode("live_guarded")
        if one_way.get("position_mode") != "ONE_WAY" or one_way.get("dual_side_position") is not False:
            return fail(f"expected ONE_WAY position mode, got {one_way}")
        if calls[-1]["path"] != "/fapi/v1/positionSide/dual" or calls[-1]["method"] != "GET":
            return fail(f"unexpected position mode endpoint call: {calls[-1]}")

        server.signed_binance_request_for_mode = fake_hedge
        hedge = server.fetch_binance_position_mode("binance_testnet_place_order")
        if hedge.get("position_mode") != "HEDGE" or hedge.get("dual_side_position") is not True:
            return fail(f"expected HEDGE position mode, got {hedge}")
    finally:
        server.signed_binance_request_for_mode = original_request
        server.ENABLE_BINANCE_LIVE = original_live_enabled
        server.BINANCE_LIVE_API_KEY = original_live_key
        server.BINANCE_LIVE_API_SECRET = original_live_secret
        server.ENABLE_BINANCE_TESTNET = original_testnet_enabled
        server.BINANCE_API_KEY = original_testnet_key
        server.BINANCE_API_SECRET = original_testnet_secret

    print(
        json.dumps(
            {
                "ok": True,
                "one_way": one_way,
                "hedge": hedge,
                "calls": calls,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
