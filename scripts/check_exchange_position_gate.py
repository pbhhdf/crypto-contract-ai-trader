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


def sample_position(symbol: str = "BTCUSDT", amount: str = "0.020") -> dict[str, Any]:
    return {
        "symbol": symbol,
        "positionAmt": amount,
        "positionSide": "BOTH",
        "entryPrice": "68000",
        "breakEvenPrice": "68010",
        "markPrice": "68100",
        "unRealizedProfit": "2.0",
        "leverage": "2",
        "isolated": True,
        "notional": "1362.0",
        "updateTime": 1790000000000,
    }


def snapshot(mode: str, positions: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "id": f"EXSNAP-{mode.upper()}",
        "ts": server.utc_now(),
        "mode": mode,
        "summary": {
            "wallet_balance_usdt": 1000,
            "available_balance_usdt": 900,
            "unrealized_pnl_usdt": sum(server.safe_float(item.get("unRealizedProfit"), 0.0) for item in positions),
            "open_position_count": len(positions),
        },
        "positions": positions,
    }


def main() -> int:
    original_sync_account = server.sync_exchange_account_snapshot
    original_exchange_recovery_status = server.exchange_recovery_status
    original_time_drift = server.safe_binance_time_drift_status
    original_live_enabled = server.ENABLE_BINANCE_LIVE
    original_live_key = server.BINANCE_LIVE_API_KEY
    original_live_secret = server.BINANCE_LIVE_API_SECRET
    server.init_db()
    original_recovery_last_at = server.get_setting("exchange_recovery_last_at", "")
    original_recovery_report = server.get_setting("exchange_recovery_last_report", "{}")

    try:
        skipped = server.exchange_positions_check("binance_testnet_validate")
        if skipped.get("status") != "pass" or not skipped.get("skipped"):
            return fail("validation mode should skip exchange position gate", skipped)

        empty_snapshot = snapshot("live_guarded", [])
        empty = server.exchange_positions_check("live_guarded", empty_snapshot)
        if empty.get("status") != "pass" or empty.get("open_position_count") != 0:
            return fail("empty live positions should pass", empty)

        occupied_snapshot = snapshot("live_guarded", [sample_position()])
        occupied = server.exchange_positions_check("live_guarded", occupied_snapshot)
        if occupied.get("status") != "fail" or occupied.get("open_position_count") != 1:
            return fail("live position gate accepted an existing exchange position", occupied)

        server.sync_exchange_account_snapshot = lambda mode: empty_snapshot
        try:
            accepted = server.assert_no_exchange_positions("live_guarded")
        except Exception as exc:  # noqa: BLE001 - this should pass for an empty snapshot.
            return fail("assert_no_exchange_positions rejected empty snapshot", {"error": str(exc)})
        if accepted.get("status") != "pass":
            return fail("assert_no_exchange_positions did not return a passing check", accepted)

        server.sync_exchange_account_snapshot = lambda mode: occupied_snapshot
        try:
            server.assert_no_exchange_positions("live_guarded")
            return fail("assert_no_exchange_positions accepted an unmanaged live position")
        except ValueError as exc:
            if "position gate blocks" not in str(exc):
                return fail("unexpected unmanaged position assertion error", {"error": str(exc)})

        server.ENABLE_BINANCE_LIVE = True
        server.BINANCE_LIVE_API_KEY = "live-position-gate-key"
        server.BINANCE_LIVE_API_SECRET = "live-position-gate-secret"
        server.safe_binance_time_drift_status = lambda mode="live_guarded": {
            "status": "pass",
            "mode": mode,
            "abs_drift_ms": 1,
            "roundtrip_ms": 1,
            "checked_at": server.utc_now(),
        }
        report = {
            "completed_at": server.utc_now(),
            "account_snapshots": [occupied_snapshot],
            "open_orders": [
                {
                    "mode": "live_guarded",
                    "status": "pass",
                    "synced_at": server.utc_now(),
                    "open_order_count": 0,
                    "open_orders": [],
                    "endpoint": "/fapi/v1/openOrders",
                }
            ],
            "position_modes": [
                {
                    "mode": "live_guarded",
                    "position_mode": "ONE_WAY",
                    "dual_side_position": False,
                    "synced_at": server.utc_now(),
                }
            ],
            "warnings": [],
            "errors": [],
        }
        server.exchange_recovery_status = lambda: {
            "last_at": report["completed_at"],
            "last_report": report,
            "snapshots": [occupied_snapshot],
            "user_stream": {
                "mode": "",
                "status": "stopped",
                "listen_key_present": False,
                "dependency_ready": True,
                "consumer_running": False,
                "websocket_connected": False,
                "event_count": 0,
            },
            "stream_summary": {},
            "stream_events": [],
        }
        gate = server.go_live_gate_status()
        position_gate = next((item for item in gate.get("gates", []) if item.get("id") == "exchange_open_positions"), None)
        gate_position_count = (
            ((position_gate or {}).get("evidence") or {}).get("positions") or {}
        ).get("open_position_count")
        if (
            not position_gate
            or position_gate.get("status") != "fail"
            or not position_gate.get("blocks_live_order")
            or gate_position_count != 1
        ):
            return fail("go-live gate did not block unmanaged live exchange positions", position_gate or gate)

        print(
            json.dumps(
                {
                    "ok": True,
                    "skipped": skipped,
                    "empty": empty,
                    "blocked": occupied,
                    "go_live_position_gate": position_gate,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    finally:
        server.sync_exchange_account_snapshot = original_sync_account
        server.exchange_recovery_status = original_exchange_recovery_status
        server.safe_binance_time_drift_status = original_time_drift
        server.ENABLE_BINANCE_LIVE = original_live_enabled
        server.BINANCE_LIVE_API_KEY = original_live_key
        server.BINANCE_LIVE_API_SECRET = original_live_secret
        server.set_setting("exchange_recovery_last_at", original_recovery_last_at)
        server.set_setting("exchange_recovery_last_report", original_recovery_report)


if __name__ == "__main__":
    raise SystemExit(main())
