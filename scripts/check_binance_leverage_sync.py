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
    original_flag = server.BINANCE_SYNC_LEVERAGE_BEFORE_ORDER

    def fake_signed_request(method: str, path: str, params: dict[str, Any], mode: str) -> dict[str, Any]:
        calls.append({"method": method, "path": path, "params": dict(params), "mode": mode})
        return {
            "symbol": params.get("symbol"),
            "leverage": params.get("leverage"),
            "maxNotionalValue": "1000000",
        }

    order = {
        "id": "TEST-LVG",
        "symbol": "BTCUSDT",
        "side": "BUY",
        "leverage": 2.7,
    }

    try:
        server.signed_binance_request_for_mode = fake_signed_request
        server.BINANCE_SYNC_LEVERAGE_BEFORE_ORDER = True

        evidence = server.ensure_binance_leverage(order, "binance_testnet_place_order")
        if evidence.get("status") != "synced":
            return fail(f"expected synced leverage evidence, got {evidence}")
        if evidence.get("synced_leverage") != 2:
            return fail(f"expected leverage to be floored to 2, got {evidence.get('synced_leverage')}")
        if len(calls) != 1:
            return fail(f"expected one leverage sync call, got {len(calls)}")
        call = calls[0]
        if call["method"] != "POST" or call["path"] != "/fapi/v1/leverage":
            return fail(f"unexpected leverage sync endpoint: {call}")
        if call["mode"] != "binance_testnet_place_order":
            return fail(f"unexpected leverage sync mode: {call}")
        if call["params"].get("symbol") != "BTCUSDT" or call["params"].get("leverage") != 2:
            return fail(f"unexpected leverage sync params: {call}")

        calls.clear()
        skipped = server.ensure_binance_leverage(order, "binance_testnet_validate")
        if skipped.get("status") != "skipped" or calls:
            return fail(f"validation mode should skip leverage sync without a request: {skipped}, calls={calls}")

        server.BINANCE_SYNC_LEVERAGE_BEFORE_ORDER = False
        disabled = server.ensure_binance_leverage(order, "live_guarded")
        if disabled.get("status") != "skipped" or calls:
            return fail(f"disabled sync should not call Binance: {disabled}, calls={calls}")

    finally:
        server.signed_binance_request_for_mode = original_request
        server.BINANCE_SYNC_LEVERAGE_BEFORE_ORDER = original_flag

    print(
        json.dumps(
            {
                "ok": True,
                "synced": evidence,
                "validation_skip": skipped,
                "disabled_skip": disabled,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
