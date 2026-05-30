from __future__ import annotations

import json
import sys
import uuid
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


def make_order(
    order_id: str,
    symbol: str,
    status: str,
    venue_status: str = "NEW",
    reconcile_status: str = "needs_reconcile",
) -> dict[str, Any]:
    now = server.utc_now()
    return {
        "id": order_id,
        "run_id": "RUN-STATEFUL-CONFLICT-CHECK",
        "symbol": symbol,
        "side": "BUY",
        "order_type": "LIMIT",
        "quantity": 0.01,
        "leverage": 2,
        "entry_price": 50000.0,
        "stop_loss": 49000.0,
        "take_profit": 52000.0,
        "status": status,
        "client_order_id": order_id,
        "venue_order_id": "",
        "venue_status": venue_status,
        "reconcile_status": reconcile_status,
        "reconcile_note": "",
        "last_reconciled_at": None,
        "created_at": now,
        "updated_at": now,
        "parent_order_id": None,
        "protection_kind": None,
    }


def cleanup(order_ids: list[str]) -> None:
    placeholders = ", ".join("?" for _ in order_ids)
    if not placeholders:
        return
    with server.DB_LOCK, server.connect() as conn:
        conn.execute(f"DELETE FROM order_transitions WHERE order_id IN ({placeholders})", order_ids)
        conn.execute(f"DELETE FROM orders WHERE id IN ({placeholders})", order_ids)
        conn.commit()


def intent(symbol: str) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "side": "BUY",
        "confidence": 0.8,
        "entry_price": 50000.0,
        "stop_loss": 49000.0,
        "take_profit": 52000.0,
        "leverage": 2.0,
        "position_pct": 0.01,
        "time_horizon": "30-90 minutes",
        "provider": "rules",
        "model": "deterministic_rules_v1",
        "ai_enabled": False,
        "fallback_reason": None,
        "rationale": "stateful order conflict check",
    }


def fresh_market(symbol: str) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "data_source": "binance_public",
        "fallback": False,
        "source_error": None,
        "timestamp": server.utc_now(),
        "mark_price": 50000.0,
        "liquidation_pressure": "low",
    }


def fresh_account(mode: str) -> dict[str, Any]:
    return {
        "source": mode,
        "snapshot_id": f"EXSNAP-{mode}",
        "synced_at": server.utc_now(),
        "equity_usdt": 2500.0,
        "free_margin_usdt": 2400.0,
        "open_position_count": 0,
    }


def main() -> int:
    server.init_db()
    suffix = uuid.uuid4().hex[:8].upper()
    symbol = f"TST{suffix[:4]}USDT"
    other_symbol = f"ALT{suffix[:4]}USDT"
    testnet_id = f"TESTLIVE-CONFLICT-{suffix}"
    live_id = f"LIVE-CONFLICT-{suffix}"
    order_ids = [testnet_id, live_id]
    original_account_state_for_mode = server.account_state_for_mode
    original_config = server.risk_config()

    try:
        cleanup(order_ids)
        server.persist_order(make_order(testnet_id, symbol, "pending_reconcile", "UNKNOWN", "needs_reconcile"))

        conflicts = server.stateful_order_conflicts("binance_testnet_place_order", symbol)
        if not any(item.get("id") == testnet_id for item in conflicts):
            return fail("pending testnet order did not block same-symbol stateful execution", conflicts)
        account_conflicts = server.stateful_order_conflicts("binance_testnet_place_order", other_symbol)
        cross_symbol_conflict = next((item for item in account_conflicts if item.get("id") == testnet_id), None)
        if not cross_symbol_conflict:
            return fail("pending testnet order did not block same-account stateful execution", account_conflicts)
        if cross_symbol_conflict.get("scope") != "same_mode_account":
            return fail("cross-symbol conflict did not record account-level scope", cross_symbol_conflict)

        try:
            server.assert_no_stateful_order_conflicts("binance_testnet_place_order", other_symbol)
            return fail("assert_no_stateful_order_conflicts accepted a pending testnet order")
        except ValueError as exc:
            if "Stateful order conflict blocks" not in str(exc):
                return fail("unexpected conflict assertion error", {"error": str(exc)})

        server.account_state_for_mode = lambda mode: fresh_account(str(mode or "").lower().strip())
        server.configure_risk({**original_config, "allowed_symbols": [symbol, other_symbol], "max_open_positions": 0})
        risk = server.risk_check(intent(other_symbol), fresh_market(other_symbol), "binance_testnet_place_order")
        conflict_check = next((item for item in risk.get("checks", []) if item.get("name") == "Stateful order conflict"), None)
        if not conflict_check:
            return fail("risk checks do not include Stateful order conflict", risk)
        if conflict_check.get("status") != "fail" or risk.get("status") != "rejected":
            return fail("risk did not reject a same-account pending stateful order", risk)

        server.update_order_state(
            testnet_id,
            status="testnet_canceled",
            venue_status="CANCELED",
            reconcile_status="reconciled",
            reconcile_note="resolved by conflict check",
            reason="stateful_conflict_check_resolved",
        )
        resolved_conflicts = server.stateful_order_conflicts("binance_testnet_place_order", symbol)
        resolved_account_conflicts = server.stateful_order_conflicts("binance_testnet_place_order", other_symbol)
        if any(item.get("id") == testnet_id for item in resolved_conflicts + resolved_account_conflicts):
            return fail(
                "terminal reconciled testnet order still blocked new execution",
                {"same_symbol": resolved_conflicts, "same_account": resolved_account_conflicts},
            )

        server.persist_order(make_order(live_id, symbol, "live_submitted", "NEW", "needs_reconcile"))
        live_conflicts = server.stateful_order_conflicts("live_guarded", other_symbol)
        testnet_conflicts_after_live = server.stateful_order_conflicts("binance_testnet_place_order", symbol)
        if not any(item.get("id") == live_id for item in live_conflicts):
            return fail("live submitted order did not block live execution", live_conflicts)
        if any(item.get("id") == live_id for item in testnet_conflicts_after_live):
            return fail("live order should not block isolated testnet placement mode", testnet_conflicts_after_live)

        print(
            json.dumps(
                {
                    "ok": True,
                    "symbol": symbol,
                    "other_symbol": other_symbol,
                    "testnet_conflict_id": testnet_id,
                    "live_conflict_id": live_id,
                    "account_conflict_scope": cross_symbol_conflict.get("scope"),
                    "risk_conflict_check": conflict_check,
                    "live_conflicts": live_conflicts,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    finally:
        server.account_state_for_mode = original_account_state_for_mode
        server.configure_risk(original_config)
        cleanup(order_ids)


if __name__ == "__main__":
    raise SystemExit(main())
