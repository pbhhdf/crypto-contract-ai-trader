from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from app import server  # noqa: E402


def fail(message: str) -> int:
    print(f"FAILED: {message}", file=sys.stderr)
    return 1


def main() -> int:
    server.init_db()
    intent = {
        "symbol": "BTCUSDT",
        "side": "BUY",
        "confidence": 0.8,
        "entry_price": 50000.0,
        "stop_loss": 49000.0,
        "take_profit": 52000.0,
        "leverage": 2.0,
        "position_pct": 0.05,
        "time_horizon": "30-90 minutes",
        "provider": "rules",
        "model": "deterministic_rules_v1",
        "ai_enabled": False,
        "fallback_reason": None,
        "rationale": "sizing smoke test",
    }
    account_state = {
        "source": "binance_testnet_validate",
        "snapshot_id": "EXSNAP-SMOKE",
        "equity_usdt": 2500.0,
        "free_margin_usdt": 2400.0,
    }
    order = server.prepare_order_payload("sizing", intent, "TEST", 2500.0, account_state)
    expected_quantity = 0.005
    if abs(order["quantity"] - expected_quantity) > 0.0000001:
        return fail(f"quantity should use account equity 2500.0, got {order['quantity']}")
    sizing = order.get("sizing") or {}
    if sizing.get("account_source") != "binance_testnet_validate":
        return fail("order sizing did not record the exchange account source")
    if sizing.get("account_snapshot_id") != "EXSNAP-SMOKE":
        return fail("order sizing did not record the exchange account snapshot id")
    if sizing.get("notional_usdt") != 250.0:
        return fail(f"expected 250 USDT notional, got {sizing.get('notional_usdt')}")

    snapshot = {
        "symbol": "BTCUSDT",
        "liquidation_pressure": "low",
    }
    risk = server.risk_check(intent, snapshot, "paper")
    account_check = next((item for item in risk.get("checks", []) if item.get("name") == "Account source"), None)
    if not account_check:
        return fail("risk checks do not include Account source")
    freshness_check = next((item for item in risk.get("checks", []) if item.get("name") == "Account snapshot freshness"), None)
    if not freshness_check:
        return fail("risk checks do not include Account snapshot freshness")
    notional_check = next((item for item in risk.get("checks", []) if item.get("name") == "Max order notional"), None)
    if not notional_check:
        return fail("risk checks do not include Max order notional")
    if risk.get("account", {}).get("source") != "paper":
        return fail("paper risk check should use the paper account source")
    fresh_account = {
        "source": "binance_testnet_place_order",
        "snapshot_id": "EXSNAP-FRESH",
        "synced_at": server.utc_now(),
        "equity_usdt": 2500.0,
        "free_margin_usdt": 2400.0,
    }
    fresh = server.execution_account_freshness("binance_testnet_place_order", fresh_account)
    if fresh.get("status") != "pass":
        return fail(f"fresh account snapshot did not pass: {fresh}")
    stale_account = {**fresh_account, "synced_at": "2000-01-01T00:00:00+00:00"}
    stale = server.execution_account_freshness("binance_testnet_place_order", stale_account)
    if stale.get("status") != "fail":
        return fail(f"stale account snapshot did not fail: {stale}")
    try:
        server.assert_fresh_execution_account_state("binance_testnet_place_order", stale_account)
        return fail("stale account snapshot was accepted by assert_fresh_execution_account_state")
    except ValueError:
        pass

    original = server.risk_config()
    try:
        server.configure_risk({**original, "max_order_notional_usdt": 100})
        capped_risk = server.risk_check(intent, snapshot, "paper")
        capped_check = next(
            (item for item in capped_risk.get("checks", []) if item.get("name") == "Max order notional"),
            {},
        )
        if capped_check.get("status") != "fail":
            return fail("max_order_notional_usdt did not reject an oversized intent")
    finally:
        server.configure_risk(original)

    print(
        json.dumps(
            {
                "ok": True,
                "quantity": order["quantity"],
                "sizing": sizing,
                "risk_account_source": risk.get("account", {}).get("source"),
                "account_check": account_check,
                "freshness_check": freshness_check,
                "notional_check": notional_check,
                "stale_snapshot_status": stale.get("status"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
