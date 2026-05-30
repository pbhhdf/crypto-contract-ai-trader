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
        [
            sys.executable,
            "scripts/run_server_live_readiness.py",
            "--dry-run",
            "--run-testnet-drill",
            "--target-cycles",
            "2",
            "--interval-seconds",
            "1",
        ],
        cwd=ROOT_DIR,
        text=True,
        capture_output=True,
        timeout=30,
    )
    if completed.returncode != 0:
        return fail("server live readiness runner dry-run failed", {"stdout": completed.stdout, "stderr": completed.stderr})
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        return fail(f"runner did not print JSON: {exc}", completed.stdout)
    report_path = Path(payload.get("report_path", ""))
    if not report_path.exists():
        return fail("runner did not write a report", payload)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    step_names = [step.get("name") for step in report.get("steps") or []]
    required = {
        "preflight",
        "server_deploy_profile",
        "binance_time_drift",
        "all_checks",
        "strategy_quality_sweep",
        "testnet_drill_until_ready",
        "go_live_report",
        "server_go_live_audit",
        "export_live_launch_plan",
        "export_live_ops_handoff",
        "export_server_bundle",
        "export_live_env_pack",
        "export_live_launch_kit",
        "backup_state",
        "final_live_ready_api",
    }
    missing = sorted(required - set(step_names))
    if missing:
        return fail("runner plan is missing required steps", {"missing": missing, "step_names": step_names})
    if not report.get("dry_run"):
        return fail("runner smoke should be a dry-run", report)
    evidence_paths = report.get("evidence_paths")
    if not isinstance(evidence_paths, dict):
        return fail("runner report does not expose evidence_paths", report)
    print(
        json.dumps(
            {
                "ok": True,
                "step_count": len(step_names),
                "evidence_path_keys": sorted(evidence_paths),
                "report_path": str(report_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
