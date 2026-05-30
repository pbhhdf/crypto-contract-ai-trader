from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def fail(message: str) -> int:
    print(f"FAILED: {message}", file=sys.stderr)
    return 1


def main() -> int:
    command = [
        sys.executable,
        "scripts/run_testnet_drill_until_ready.py",
        "--dry-run",
        "--target-kind",
        "dry_run",
        "--max-cycles",
        "1",
        "--interval-seconds",
        "0",
    ]
    completed = subprocess.run(
        command,
        cwd=ROOT_DIR,
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )
    if completed.returncode != 0:
        return fail((completed.stderr or completed.stdout or "runner exited non-zero").strip())

    decoder = json.JSONDecoder()
    payload = None
    for index, char in enumerate(completed.stdout):
        if char != "{":
            continue
        try:
            candidate, end = decoder.raw_decode(completed.stdout[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict) and "report_path" in candidate and "final_status" in candidate:
            payload = candidate
            break
    if not payload:
        return fail("runner did not print a final JSON report")
    if not payload.get("ok"):
        return fail(f"runner report was not ok: {payload}")
    if not payload.get("dry_run"):
        return fail("runner check must use dry_run")
    if payload.get("target_kind") != "dry_run":
        return fail("runner did not target dry_run counter")
    if not Path(payload.get("report_path", "")).exists():
        return fail("runner report path does not exist")

    summary = {
        "ok": True,
        "report_path": payload.get("report_path"),
        "attempted_cycles": payload.get("attempted_cycles"),
        "final_counter": payload.get("final_counter"),
        "target_cycles": payload.get("target_cycles"),
        "blocking_gates": (payload.get("go_live_gate") or {}).get("blocking_gates") or [],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
