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


def make_order(order_id: str) -> dict[str, Any]:
    now = server.utc_now()
    return {
        "id": order_id,
        "run_id": "RUN-PROTECTION-UNKNOWN-CHECK",
        "symbol": "BTCUSDT",
        "side": "BUY",
        "order_type": "LIMIT",
        "quantity": 0.01,
        "leverage": 2,
        "entry_price": 50000.0,
        "stop_loss": 49000.0,
        "take_profit": 52000.0,
        "status": "testnet_submitted",
        "client_order_id": order_id,
        "venue_order_id": "ENTRY-VENUE",
        "venue_status": "NEW",
        "reconcile_status": "needs_reconcile",
        "reconcile_note": "entry submitted for protection unknown smoke test",
        "last_reconciled_at": None,
        "created_at": now,
        "updated_at": now,
        "parent_order_id": None,
        "protection_kind": None,
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
    parent_id = f"TESTLIVE-PROTECT-UNKNOWN-{suffix}"
    stop_id = f"{parent_id}-SL"
    take_id = f"{parent_id}-TP"
    order_ids = [parent_id, stop_id, take_id]
    original = {
        "ENABLE_BINANCE_TESTNET": server.ENABLE_BINANCE_TESTNET,
        "BINANCE_API_KEY": server.BINANCE_API_KEY,
        "BINANCE_API_SECRET": server.BINANCE_API_SECRET,
        "signed_binance_request_for_mode": server.signed_binance_request_for_mode,
        "raise_alert": server.raise_alert,
        "insert_event": server.insert_event,
    }
    calls: list[dict[str, Any]] = []
    alerts: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []

    try:
        cleanup(order_ids)
        seed_rules("BTCUSDT", "binance_testnet_place_order")
        server.persist_order(make_order(parent_id))
        server.ENABLE_BINANCE_TESTNET = True
        server.BINANCE_API_KEY = "test-key"
        server.BINANCE_API_SECRET = "test-secret"

        def fake_signed(method: str, path: str, params: dict[str, Any], mode: str) -> dict[str, Any]:
            calls.append({"method": method, "path": path, "params": dict(params), "mode": mode})
            if method == "POST" and path == "/fapi/v1/order":
                if params.get("type") == "TAKE_PROFIT_MARKET":
                    raise RuntimeError("simulated timeout after take-profit submit reached venue")
                return {"status": "NEW", "orderId": "VENUE-SL"}
            if method == "DELETE" and path == "/fapi/v1/order":
                return {
                    "status": "CANCELED",
                    "orderId": f"VENUE-CANCEL-{params.get('origClientOrderId')}",
                }
            return {"ok": True}

        def fake_raise_alert(
            key: str,
            severity: str,
            source: str,
            title: str,
            body: str,
            payload: dict[str, Any] | None = None,
        ) -> dict[str, Any]:
            alert = {
                "key": key,
                "severity": severity,
                "source": source,
                "title": title,
                "body": body,
                "payload": payload or {},
            }
            alerts.append(alert)
            return alert

        def fake_insert_event(
            run_id: str,
            kind: str,
            actor: str,
            title: str,
            body: str,
            payload: dict[str, Any] | None = None,
        ) -> dict[str, Any]:
            event = {
                "run_id": run_id,
                "kind": kind,
                "actor": actor,
                "title": title,
                "body": body,
                "payload": payload or {},
            }
            events.append(event)
            return event

        server.signed_binance_request_for_mode = fake_signed
        server.raise_alert = fake_raise_alert
        server.insert_event = fake_insert_event

        try:
            server.submit_binance_protection_orders(server.get_order(parent_id) or {}, "binance_testnet_place_order")
            return fail("protection submit should raise the simulated unknown take-profit failure")
        except RuntimeError as exc:
            if "simulated timeout" not in str(exc):
                return fail("unexpected protection submit error", str(exc))

        stop_child = server.get_order(stop_id) or {}
        unknown_child = server.get_order(take_id) or {}
        if stop_child.get("status") != "testnet_protection_submitted":
            return fail("successfully submitted stop-loss child was not persisted", stop_child)
        if unknown_child.get("status") != "testnet_protection_submitted":
            return fail("unknown take-profit child was not persisted as a cancelable protection order", unknown_child)
        if unknown_child.get("venue_status") != "UNKNOWN" or unknown_child.get("reconcile_status") != "needs_reconcile":
            return fail("unknown child did not require venue reconciliation", unknown_child)
        if unknown_child.get("parent_order_id") != parent_id or unknown_child.get("protection_kind") != "take_profit":
            return fail("unknown child did not preserve parent/protection linkage", unknown_child)
        if "clientOrderId before retry" not in unknown_child.get("reconcile_note", ""):
            return fail("unknown child note does not instruct clientOrderId reconcile before retry", unknown_child)

        guarded = server.handle_binance_protection_submit_failure(
            server.get_order(parent_id) or {},
            RuntimeError("take-profit submit unknown after venue accept"),
            "binance_testnet_place_order",
        )
        guard = guarded.get("guard") or {}
        if guard.get("status") != "entry_canceled":
            return fail("guard should safely cancel entry and known/unknown protection children", guard)
        attempts = guard.get("protection_cancel_attempts") or []
        resolved_child_ids = sorted(
            str(item.get("order_id"))
            for item in attempts
            if item.get("status") in {"canceled", "skipped"}
        )
        if resolved_child_ids != sorted([stop_id, take_id]):
            return fail("guard did not resolve both known and unknown protection children", guard)
        unknown_after_guard = server.get_order(take_id) or {}
        if unknown_after_guard.get("status") != "testnet_protection_canceled":
            return fail("unknown child was not cancelable through OMS after guard handling", unknown_after_guard)
        canceled_client_ids = [
            call["params"].get("origClientOrderId")
            for call in calls
            if call["method"] == "DELETE" and call["path"] == "/fapi/v1/order"
        ]
        if canceled_client_ids != [parent_id, stop_id, take_id]:
            return fail("cancel calls did not target parent, known child, then unknown child by client order id", calls)
        if not alerts or not events:
            return fail("protection failure guard did not emit alert and audit event", {"alerts": alerts, "events": events})

        print(
            json.dumps(
                {
                    "ok": True,
                    "unknown_child": {
                        "status": unknown_child.get("status"),
                        "venue_status": unknown_child.get("venue_status"),
                        "reconcile_status": unknown_child.get("reconcile_status"),
                        "protection_kind": unknown_child.get("protection_kind"),
                    },
                    "guard_status": guard.get("status"),
                    "cancel_client_order_ids": canceled_client_ids,
                    "guard_child_attempts": [
                        {"order_id": item.get("order_id"), "status": item.get("status")}
                        for item in attempts
                    ],
                    "alert_count": len(alerts),
                    "event_count": len(events),
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
        server.raise_alert = original["raise_alert"]
        server.insert_event = original["insert_event"]
        cleanup(order_ids)


if __name__ == "__main__":
    raise SystemExit(main())
