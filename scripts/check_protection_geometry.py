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


def snapshot(symbol: str = "BTCUSDT") -> dict[str, Any]:
    return {
        "symbol": symbol,
        "mark_price": 50000.0,
        "source": "binance_public",
        "is_synthetic": False,
        "fallback": False,
        "fetched_at": server.utc_now(),
        "funding_rate": 0.0001,
        "open_interest": 1000000,
        "open_interest_change_pct": 1.0,
        "realized_volatility_pct": 2.0,
        "order_book_imbalance": 0.1,
        "liquidation_pressure": "low",
    }


def intent(side: str, stop_loss: float, take_profit: float) -> dict[str, Any]:
    return {
        "symbol": "BTCUSDT",
        "side": side,
        "score": 1.0 if side == "BUY" else -1.0,
        "confidence": 0.7,
        "entry_price": 50000.0,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "leverage": 2,
        "position_pct": 0.02,
        "time_horizon": "30-90 minutes",
    }


def order_from_intent(trade_intent: dict[str, Any]) -> dict[str, Any]:
    return server.prepare_order_payload(
        "RUN-PROTECTION-GEOMETRY",
        trade_intent,
        "TEST",
        10000.0,
        {"source": "check"},
    )


def main() -> int:
    original_signed = server.signed_binance_request_for_mode
    original_risk_config = server.risk_config
    original_account = server.account_state_for_mode
    original_conflicts = server.stateful_order_conflicts
    calls: list[dict[str, Any]] = []
    try:
        valid_buy = intent("BUY", 49000.0, 52000.0)
        buy_geometry = server.protection_geometry(valid_buy)
        if buy_geometry.get("status") != "pass" or buy_geometry.get("reward_risk_ratio") != 2.0:
            return fail("valid BUY geometry did not pass", buy_geometry)

        valid_sell = intent("SELL", 51000.0, 48000.0)
        sell_geometry = server.protection_geometry(valid_sell)
        if sell_geometry.get("status") != "pass" or sell_geometry.get("reward_risk_ratio") != 2.0:
            return fail("valid SELL geometry did not pass", sell_geometry)

        invalid_buy = intent("BUY", 50500.0, 52000.0)
        invalid_geometry = server.protection_geometry(invalid_buy)
        if invalid_geometry.get("status") != "fail":
            return fail("invalid BUY stop-loss geometry should fail", invalid_geometry)
        try:
            server.assert_valid_protection_geometry(invalid_buy)
            return fail("assert_valid_protection_geometry accepted invalid BUY geometry")
        except ValueError:
            pass

        poor_ratio = intent("BUY", 49000.0, 50500.0)
        poor_geometry = server.protection_geometry(poor_ratio)
        if poor_geometry.get("status") != "fail" or "reward/risk" not in poor_geometry.get("detail", ""):
            return fail("poor reward/risk geometry should fail", poor_geometry)

        server.risk_config = lambda: {
            "max_leverage": 3.0,
            "max_position_pct": 0.05,
            "max_order_notional_usdt": 0.0,
            "max_daily_loss_pct": 0.03,
            "max_open_positions": 8,
            "max_consecutive_losses": 3,
            "allowed_symbols": ["BTCUSDT"],
            "emergency_stop": False,
        }
        server.account_state_for_mode = lambda _mode: {
            "source": "check",
            "equity_usdt": 10000.0,
            "free_margin_usdt": 10000.0,
            "open_position_count": 0,
            "snapshot_id": "check",
            "fetched_at": server.utc_now(),
        }
        server.stateful_order_conflicts = lambda _mode, _symbol: []
        risk = server.risk_check(poor_ratio, snapshot(), "paper")
        if risk.get("status") != "rejected":
            return fail("risk_check should reject poor protection geometry", risk)
        protection_row = next((item for item in risk.get("checks", []) if item.get("name") == "Protection geometry"), None)
        if not protection_row or protection_row.get("status") != "fail":
            return fail("risk_check did not expose failing Protection geometry row", risk)

        seed_rules("BTCUSDT", "binance_testnet_validate")
        valid_order = order_from_intent(valid_buy)
        stop_params, stop_evidence = server.binance_protection_order_params(
            valid_order,
            "stop_loss",
            "binance_testnet_validate",
        )
        if stop_params["stopPrice"] != "49000" or stop_evidence.get("protection_geometry", {}).get("status") != "pass":
            return fail("Binance protection params did not carry passing geometry evidence", stop_evidence)

        invalid_order = order_from_intent(invalid_buy)
        try:
            server.binance_protection_order_params(invalid_order, "stop_loss", "binance_testnet_validate")
            return fail("Binance protection params accepted invalid geometry")
        except ValueError:
            pass

        def fake_signed(method: str, path: str, params: dict[str, Any], mode: str) -> dict[str, Any]:
            calls.append({"method": method, "path": path, "params": params, "mode": mode})
            return {"ok": True}

        server.signed_binance_request_for_mode = fake_signed
        entry_params = server.binance_order_params(invalid_order, "binance_testnet_validate")
        try:
            server.validate_binance_order_bundle(invalid_order, entry_params, "binance_testnet_validate")
            return fail("pre-submit validation accepted invalid protection geometry")
        except ValueError:
            pass
        if calls:
            return fail("invalid protection geometry should fail before any Binance /order/test call", calls)

        print(
            json.dumps(
                {
                    "ok": True,
                    "valid_buy": buy_geometry,
                    "valid_sell": sell_geometry,
                    "invalid_buy": invalid_geometry,
                    "poor_ratio": poor_geometry,
                    "risk_status": risk.get("status"),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    finally:
        server.signed_binance_request_for_mode = original_signed
        server.risk_config = original_risk_config
        server.account_state_for_mode = original_account
        server.stateful_order_conflicts = original_conflicts


if __name__ == "__main__":
    raise SystemExit(main())
