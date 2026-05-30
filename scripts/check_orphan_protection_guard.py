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
        "run_id": "RUN-ORPHAN-PROTECTION-CHECK",
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
    if not order_ids:
        return
    placeholders = ", ".join("?" for _ in order_ids)
    with server.DB_LOCK, server.connect() as conn:
        conn.execute(f"DELETE FROM order_transitions WHERE order_id IN ({placeholders})", order_ids)
        conn.execute(f"DELETE FROM orders WHERE id IN ({placeholders})", order_ids)
        conn.commit()


def private_order_event(client_order_id: str, venue_status: str, filled_qty: str = "0") -> dict[str, Any]:
    return {
        "e": "ORDER_TRADE_UPDATE",
        "o": {
            "c": client_order_id,
            "i": 987654321,
            "x": venue_status,
            "X": venue_status,
            "z": filled_qty,
            "ap": "0",
            "rp": "0",
        },
    }


def main() -> int:
    server.init_db()
    suffix = str(uuid.uuid4())[:8].upper()
    reconcile_parent = f"TESTLIVE-ORPHAN-REC-{suffix}"
    reconcile_child = f"TESTLIVE-ORPHAN-REC-SL-{suffix}"
    stream_parent = f"TESTLIVE-ORPHAN-STR-{suffix}"
    stream_child = f"TESTLIVE-ORPHAN-STR-SL-{suffix}"
    partial_reconcile_parent = f"TESTLIVE-ORPHAN-PREC-{suffix}"
    partial_reconcile_child = f"TESTLIVE-ORPHAN-PREC-SL-{suffix}"
    partial_stream_parent = f"TESTLIVE-ORPHAN-PSTR-{suffix}"
    partial_stream_child = f"TESTLIVE-ORPHAN-PSTR-SL-{suffix}"
    filled_parent = f"TESTLIVE-ORPHAN-FILL-{suffix}"
    filled_child = f"TESTLIVE-ORPHAN-FILL-SL-{suffix}"
    order_ids = [
        reconcile_parent,
        reconcile_child,
        stream_parent,
        stream_child,
        partial_reconcile_parent,
        partial_reconcile_child,
        partial_stream_parent,
        partial_stream_child,
        filled_parent,
        filled_child,
    ]
    original = {
        "ENABLE_BINANCE_TESTNET": server.ENABLE_BINANCE_TESTNET,
        "BINANCE_API_KEY": server.BINANCE_API_KEY,
        "BINANCE_API_SECRET": server.BINANCE_API_SECRET,
        "signed_binance_request_for_mode": server.signed_binance_request_for_mode,
    }
    calls: list[dict[str, Any]] = []

    try:
        cleanup(order_ids)
        server.ENABLE_BINANCE_TESTNET = True
        server.BINANCE_API_KEY = "test-key"
        server.BINANCE_API_SECRET = "test-secret"

        def fake_signed(method: str, path: str, params: dict[str, Any], mode: str) -> dict[str, Any]:
            calls.append({"method": method, "path": path, "params": params, "mode": mode})
            if method == "GET" and path == "/fapi/v1/order":
                executed_qty = "0.005" if params.get("origClientOrderId") == partial_reconcile_parent else "0"
                return {
                    "status": "EXPIRED",
                    "orderId": "VENUE-PARENT-EXPIRED",
                    "executedQty": executed_qty,
                    "avgPrice": "0",
                }
            if method == "DELETE" and path == "/fapi/v1/order":
                return {"status": "CANCELED", "orderId": f"VENUE-CANCEL-{len(calls)}"}
            raise AssertionError(f"unexpected signed request: {method} {path}")

        server.signed_binance_request_for_mode = fake_signed

        server.persist_order(make_order(reconcile_parent, "testnet_submitted"))
        server.persist_order(make_order(reconcile_child, "testnet_protection_submitted", reconcile_parent, "stop_loss"))
        reconciled = server.reconcile_order(reconcile_parent)
        if reconciled.get("status") != "testnet_canceled":
            return fail("reconcile did not mark terminal parent canceled", reconciled)
        reconcile_attempts = reconciled.get("child_protection_cancel_attempts") or []
        if len(reconcile_attempts) != 1 or reconcile_attempts[0].get("status") != "canceled":
            return fail("reconcile did not cancel child protection after terminal parent", reconciled)
        reconcile_child_order = server.get_order(reconcile_child) or {}
        if reconcile_child_order.get("status") != "testnet_protection_canceled":
            return fail("reconcile child protection order was not marked canceled", reconcile_child_order)

        calls.clear()
        server.persist_order(make_order(stream_parent, "testnet_submitted"))
        server.persist_order(make_order(stream_child, "testnet_protection_submitted", stream_parent, "stop_loss"))
        processed, note = server.handle_private_order_update(
            "binance_testnet_place_order",
            private_order_event(stream_parent, "CANCELED"),
        )
        if not processed or "child protection terminal-parent actions=1" not in note:
            return fail("private stream update did not report child protection cleanup", {"processed": processed, "note": note})
        stream_child_order = server.get_order(stream_child) or {}
        if stream_child_order.get("status") != "testnet_protection_canceled":
            return fail("private stream child protection order was not marked canceled", stream_child_order)
        stream_cancel_ids = [call["params"].get("origClientOrderId") for call in calls if call["method"] == "DELETE"]
        if stream_cancel_ids != [stream_child]:
            return fail("private stream cleanup did not cancel the expected child order", calls)

        calls.clear()
        server.persist_order(make_order(partial_reconcile_parent, "testnet_submitted"))
        server.persist_order(make_order(partial_reconcile_child, "testnet_protection_submitted", partial_reconcile_parent, "stop_loss"))
        partial_reconciled = server.reconcile_order(partial_reconcile_parent)
        partial_reconcile_attempts = partial_reconciled.get("child_protection_cancel_attempts") or []
        if len(partial_reconcile_attempts) != 1 or partial_reconcile_attempts[0].get("status") != "kept":
            return fail("partial-fill reconcile should keep child protection active", partial_reconciled)
        partial_reconcile_child_order = server.get_order(partial_reconcile_child) or {}
        if partial_reconcile_child_order.get("status") != "testnet_protection_submitted":
            return fail("partial-fill reconcile canceled child protection unexpectedly", partial_reconcile_child_order)
        partial_reconcile_cancel_ids = [call["params"].get("origClientOrderId") for call in calls if call["method"] == "DELETE"]
        if partial_reconcile_cancel_ids:
            return fail("partial-fill reconcile should not send child cancel requests", calls)

        calls.clear()
        server.persist_order(make_order(partial_stream_parent, "testnet_submitted"))
        server.persist_order(make_order(partial_stream_child, "testnet_protection_submitted", partial_stream_parent, "stop_loss"))
        processed, note = server.handle_private_order_update(
            "binance_testnet_place_order",
            private_order_event(partial_stream_parent, "CANCELED", filled_qty="0.005"),
        )
        if not processed or "child protection terminal-parent actions=1" not in note:
            return fail("partial-fill private stream update did not preserve child evidence", {"processed": processed, "note": note})
        partial_stream_child_order = server.get_order(partial_stream_child) or {}
        if partial_stream_child_order.get("status") != "testnet_protection_submitted":
            return fail("partial-fill private stream canceled child protection unexpectedly", partial_stream_child_order)
        partial_stream_cancel_ids = [call["params"].get("origClientOrderId") for call in calls if call["method"] == "DELETE"]
        if partial_stream_cancel_ids:
            return fail("partial-fill private stream should not send child cancel requests", calls)

        calls.clear()
        server.persist_order(make_order(filled_parent, "testnet_submitted"))
        server.persist_order(make_order(filled_child, "testnet_protection_submitted", filled_parent, "stop_loss"))
        processed, note = server.handle_private_order_update(
            "binance_testnet_place_order",
            private_order_event(filled_parent, "FILLED"),
        )
        if not processed:
            return fail("filled private stream event was not processed", {"note": note})
        filled_child_order = server.get_order(filled_child) or {}
        if filled_child_order.get("status") != "testnet_protection_submitted":
            return fail("filled parent should keep protective child orders active", filled_child_order)
        filled_cancel_ids = [call["params"].get("origClientOrderId") for call in calls if call["method"] == "DELETE"]
        if filled_cancel_ids:
            return fail("filled parent unexpectedly canceled child protection orders", calls)

        print(
            json.dumps(
                {
                    "ok": True,
                    "reconcile_parent_status": reconciled.get("status"),
                    "reconcile_child_status": reconcile_child_order.get("status"),
                    "stream_child_status": stream_child_order.get("status"),
                    "partial_reconcile_child_status": partial_reconcile_child_order.get("status"),
                    "partial_stream_child_status": partial_stream_child_order.get("status"),
                    "filled_child_status": filled_child_order.get("status"),
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
