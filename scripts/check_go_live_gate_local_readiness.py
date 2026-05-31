from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
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


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def synthetic_report(*, status: str, ok: bool, updated_at: str, readiness_overall: str = "warn") -> dict[str, Any]:
    return {
        "ok": ok,
        "status": status,
        "started_at": updated_at,
        "updated_at": updated_at,
        "project_root": str(ROOT_DIR),
        "base_url": "http://127.0.0.1:8787",
        "current_step": {"name": "completed" if status == "completed" else "compile", "status": status},
        "completed_step_count": 3,
        "failed_steps": [] if ok else ["compile"],
        "final_report_path": str(ROOT_DIR / "reports" / "local-readiness-synthetic.json"),
        "steps": [
            {
                "name": "compile",
                "ok": ok,
                "returncode": 0 if ok else 1,
                "duration_seconds": 1.0,
                "command": ["py", "-m", "py_compile", "app/server.py"],
                "stdout": "",
                "stderr": "",
                "timed_out": False,
            }
        ],
        "readiness": {"overall": readiness_overall},
    }


def local_gate(gate: dict[str, Any]) -> dict[str, Any]:
    for item in gate.get("gates") or []:
        if item.get("id") == "local_readiness":
            return item
    return {}


def main() -> int:
    active_path = ROOT_DIR / "reports" / "local-readiness-active.json"
    original = active_path.read_text(encoding="utf-8") if active_path.exists() else None
    fresh = datetime.now(timezone.utc).isoformat(timespec="seconds")
    old = (
        datetime.now(timezone.utc)
        - timedelta(hours=server.GO_LIVE_LOCAL_READINESS_MAX_AGE_HOURS + 1)
    ).isoformat(timespec="seconds")
    stale_running = (
        datetime.now(timezone.utc)
        - timedelta(seconds=server.LOCAL_READINESS_STALE_SECONDS + 60)
    ).isoformat(timespec="seconds")

    try:
        write_json(active_path, synthetic_report(status="completed", ok=True, updated_at=fresh))
        fresh_gate = local_gate(server.go_live_gate_status())
        if fresh_gate.get("status") != "pass" or fresh_gate.get("blocks_live_order"):
            return fail("fresh successful local readiness should pass the go-live gate", fresh_gate)

        write_json(active_path, synthetic_report(status="completed", ok=True, updated_at=old))
        expired_gate = local_gate(server.go_live_gate_status())
        if expired_gate.get("status") == "pass" or not expired_gate.get("blocks_live_order"):
            return fail("expired local readiness should block the go-live gate", expired_gate)

        write_json(active_path, synthetic_report(status="completed", ok=False, updated_at=fresh, readiness_overall="fail"))
        failed_gate = local_gate(server.go_live_gate_status())
        if failed_gate.get("status") == "pass" or not failed_gate.get("blocks_live_order"):
            return fail("failed local readiness should block the go-live gate", failed_gate)

        write_json(active_path, synthetic_report(status="running", ok=False, updated_at=stale_running))
        interrupted_gate = local_gate(server.go_live_gate_status())
        if interrupted_gate.get("status") == "pass" or not interrupted_gate.get("blocks_live_order"):
            return fail("interrupted local readiness should block the go-live gate", interrupted_gate)
        if "中断" not in str(interrupted_gate.get("detail") or "") and "验收进度" not in str(interrupted_gate.get("detail") or ""):
            return fail("interrupted local readiness gate should explain the stale report", interrupted_gate)

        print(
            json.dumps(
                {
                    "ok": True,
                    "fresh_status": fresh_gate.get("status"),
                    "expired_status": expired_gate.get("status"),
                    "failed_status": failed_gate.get("status"),
                    "interrupted_status": interrupted_gate.get("status"),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    finally:
        if original is None:
            try:
                active_path.unlink()
            except FileNotFoundError:
                pass
        else:
            active_path.write_text(original, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
