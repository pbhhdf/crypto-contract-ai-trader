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
    status: str,
    parent_order_id: str | None = None,
    protection_kind: str | None = None,
) -> dict[str, Any]:
    now = server.utc_now()
    return {
        "id": order_id,
        "run_id": "RUN-SIBLING-PROTECTION-CHECK",
        "symbol": "BTCUSDT",
        "side": "BUY" if not parent_order_id else "SELL",
        "order_type": "LIMIT" if not parent_order_id else "STOP_MARKET",
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
            "ap": "50050",
            "rp": "12.34",
        },
    }


def persist_parent_pair(parent: str, stop: str, take: str) -> None:
    server.persist_order(make_order(parent, "testnet_submitted"))
    server.persist_order(make_order(stop, "testnet_protection_submitted", parent, "stop_loss"))
    server.persist_order(make_order(take, "testnet_protection_submitted", parent, "take_profit"))


def main() -> int:
    server.init_db()
    suffix = str(uuid.uuid4())[:8].upper()
    reconcile_parent = f"TESTLIVE-SIB-REC-{suffix}"
    reconcile_stop = f"TESTLIVE-SIB-REC-SL-{suffix}"
    reconcile_take = f"TESTLIVE-SIB-REC-TP-{suffix}"
    stream_parent = f"TESTLIVE-SIB-STR-{suffix}"
    stream_stop = f"TESTLIVE-SIB-STR-SL-{suffix}"
    stream_take = f"TESTLIVE-SIB-STR-TP-{suffix}"
    canceled_parent = f"TESTLIVE-SIB-CAN-{suffix}"
    canceled_stop = f"TESTLIVE-SIB-CAN-SL-{suffix}"
    canceled_take = f"TESTLIVE-SIB-CAN-TP-{suffix}"
    order_ids = [
        reconcile_parent,
        reconcile_stop,
        reconcile_take,
        stream_parent,
        stream_stop,
        stream_take,
        canceled_parent,
        canceled_stop,
        canceled_take,
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
            calls.append({"method": method, "path": path, "params": dict(params), "mode": mode})
            if method == "GET" and path == "/fapi/v1/order":
                return {
                    "status": "FILLED",
                    "orderId": "VENUE-PROTECTION-FILL",
                    "executedQty": "0.01",
                    "avgPrice": "50050",
                }
            if method == "DELETE" and path == "/fapi/v1/order":
                return {
                    "status": "CANCELED",
                    "orderId": f"VENUE-CANCEL-{params.get('origClientOrderId')}",
                }
            raise AssertionError(f"unexpected signed request: {method} {path}")

        server.signed_binance_request_for_mode = fake_signed

        persist_parent_pair(reconcile_parent, reconcile_stop, reconcile_take)
        reconciled = server.reconcile_order(reconcile_stop)
        reconcile_attempts = reconciled.get("sibling_protection_cancel_attempts") or []
        if reconciled.get("status") != "testnet_protection_filled":
            return fail("filled stop-loss child was not marked filled during reconcile", reconciled)
        if len(reconcile_attempts) != 1 or reconcile_attempts[0].get("order_id") != reconcile_take:
            return fail("reconcile did not cancel the take-profit sibling after stop-loss fill", reconciled)
        reconcile_take_order = server.get_order(reconcile_take) or {}
        if reconcile_take_order.get("status") != "testnet_protection_canceled":
            return fail("take-profit sibling was not canceled after stop-loss fill reconcile", reconcile_take_order)
        reconcile_parent_order = server.get_order(reconcile_parent) or {}
        if reconcile_parent_order.get("status") != "testnet_protected_exit":
            return fail("parent order was not marked exited by protection after reconcile", reconcile_parent_order)
        if reconcile_parent_order.get("reconcile_status") != "reconciled":
            return fail("parent protection exit should be reconciled", reconcile_parent_order)
        if server.stateful_order_conflict_reason(reconcile_parent_order, "binance_testnet_place_order", "BTCUSDT"):
            return fail("protected-exit parent should not block new stateful executions", reconcile_parent_order)

        calls.clear()
        persist_parent_pair(stream_parent, stream_stop, stream_take)
        stream_processed, stream_note = server.handle_private_order_update(
            "binance_testnet_place_order",
            private_order_event(stream_take, "FILLED", filled_qty="0.01"),
        )
        if not stream_processed or "sibling protection child-fill actions=1" not in stream_note:
            return fail(
                "private stream did not report sibling cleanup after take-profit fill",
                {"processed": stream_processed, "note": stream_note},
            )
        stream_stop_order = server.get_order(stream_stop) or {}
        stream_take_order = server.get_order(stream_take) or {}
        if stream_take_order.get("status") != "testnet_protection_filled":
            return fail("take-profit child was not marked protection-filled from private stream", stream_take_order)
        if stream_stop_order.get("status") != "testnet_protection_canceled":
            return fail("stop-loss sibling was not canceled after take-profit fill stream event", stream_stop_order)
        stream_parent_order = server.get_order(stream_parent) or {}
        if stream_parent_order.get("status") != "testnet_protected_exit":
            return fail("parent order was not marked exited by protection from private stream", stream_parent_order)
        stream_cancel_ids = [call["params"].get("origClientOrderId") for call in calls if call["method"] == "DELETE"]
        if stream_cancel_ids != [stream_stop]:
            return fail("private stream sibling cleanup canceled the wrong order", calls)

        calls.clear()
        persist_parent_pair(canceled_parent, canceled_stop, canceled_take)
        canceled_processed, canceled_note = server.handle_private_order_update(
            "binance_testnet_place_order",
            private_order_event(canceled_stop, "CANCELED", filled_qty="0"),
        )
        if not canceled_processed:
            return fail("canceled child private stream event was not processed", canceled_note)
        canceled_take_order = server.get_order(canceled_take) or {}
        if canceled_take_order.get("status") != "testnet_protection_submitted":
            return fail("zero-fill canceled child should not cancel the sibling protection order", canceled_take_order)
        canceled_parent_order = server.get_order(canceled_parent) or {}
        if canceled_parent_order.get("status") != "testnet_submitted":
            return fail("zero-fill canceled child should not mark parent as protection-exited", canceled_parent_order)
        zero_fill_cancel_ids = [call["params"].get("origClientOrderId") for call in calls if call["method"] == "DELETE"]
        if zero_fill_cancel_ids:
            return fail("zero-fill canceled child should not send sibling cancel requests", calls)

        print(
            json.dumps(
                {
                    "ok": True,
                    "reconcile": {
                        "filled_child": reconciled.get("status"),
                        "parent_status": reconcile_parent_order.get("status"),
                        "canceled_sibling": reconcile_take_order.get("status"),
                    },
                    "private_stream": {
                        "processed": stream_processed,
                        "note": stream_note,
                        "filled_child": stream_take_order.get("status"),
                        "parent_status": stream_parent_order.get("status"),
                        "canceled_sibling": stream_stop_order.get("status"),
                    },
                    "zero_fill_cancel": {
                        "parent_status": canceled_parent_order.get("status"),
                        "remaining_sibling": canceled_take_order.get("status"),
                        "cancel_calls": zero_fill_cancel_ids,
                    },
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
