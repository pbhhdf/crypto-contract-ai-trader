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


def make_order(order_id: str, status: str, parent_order_id: str | None = None, protection_kind: str | None = None) -> dict[str, Any]:
    now = server.utc_now()
    return {
        "id": order_id,
        "run_id": "RUN-PARENT-CANCEL-CASCADE-CHECK",
        "symbol": "BTCUSDT",
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
        "venue_status": "NEW",
        "reconcile_status": "needs_reconcile",
        "reconcile_note": "",
        "last_reconciled_at": None,
        "created_at": now,
        "updated_at": now,
        "parent_order_id": parent_order_id,
        "protection_kind": protection_kind,
    }


def cleanup(order_ids: list[str]) -> None:
    placeholders = ", ".join("?" for _ in order_ids)
    with server.DB_LOCK, server.connect() as conn:
        conn.execute(f"DELETE FROM order_transitions WHERE order_id IN ({placeholders})", order_ids)
        conn.execute(f"DELETE FROM orders WHERE id IN ({placeholders})", order_ids)
        conn.commit()


def main() -> int:
    server.init_db()
    suffix = str(uuid.uuid4())[:8].upper()
    parent_id = f"TESTLIVE-CASCADE-{suffix}"
    child_id = f"TESTLIVE-CASCADE-SL-{suffix}"
    order_ids = [parent_id, child_id]
    original = {
        "ENABLE_BINANCE_TESTNET": server.ENABLE_BINANCE_TESTNET,
        "BINANCE_API_KEY": server.BINANCE_API_KEY,
        "BINANCE_API_SECRET": server.BINANCE_API_SECRET,
        "signed_binance_request_for_mode": server.signed_binance_request_for_mode,
    }
    calls: list[dict[str, Any]] = []

    try:
        cleanup(order_ids)
        server.persist_order(make_order(parent_id, "testnet_submitted"))
        server.persist_order(make_order(child_id, "testnet_protection_submitted", parent_id, "stop_loss"))
        server.ENABLE_BINANCE_TESTNET = True
        server.BINANCE_API_KEY = "test-key"
        server.BINANCE_API_SECRET = "test-secret"

        def fake_signed(method: str, path: str, params: dict[str, Any], mode: str) -> dict[str, Any]:
            calls.append({"method": method, "path": path, "params": params, "mode": mode})
            return {"status": "CANCELED", "orderId": f"VENUE-{len(calls)}"}

        server.signed_binance_request_for_mode = fake_signed
        result = server.cancel_testnet_order(parent_id)
        if result.get("status") != "testnet_canceled":
            return fail("parent cancel did not mark parent canceled", result)
        attempts = result.get("child_protection_cancel_attempts") or []
        if len(attempts) != 1 or attempts[0].get("status") != "canceled":
            return fail("parent cancel did not cascade to child protection order", result)
        child = server.get_order(child_id) or {}
        if child.get("status") != "testnet_protection_canceled":
            return fail("child protection order was not marked canceled", child)
        canceled_client_ids = [call["params"].get("origClientOrderId") for call in calls]
        if canceled_client_ids != [parent_id, child_id]:
            return fail("cancel calls did not target parent then child client order ids", calls)

        print(
            json.dumps(
                {
                    "ok": True,
                    "parent_status": result.get("status"),
                    "child_status": child.get("status"),
                    "cancel_order": canceled_client_ids,
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
        server.signed_binance_request_for_mode = original["signed_binance_request_for_mode"]
        cleanup(order_ids)


if __name__ == "__main__":
    raise SystemExit(main())
