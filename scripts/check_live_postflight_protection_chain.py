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
    run_id: str,
    status: str,
    parent_order_id: str | None = None,
    protection_kind: str | None = None,
    reconcile_status: str = "reconciled",
) -> dict[str, Any]:
    now = server.utc_now()
    return {
        "id": order_id,
        "run_id": run_id,
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
        "reconcile_status": reconcile_status,
        "reconcile_note": "synthetic live protection chain check",
        "last_reconciled_at": now if reconcile_status == "reconciled" else None,
        "created_at": now,
        "updated_at": now,
        "parent_order_id": parent_order_id,
        "protection_kind": protection_kind,
    }


def cleanup(order_ids: list[str], run_ids: list[str]) -> None:
    with server.DB_LOCK, server.connect() as conn:
        if order_ids:
            placeholders = ", ".join("?" for _ in order_ids)
            conn.execute(f"DELETE FROM order_transitions WHERE order_id IN ({placeholders})", order_ids)
            conn.execute(f"DELETE FROM orders WHERE id IN ({placeholders})", order_ids)
        if run_ids:
            placeholders = ", ".join("?" for _ in run_ids)
            conn.execute(f"DELETE FROM runs WHERE id IN ({placeholders})", run_ids)
        conn.commit()


def main() -> int:
    server.init_db()
    suffix = str(uuid.uuid4())[:8].upper()
    parent_id = f"LIVE-CHAIN-{suffix}"
    stop_id = f"LIVE-CHAIN-SL-{suffix}"
    take_id = f"LIVE-CHAIN-TP-{suffix}"
    orphan_id = f"LIVE-CHAIN-ORPHAN-{suffix}"
    order_ids = [parent_id, stop_id, take_id, orphan_id]
    run = server.create_run("BTCUSDT", "live_guarded")
    run_id = str(run.get("id") or "")
    if not run_id:
        return fail("could not create synthetic live run", run)

    try:
        missing_run = server.live_pilot_protection_chain_status("BTCUSDT", f"missing-{suffix}")
        if missing_run.get("status") != "warn" or missing_run.get("parent_order_id"):
            return fail("missing live run should return a warning without a parent order", missing_run)

        server.persist_order(make_order(parent_id, run_id, "live_submitted"))
        server.persist_order(make_order(stop_id, run_id, "live_protection_submitted", parent_id, "stop_loss"))
        missing_take = server.live_pilot_protection_chain_status("BTCUSDT", run_id)
        if missing_take.get("status") != "fail" or "take_profit" not in (missing_take.get("missing_kinds") or []):
            return fail("missing take-profit protection should fail the chain", missing_take)

        server.persist_order(make_order(take_id, run_id, "live_protection_submitted", parent_id, "take_profit"))
        complete_chain = server.live_pilot_protection_chain_status("BTCUSDT", run_id)
        if complete_chain.get("status") != "pass" or complete_chain.get("child_count") != 2:
            return fail("complete stop-loss/take-profit chain should pass", complete_chain)

        server.persist_order(
            make_order(
                orphan_id,
                run_id,
                "live_protection_submitted",
                f"LIVE-MISSING-PARENT-{suffix}",
                "stop_loss",
            )
        )
        orphan_chain = server.live_pilot_protection_chain_status("BTCUSDT", run_id)
        if orphan_chain.get("status") != "fail" or orphan_chain.get("orphan_child_count") != 1:
            return fail("orphan live protection child should fail the chain", orphan_chain)

        print(
            json.dumps(
                {
                    "ok": True,
                    "run_id": run_id,
                    "missing_run_status": missing_run.get("status"),
                    "missing_take_status": missing_take.get("status"),
                    "complete_chain_status": complete_chain.get("status"),
                    "orphan_chain_status": orphan_chain.get("status"),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    finally:
        cleanup(order_ids, [run_id])


if __name__ == "__main__":
    raise SystemExit(main())
