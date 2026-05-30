from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from app import server  # noqa: E402


def fail(message: str, payload: Any | None = None) -> int:
    print(f"FAILED: {message}", file=sys.stderr)
    if payload is not None:
        print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
    return 1


def seed_rules(symbol: str, mode: str) -> None:
    server.BINANCE_SYMBOL_RULES_CACHE[(mode, symbol)] = {
        "symbol": symbol,
        "mode": mode,
        "fetched_at": server.utc_now(),
        "price_precision": 2,
        "quantity_precision": 4,
        "tick_size": "0.10",
        "min_price": "1",
        "max_price": "1000000",
        "step_size": "0.001",
        "min_qty": "0.001",
        "max_qty": "1000",
        "min_notional": "5",
    }


def main() -> int:
    original_signed = server.signed_binance_request_for_mode
    calls: list[dict[str, Any]] = []
    try:
        seed_rules("BTCUSDT", "live_guarded")
        intent = {
            "symbol": "BTCUSDT",
            "side": "BUY",
            "position_pct": 0.05,
            "leverage": 2,
            "entry_price": 50000.0,
            "stop_loss": 49000.0,
            "take_profit": 52000.0,
        }
        order = server.prepare_order_payload("RUN-PRE-SUBMIT-CHECK", intent, "LIVE", 10000.0, {"source": "check"})
        params = server.binance_order_params(order, "live_guarded")

        def fake_signed(method: str, path: str, params: dict[str, Any], mode: str) -> dict[str, Any]:
            calls.append({"method": method, "path": path, "params": params, "mode": mode})
            return {"ok": True, "path": path, "clientOrderId": params.get("newClientOrderId")}

        server.signed_binance_request_for_mode = fake_signed
        bundle = server.validate_binance_order_bundle(order, params, "live_guarded")

        if len(calls) != 3:
            return fail("pre-submit bundle should test entry, stop-loss, and take-profit", calls)
        if any(call["method"] != "POST" or call["path"] != "/fapi/v1/order/test" for call in calls):
            return fail("pre-submit validation must only use /fapi/v1/order/test", calls)
        if any(call["mode"] != "live_guarded" for call in calls):
            return fail("pre-submit validation did not preserve live_guarded mode", calls)
        client_ids = [call["params"].get("newClientOrderId") for call in calls]
        if client_ids[0] != order["client_order_id"]:
            return fail("entry test did not use the parent client order id", client_ids)
        if not client_ids[1].endswith("-SL") or not client_ids[2].endswith("-TP"):
            return fail("protection tests did not use SL/TP child client order ids", client_ids)
        if set(bundle.keys()) != {"mode", "entry", "protection_geometry", "protections"} or len(bundle["protections"]) != 2:
            return fail("validation bundle has unexpected structure", bundle)
        if bundle["protection_geometry"].get("status") != "pass":
            return fail("validation bundle did not include passing protection geometry", bundle)

        print(
            json.dumps(
                {
                    "ok": True,
                    "tested_paths": [call["path"] for call in calls],
                    "mode": bundle.get("mode"),
                    "client_order_ids": client_ids,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    finally:
        server.signed_binance_request_for_mode = original_signed


if __name__ == "__main__":
    raise SystemExit(main())
