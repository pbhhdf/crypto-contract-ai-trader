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


def fresh_account(mode: str) -> dict[str, Any]:
    return {
        "source": mode,
        "snapshot_id": f"EXSNAP-{mode}",
        "synced_at": server.utc_now(),
        "equity_usdt": 2500.0,
        "free_margin_usdt": 2400.0,
        "open_position_count": 0,
    }


def fresh_public_market() -> dict[str, Any]:
    return {
        "symbol": "BTCUSDT",
        "data_source": "binance_public",
        "fallback": False,
        "source_error": None,
        "timestamp": server.utc_now(),
        "mark_price": 50000.0,
        "liquidation_pressure": "low",
    }


def main() -> int:
    synthetic = server.build_synthetic_market_snapshot("BTCUSDT", "RuntimeError: public endpoint unavailable")
    stateful_synthetic = server.execution_market_freshness("binance_testnet_place_order", synthetic)
    if stateful_synthetic.get("status") != "fail":
        return fail("stateful testnet placement accepted synthetic/fallback market data", stateful_synthetic)

    validate_synthetic = server.execution_market_freshness("binance_testnet_validate", synthetic)
    if validate_synthetic.get("status") != "pass":
        return fail("/order/test validation mode should not require stateful market freshness", validate_synthetic)

    fresh_public = fresh_public_market()
    live_fresh = server.execution_market_freshness("live_guarded", fresh_public)
    if live_fresh.get("status") != "pass":
        return fail("live guarded rejected a fresh Binance public snapshot", live_fresh)

    stale_public = {**fresh_public, "timestamp": "2000-01-01T00:00:00+00:00"}
    live_stale = server.execution_market_freshness("live_guarded", stale_public)
    if live_stale.get("status") != "fail":
        return fail("live guarded accepted a stale Binance public snapshot", live_stale)

    try:
        server.assert_fresh_execution_market_snapshot("live_guarded", synthetic)
        return fail("assert_fresh_execution_market_snapshot accepted synthetic live market data")
    except ValueError as exc:
        if "Execution market snapshot is not fresh" not in str(exc):
            return fail("unexpected market freshness assertion error", {"error": str(exc)})

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
        "rationale": "market freshness check",
    }
    original_account_state_for_mode = server.account_state_for_mode
    try:
        server.account_state_for_mode = lambda mode: fresh_account(str(mode or "").lower().strip())
        risk = server.risk_check(intent, synthetic, "binance_testnet_place_order")
    finally:
        server.account_state_for_mode = original_account_state_for_mode
    market_check = next((item for item in risk.get("checks", []) if item.get("name") == "Market snapshot freshness"), None)
    if not market_check:
        return fail("risk checks do not include Market snapshot freshness", risk)
    if market_check.get("status") != "fail" or risk.get("status") != "rejected":
        return fail("risk did not reject stateful execution on synthetic market data", risk)

    print(
        json.dumps(
            {
                "ok": True,
                "stateful_synthetic_status": stateful_synthetic.get("status"),
                "validate_synthetic_status": validate_synthetic.get("status"),
                "live_fresh_status": live_fresh.get("status"),
                "live_stale_status": live_stale.get("status"),
                "risk_market_check": market_check,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
