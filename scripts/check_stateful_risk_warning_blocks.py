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


def main() -> int:
    original_signed = server.signed_binance_request_for_mode
    original_signed_testnet = server.signed_binance_request
    original_assert_conflicts = server.assert_no_stateful_order_conflicts
    original_assert_open_orders = server.assert_no_exchange_open_orders
    original_assert_positions = server.assert_no_exchange_positions
    calls: list[dict[str, Any]] = []
    try:
        intent = {
            "symbol": "BTCUSDT",
            "side": "BUY",
            "position_pct": 0.01,
            "leverage": 2,
            "entry_price": 50000.0,
            "stop_loss": 49000.0,
            "take_profit": 52000.0,
        }
        risk = {
            "status": "warning",
            "account": {
                "source": "binance_testnet_place_order",
                "snapshot_id": "EXSNAP-WARNING-BLOCK",
                "synced_at": server.utc_now(),
                "equity_usdt": 1000,
                "free_margin_usdt": 900,
                "open_position_count": 0,
            },
            "market": {
                "data_source": "binance_public",
                "fallback": False,
                "source_error": "",
                "timestamp": server.utc_now(),
                "mark_price": 50000,
            },
        }

        def fake_signed(*args: Any, **kwargs: Any) -> dict[str, Any]:
            calls.append({"args": args, "kwargs": kwargs})
            raise AssertionError("warning risk must not reach Binance signed request")

        server.signed_binance_request_for_mode = fake_signed
        server.signed_binance_request = fake_signed
        server.assert_no_stateful_order_conflicts = lambda mode, symbol: []
        server.assert_no_exchange_open_orders = lambda mode: {"status": "pass", "mode": mode}
        server.assert_no_exchange_positions = lambda mode: {"status": "pass", "mode": mode}

        result = server.execute_order("RUN-WARNING-BLOCK", intent, risk, "binance_testnet_place_order")
        if result is not None:
            return fail("stateful warning risk produced an order", result)
        if calls:
            return fail("stateful warning risk reached signed Binance request", calls)
        reason = risk.get("execution_blocked_reason") or ""
        if "requires risk status approved" not in reason:
            return fail("risk warning did not record an execution block reason", risk)

        print(
            json.dumps(
                {
                    "ok": True,
                    "result": result,
                    "signed_call_count": len(calls),
                    "execution_blocked_reason": reason,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    finally:
        server.signed_binance_request_for_mode = original_signed
        server.signed_binance_request = original_signed_testnet
        server.assert_no_stateful_order_conflicts = original_assert_conflicts
        server.assert_no_exchange_open_orders = original_assert_open_orders
        server.assert_no_exchange_positions = original_assert_positions


if __name__ == "__main__":
    raise SystemExit(main())
