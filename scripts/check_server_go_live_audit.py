from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def fail(message: str, payload: object | None = None) -> int:
    print(f"FAILED: {message}", file=sys.stderr)
    if payload is not None:
        print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
    return 1


def main() -> int:
    completed = subprocess.run(
        [sys.executable, "scripts/server_go_live_audit.py"],
        cwd=ROOT_DIR,
        text=True,
        capture_output=True,
        timeout=120,
    )
    if completed.returncode != 0:
        return fail(
            "server_go_live_audit.py exited non-zero",
            {"stdout": completed.stdout, "stderr": completed.stderr, "returncode": completed.returncode},
        )
    try:
        summary = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        return fail(f"server_go_live_audit.py did not print JSON: {exc}", completed.stdout)
    json_path = Path(summary.get("json_path") or "")
    markdown_path = Path(summary.get("markdown_path") or "")
    if not json_path.exists() or not markdown_path.exists():
        return fail("audit files were not written", summary)
    audit = json.loads(json_path.read_text(encoding="utf-8"))
    for key in (
        "health",
        "readiness",
        "go_live_gate",
        "final_live_ready_prearm",
        "final_live_ready_armed",
        "ai_operator",
        "go_live_report",
    ):
        if key not in audit:
            return fail(f"audit missing {key}", audit)
    if "Server Go-Live Audit" not in markdown_path.read_text(encoding="utf-8"):
        return fail("markdown audit title missing", str(markdown_path))
    print(json.dumps({"ok": True, "json_path": str(json_path), "markdown_path": str(markdown_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
