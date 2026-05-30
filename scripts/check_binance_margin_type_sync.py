from __future__ import annotations

import json
import sys
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.error import HTTPError


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from app import server  # noqa: E402


def fail(message: str) -> int:
    print(f"FAILED: {message}", file=sys.stderr)
    return 1


def main() -> int:
    calls: list[dict[str, Any]] = []
    original_request = server.signed_binance_request_for_mode
    original_sync_flag = server.BINANCE_SYNC_MARGIN_TYPE_BEFORE_ORDER
    original_target = server.BINANCE_TARGET_MARGIN_TYPE

    def fake_signed_request(method: str, path: str, params: dict[str, Any], mode: str) -> dict[str, Any]:
        calls.append({"method": method, "path": path, "params": dict(params), "mode": mode})
        return {"code": 200, "msg": "success", "symbol": params.get("symbol")}

    order = {
        "id": "TEST-MARGIN",
        "symbol": "BTCUSDT",
        "side": "BUY",
        "leverage": 2.0,
    }

    try:
        server.signed_binance_request_for_mode = fake_signed_request
        server.BINANCE_SYNC_MARGIN_TYPE_BEFORE_ORDER = True
        server.BINANCE_TARGET_MARGIN_TYPE = "ISOLATED"

        evidence = server.ensure_binance_margin_type(order, "binance_testnet_place_order")
        if evidence.get("status") != "synced":
            return fail(f"expected synced margin evidence, got {evidence}")
        if len(calls) != 1:
            return fail(f"expected one margin sync call, got {len(calls)}")
        call = calls[0]
        if call["method"] != "POST" or call["path"] != "/fapi/v1/marginType":
            return fail(f"unexpected margin sync endpoint: {call}")
        if call["params"].get("symbol") != "BTCUSDT" or call["params"].get("marginType") != "ISOLATED":
            return fail(f"unexpected margin sync params: {call}")

        def fake_already_set(method: str, path: str, params: dict[str, Any], mode: str) -> dict[str, Any]:
            calls.append({"method": method, "path": path, "params": dict(params), "mode": mode})
            body = BytesIO(b'{"code":-4046,"msg":"No need to change margin type."}')
            raise HTTPError("https://test.invalid", 400, "Bad Request", hdrs=None, fp=body)

        server.signed_binance_request_for_mode = fake_already_set
        calls.clear()
        already = server.ensure_binance_margin_type(order, "live_guarded")
        if already.get("status") != "already_set":
            return fail(f"already-set margin response should be accepted: {already}")
        if len(calls) != 1:
            return fail(f"expected one already-set margin sync call, got {len(calls)}")

        calls.clear()
        skipped = server.ensure_binance_margin_type(order, "binance_testnet_validate")
        if skipped.get("status") != "skipped" or calls:
            return fail(f"validation mode should skip margin sync without a request: {skipped}, calls={calls}")

        server.BINANCE_SYNC_MARGIN_TYPE_BEFORE_ORDER = False
        disabled = server.ensure_binance_margin_type(order, "live_guarded")
        if disabled.get("status") != "skipped" or calls:
            return fail(f"disabled sync should not call Binance: {disabled}, calls={calls}")

    finally:
        server.signed_binance_request_for_mode = original_request
        server.BINANCE_SYNC_MARGIN_TYPE_BEFORE_ORDER = original_sync_flag
        server.BINANCE_TARGET_MARGIN_TYPE = original_target

    print(
        json.dumps(
            {
                "ok": True,
                "synced": evidence,
                "already_set": already,
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
