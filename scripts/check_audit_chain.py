from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from app import server  # noqa: E402


def fail(message: str) -> int:
    print(f"FAILED: {message}", file=sys.stderr)
    return 1


def main() -> int:
    server.init_db()
    run_id = "AUDIT-SMOKE-RUN"
    server.insert_event(
        run_id,
        "system",
        "Audit Chain Check",
        "Audit chain smoke event",
        "Verifying tamper-evident audit chain.",
        {"smoke": True},
    )
    server.insert_order_transition(
        "AUDIT-SMOKE-ORDER",
        None,
        "prepared",
        "audit_chain_smoke",
        {"smoke": True},
    )
    server.insert_ai_operator_message(
        "assistant",
        "audit chain smoke message",
        actions=[{"action": "read", "path": "README.md"}],
        metadata={"smoke": True},
    )

    status = server.audit_chain_status(limit=10)
    if status.get("status") != "pass":
        return fail(f"audit chain is not passing: {status.get('broken_records')}")
    if int(status.get("broken_count") or 0) != 0:
        return fail(f"audit chain has broken records: {status.get('broken_count')}")
    if int(status.get("total_records") or 0) < 3:
        return fail("audit chain did not record smoke actions")
    streams = status.get("stream_counts") or {}
    for stream in ("event", "order_transition", "ai_operator"):
        if stream not in streams:
            return fail(f"audit chain is missing stream {stream}")
    if not status.get("last_hash") or status.get("last_hash") == "GENESIS":
        return fail("audit chain did not advance past genesis")

    print(
        json.dumps(
            {
                "ok": True,
                "total_records": status["total_records"],
                "broken_count": status["broken_count"],
                "last_hash": status["last_hash"],
                "stream_counts": streams,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
