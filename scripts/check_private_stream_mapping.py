from __future__ import annotations

import json
import sys
import time
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
        "entry_price": 100000.0,
        "stop_loss": 99000.0,
        "take_profit": 103000.0,
        "leverage": 1.0,
        "position_pct": 0.001,
    }
    order = server.prepare_order_payload(f"stream-check-{int(time.time())}", intent, "TESTLIVE")
    server.persist_order(order)
    event = {
        "e": "ORDER_TRADE_UPDATE",
        "E": int(time.time() * 1000),
        "T": int(time.time() * 1000),
        "o": {
            "s": "BTCUSDT",
            "c": order["client_order_id"],
            "S": "BUY",
            "o": "LIMIT",
            "x": "TRADE",
            "X": "FILLED",
            "i": 123456789,
            "l": str(order["quantity"]),
            "z": str(order["quantity"]),
            "L": "100000",
            "ap": "100000",
            "rp": "1.23",
        },
    }
    stored = server.handle_binance_user_stream_event("binance_testnet_place_order", event)
    updated = server.get_order(order["id"]) or {}
    if not stored.get("processed"):
        return fail("private stream order event was stored but not processed")
    if updated.get("status") != "testnet_filled":
        return fail(f"expected testnet_filled, got {updated.get('status')}")
    if updated.get("reconcile_status") != "reconciled":
        return fail(f"expected reconciled, got {updated.get('reconcile_status')}")
    if updated.get("venue_status") != "FILLED":
        return fail(f"expected FILLED venue status, got {updated.get('venue_status')}")

    print(
        json.dumps(
            {
                "ok": True,
                "event_id": stored["id"],
                "order_id": updated["id"],
                "status": updated["status"],
                "reconcile_status": updated["reconcile_status"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
