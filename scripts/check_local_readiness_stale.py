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


def main() -> int:
    active_path = ROOT_DIR / "reports" / "local-readiness-active.json"
    original = active_path.read_text(encoding="utf-8") if active_path.exists() else None
    old_time = (datetime.now(timezone.utc) - timedelta(seconds=server.LOCAL_READINESS_STALE_SECONDS + 60)).isoformat(
        timespec="seconds"
    )
    synthetic = {
        "ok": False,
        "status": "running",
        "started_at": old_time,
        "updated_at": old_time,
        "project_root": str(ROOT_DIR),
        "base_url": "http://127.0.0.1:8787",
        "current_step": {"name": "scheduler", "status": "done", "updated_at": old_time},
        "completed_step_count": 1,
        "failed_steps": [],
        "final_report_path": str(ROOT_DIR / "reports" / "local-readiness-synthetic.json"),
        "steps": [
            {
                "name": "scheduler",
                "ok": True,
                "returncode": 0,
                "duration_seconds": 1.2,
                "command": ["py", "scripts/check_scheduler.py"],
                "stdout": "",
                "stderr": "",
                "timed_out": False,
            }
        ],
        "readiness": None,
    }

    try:
        write_json(active_path, synthetic)
        status = server.local_readiness_report_status(limit=3)
        if status.get("status") != "interrupted":
            return fail("stale active local readiness report was not marked interrupted", status)
        if status.get("ok") is not False or status.get("interrupted") is not True or status.get("stale") is not True:
            return fail("interrupted local readiness report did not expose failure flags", status)
        if (status.get("current_step") or {}).get("status") != "interrupted":
            return fail("interrupted local readiness report did not mark the current step interrupted", status)
        if not status.get("interrupted_reason") or "本地验收进度" not in str(status.get("interrupted_reason")):
            return fail("interrupted local readiness report did not explain the stale runner", status)
        if not status.get("last_steps") or status["last_steps"][0].get("name") != "scheduler":
            return fail("interrupted local readiness report lost completed step evidence", status)

        print(
            json.dumps(
                {
                    "ok": True,
                    "status": status.get("status"),
                    "interrupted_step": status.get("interrupted_step"),
                    "stale_seconds": status.get("stale_seconds"),
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
