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


def seed_rules(symbol: str) -> None:
    server.BINANCE_SYMBOL_RULES_CACHE[("binance_testnet_place_order", symbol)] = {
        "symbol": symbol,
        "mode": "binance_testnet_place_order",
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
    server.init_db()
    seed_rules("BTCUSDT")
    original = {
        "ENABLE_BINANCE_TESTNET": server.ENABLE_BINANCE_TESTNET,
        "BINANCE_API_KEY": server.BINANCE_API_KEY,
        "BINANCE_API_SECRET": server.BINANCE_API_SECRET,
        "sync_exchange_account_snapshot": server.sync_exchange_account_snapshot,
        "signed_binance_request_for_mode": server.signed_binance_request_for_mode,
    }
    calls: list[dict[str, Any]] = []

    try:
        one_way_params, one_way_evidence = server.binance_flatten_position_params(
            {"symbol": "BTCUSDT", "positionAmt": "0.12345678", "positionSide": "BOTH"},
            "binance_testnet_place_order",
        )
        if one_way_params.get("side") != "SELL":
            return fail("long position flatten side should be SELL")
        if one_way_params.get("quantity") != "0.123":
            return fail(f"quantity should be floored to stepSize, got {one_way_params.get('quantity')}")
        if one_way_params.get("reduceOnly") != "true":
            return fail("one-way flatten order must be reduceOnly")

        hedge_params, hedge_evidence = server.binance_flatten_position_params(
            {"symbol": "BTCUSDT", "positionAmt": "-0.2509", "positionSide": "SHORT"},
            "binance_testnet_place_order",
        )
        if hedge_params.get("side") != "BUY":
            return fail("short position flatten side should be BUY")
        if hedge_params.get("positionSide") != "SHORT":
            return fail("hedge flatten order must preserve positionSide")
        if "reduceOnly" in hedge_params:
            return fail("hedge-mode flatten order should not send reduceOnly")

        server.ENABLE_BINANCE_TESTNET = True
        server.BINANCE_API_KEY = "test-key"
        server.BINANCE_API_SECRET = "test-secret"

        def fake_sync(mode: str) -> dict[str, Any]:
            return {
                "id": "EXSNAP-EMERGENCY",
                "ts": server.utc_now(),
                "mode": mode,
                "summary": {"open_position_count": 2},
                "positions": [
                    {"symbol": "BTCUSDT", "positionAmt": "0.12345678", "positionSide": "BOTH"},
                    {"symbol": "BTCUSDT", "positionAmt": "-0.2509", "positionSide": "SHORT"},
                ],
            }

        def fake_signed(method: str, path: str, params: dict[str, Any], mode: str) -> dict[str, Any]:
            calls.append({"method": method, "path": path, "params": params, "mode": mode})
            return {"ok": True, "path": path}

        server.sync_exchange_account_snapshot = fake_sync
        server.signed_binance_request_for_mode = fake_signed

        plan = server.binance_flatten_positions("binance_testnet_place_order", dry_run=True)
        if plan.get("planned_count") != 2 or plan.get("submitted_count") != 0:
            return fail(f"dry-run flatten plan should plan two orders and submit none: {plan}")
        if calls:
            return fail("dry-run flatten unexpectedly called signed request")

        try:
            server.binance_flatten_positions("binance_testnet_place_order", dry_run=False, confirmation="")
            return fail("flatten execution accepted missing confirmation")
        except ValueError as exc:
            if "FLATTEN_POSITIONS" not in str(exc):
                return fail(f"unexpected missing-confirmation error: {exc}")

        executed = server.binance_flatten_positions(
            "binance_testnet_place_order",
            dry_run=False,
            confirmation="FLATTEN_POSITIONS",
        )
        if executed.get("submitted_count") != 2:
            return fail(f"flatten execution should submit two reduce orders: {executed}")
        if not all(call["path"] == "/fapi/v1/order" and call["method"] == "POST" for call in calls):
            return fail(f"flatten execution used unexpected signed calls: {calls}")

        calls.clear()
        cancel_result = server.cancel_all_open_exchange_orders(
            modes=["binance_testnet_place_order"],
            explicit_symbols=["BTCUSDT"],
        )
        if not cancel_result or cancel_result[0].get("status") != "sent":
            return fail(f"global cancel did not send expected request: {cancel_result}")
        if calls[0]["path"] != "/fapi/v1/allOpenOrders" or calls[0]["method"] != "DELETE":
            return fail(f"global cancel used unexpected signed call: {calls[0]}")

        print(
            json.dumps(
                {
                    "ok": True,
                    "one_way": {"params": one_way_params, "evidence": one_way_evidence},
                    "hedge": {"params": hedge_params, "evidence": hedge_evidence},
                    "dry_run_planned": plan.get("planned_count"),
                    "submitted": executed.get("submitted_count"),
                    "cancel_symbols": [item.get("symbol") for item in cancel_result],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    finally:
        server.ENABLE_BINANCE_TESTNET = original["ENABLE_BINANCE_TESTNET"]
        server.BINANCE_API_KEY = original["BINANCE_API_KEY"]
        server.BINANCE_API_SECRET = original["BINANCE_API_SECRET"]
        server.sync_exchange_account_snapshot = original["sync_exchange_account_snapshot"]
        server.signed_binance_request_for_mode = original["signed_binance_request_for_mode"]


if __name__ == "__main__":
    raise SystemExit(main())
