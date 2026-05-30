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
        "run_id": "RUN-PROTECTION-GUARD-CHECK",
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
    parent_id = f"LIVE-GUARD-{suffix}"
    child_id = f"LIVE-GUARD-SL-{suffix}"
    stuck_parent_id = f"LIVE-GUARD-STUCK-{suffix}"
    stuck_child_id = f"LIVE-GUARD-STUCK-SL-{suffix}"
    order_ids = [parent_id, child_id, stuck_parent_id, stuck_child_id]

    original = {
        "cancel_testnet_order": server.cancel_testnet_order,
        "disarm_live_trading": server.disarm_live_trading,
        "raise_alert": server.raise_alert,
        "insert_event": server.insert_event,
    }
    cancel_calls: list[str] = []
    disarm_reasons: list[str] = []
    alerts: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []

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

    def fake_disarm(reason: str = "manual_disarm") -> dict[str, Any]:
        disarm_reasons.append(reason)
        return {"armed": False, "reason": reason}

    try:
        cleanup(order_ids)
        server.persist_order(make_order(parent_id, "live_submitted"))
        server.persist_order(make_order(child_id, "live_protection_submitted", parent_id, "stop_loss"))
        server.persist_order(make_order(stuck_parent_id, "live_submitted"))
        server.persist_order(make_order(stuck_child_id, "live_protection_submitted", stuck_parent_id, "stop_loss"))

        def fake_cancel(order_id: str) -> dict[str, Any]:
            cancel_calls.append(order_id)
            if order_id == stuck_parent_id:
                raise RuntimeError("entry already unknown")
            current = server.get_order(order_id)
            if not current:
                raise RuntimeError("missing order")
            status = "live_protection_canceled" if current.get("parent_order_id") else "live_canceled"
            return server.update_order_state(
                order_id,
                status=status,
                venue_status="CANCELED",
                reconcile_status="reconciled",
                reconcile_note="fake cancellation for protection guard check",
                reason="fake_cancel",
            )

        server.cancel_testnet_order = fake_cancel
        server.disarm_live_trading = fake_disarm
        server.raise_alert = fake_raise_alert
        server.insert_event = fake_insert_event

        guarded = server.handle_binance_protection_submit_failure(
            server.get_order(parent_id) or {},
            RuntimeError("stop/take-profit submit failed"),
            "live_guarded",
        )
        guard = guarded.get("guard") or {}
        if guard.get("status") != "entry_canceled":
            return fail("guard should mark successfully canceled entry as entry_canceled", guard)
        if guard.get("entry_cancel", {}).get("status") != "canceled":
            return fail("entry cancel did not record canceled status", guard)
        if child_id not in cancel_calls:
            return fail("submitted child protection order was not canceled after entry cancellation", guard)
        if not disarm_reasons or not disarm_reasons[0].startswith("protection_submit_failed:"):
            return fail("live trading was not disarmed after protection failure", guard)
        final_parent = server.get_order(parent_id) or {}
        if final_parent.get("status") != "live_canceled" or final_parent.get("reconcile_status") != "reconciled":
            return fail("final parent order was not left reconciled after safe cancel", final_parent)

        guarded_stuck = server.handle_binance_protection_submit_failure(
            server.get_order(stuck_parent_id) or {},
            RuntimeError("take-profit submit failed"),
            "live_guarded",
        )
        stuck_guard = guarded_stuck.get("guard") or {}
        if stuck_guard.get("status") != "needs_manual_reconcile":
            return fail("failed entry cancellation must require manual reconcile", stuck_guard)
        kept_children = stuck_guard.get("protection_cancel_attempts") or []
        if not kept_children or kept_children[0].get("status") != "kept_for_safety":
            return fail("child protection should be kept when entry cancellation is not confirmed", stuck_guard)
        stuck_parent = server.get_order(stuck_parent_id) or {}
        if stuck_parent.get("reconcile_status") != "needs_reconcile":
            return fail("stuck parent should remain needs_reconcile", stuck_parent)
        if not alerts or not events:
            return fail("guard did not emit alert and audit event evidence", {"alerts": alerts, "events": events})

        print(
            json.dumps(
                {
                    "ok": True,
                    "successful_guard": {
                        "status": guard.get("status"),
                        "entry_cancel": guard.get("entry_cancel", {}).get("status"),
                        "child_cancel_count": len(guard.get("protection_cancel_attempts") or []),
                    },
                    "stuck_guard": {
                        "status": stuck_guard.get("status"),
                        "entry_cancel": stuck_guard.get("entry_cancel", {}).get("status"),
                        "child_policy": kept_children[0].get("status"),
                    },
                    "disarm_count": len(disarm_reasons),
                    "alert_count": len(alerts),
                    "event_count": len(events),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    finally:
        server.cancel_testnet_order = original["cancel_testnet_order"]
        server.disarm_live_trading = original["disarm_live_trading"]
        server.raise_alert = original["raise_alert"]
        server.insert_event = original["insert_event"]
        cleanup(order_ids)


if __name__ == "__main__":
    raise SystemExit(main())
