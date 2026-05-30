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


def sample_open_order(symbol: str = "ETHUSDT") -> dict[str, Any]:
    return {
        "symbol": symbol,
        "orderId": 123456789,
        "clientOrderId": "MANUAL-OPEN-ORDER",
        "side": "SELL",
        "type": "LIMIT",
        "status": "NEW",
        "origQty": "0.010",
        "executedQty": "0",
        "price": "5000",
        "stopPrice": "0",
        "reduceOnly": False,
        "closePosition": False,
        "timeInForce": "GTC",
        "updateTime": 1790000000000,
    }


def main() -> int:
    original_signed = server.signed_binance_request_for_mode
    original_recovery_modes = server.binance_recovery_modes
    original_sync_account = server.sync_exchange_account_snapshot
    original_position_mode = server.fetch_binance_position_mode
    original_stream_status = server.binance_user_stream_status
    original_live_enabled = server.ENABLE_BINANCE_LIVE
    original_live_key = server.BINANCE_LIVE_API_KEY
    original_live_secret = server.BINANCE_LIVE_API_SECRET
    server.init_db()
    original_recovery_last_at = server.get_setting("exchange_recovery_last_at", "")
    original_recovery_report = server.get_setting("exchange_recovery_last_report", "{}")
    calls: list[dict[str, Any]] = []

    try:
        server.ENABLE_BINANCE_LIVE = True
        server.BINANCE_LIVE_API_KEY = "live-open-order-gate-key"
        server.BINANCE_LIVE_API_SECRET = "live-open-order-gate-secret"

        def fake_signed(method: str, path: str, params: dict[str, Any], mode: str) -> Any:
            calls.append({"method": method, "path": path, "params": params, "mode": mode})
            if method == "GET" and path == "/fapi/v1/openOrders":
                return []
            raise AssertionError(f"unexpected signed request: {method} {path} {mode}")

        server.signed_binance_request_for_mode = fake_signed
        skipped = server.exchange_open_orders_check("binance_testnet_validate")
        if skipped.get("status") != "pass" or not skipped.get("skipped"):
            return fail("validation mode should skip exchange open-order gate", skipped)

        empty = server.exchange_open_orders_check("live_guarded")
        if empty.get("status") != "pass" or empty.get("open_order_count") != 0:
            return fail("empty live openOrders should pass", empty)
        if calls[-1]["path"] != "/fapi/v1/openOrders" or calls[-1]["mode"] != "live_guarded":
            return fail("live open-order check did not call the expected endpoint", calls[-1])

        open_snapshot = {
            "mode": "live_guarded",
            "synced_at": server.utc_now(),
            "open_order_count": 1,
            "open_orders": [server.summarize_binance_open_order(sample_open_order())],
            "endpoint": "/fapi/v1/openOrders",
        }
        open_check = server.exchange_open_orders_check("live_guarded", open_snapshot)
        if open_check.get("status") != "fail":
            return fail("live open-order gate accepted an existing exchange order", open_check)
        try:
            server.assert_no_exchange_open_orders("live_guarded")
        except Exception as exc:  # noqa: BLE001 - this branch should not trigger with fake empty endpoint.
            return fail("assert_no_exchange_open_orders rejected empty endpoint response", {"error": str(exc)})

        def fake_signed_with_order(method: str, path: str, params: dict[str, Any], mode: str) -> Any:
            calls.append({"method": method, "path": path, "params": params, "mode": mode})
            if method == "GET" and path == "/fapi/v1/openOrders":
                return [sample_open_order()]
            raise AssertionError(f"unexpected signed request: {method} {path} {mode}")

        server.signed_binance_request_for_mode = fake_signed_with_order
        try:
            server.assert_no_exchange_open_orders("live_guarded")
            return fail("assert_no_exchange_open_orders accepted unmanaged live open order")
        except ValueError as exc:
            if "open-order gate blocks" not in str(exc):
                return fail("unexpected unmanaged open-order assertion error", {"error": str(exc)})

        server.binance_recovery_modes = lambda: ["live_guarded"]
        server.sync_exchange_account_snapshot = lambda mode: {
            "id": "EXSNAP-OPEN-ORDER-GATE",
            "ts": server.utc_now(),
            "mode": mode,
            "summary": {"wallet_balance_usdt": 1000, "open_position_count": 0},
            "positions": [],
        }
        server.fetch_binance_position_mode = lambda mode: {
            "mode": mode,
            "position_mode": "ONE_WAY",
            "dual_side_position": False,
            "synced_at": server.utc_now(),
        }
        server.binance_user_stream_status = lambda include_health=True: {
            "mode": "",
            "status": "stopped",
            "listen_key_present": False,
            "dependency_ready": True,
            "consumer_running": False,
            "websocket_connected": False,
            "event_count": 0,
        }
        report = server.recover_exchange_state("check_exchange_open_order_gate")
        live_report = server.exchange_open_orders_snapshot_from_report(report, "live_guarded")
        if not live_report or live_report.get("open_order_count") != 1:
            return fail("exchange recovery did not include live openOrders evidence", report)

        print(
            json.dumps(
                {
                    "ok": True,
                    "skipped": skipped,
                    "empty": empty,
                    "blocked": open_check,
                    "recovery_open_orders": live_report,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    finally:
        server.signed_binance_request_for_mode = original_signed
        server.binance_recovery_modes = original_recovery_modes
        server.sync_exchange_account_snapshot = original_sync_account
        server.fetch_binance_position_mode = original_position_mode
        server.binance_user_stream_status = original_stream_status
        server.ENABLE_BINANCE_LIVE = original_live_enabled
        server.BINANCE_LIVE_API_KEY = original_live_key
        server.BINANCE_LIVE_API_SECRET = original_live_secret
        server.set_setting("exchange_recovery_last_at", original_recovery_last_at)
        server.set_setting("exchange_recovery_last_report", original_recovery_report)


if __name__ == "__main__":
    raise SystemExit(main())
