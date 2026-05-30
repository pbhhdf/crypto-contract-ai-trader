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
            "scripts/run_strategy_quality_sweep.py",
            "--dry-run",
            "--symbols",
            "BTCUSDT,ETHUSDT",
            "--intervals",
            "15m,1h",
            "--max-candidates",
            "3",
            "--report-prefix",
            "strategy-quality-sweep-smoke",
        ],
        cwd=ROOT_DIR,
        text=True,
        capture_output=True,
        timeout=30,
    )
    if completed.returncode != 0:
        return fail("strategy quality sweep dry-run failed", {"stdout": completed.stdout, "stderr": completed.stderr})
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        return fail(f"strategy quality sweep did not print JSON: {exc}", completed.stdout)
    report_path = Path(payload.get("report_path", ""))
    if not report_path.exists():
        return fail("strategy quality sweep report was not written", payload)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("candidate_count") != 3:
        return fail("strategy quality sweep did not honor max-candidates", report)
    if not report.get("dry_run"):
        return fail("strategy quality sweep smoke must not call walk-forward endpoints", report)
    if not {"min_folds", "min_total_return_pct", "min_positive_fold_rate_pct", "max_fold_drawdown_pct"} <= set(
        report.get("thresholds") or {}
    ):
        return fail("strategy quality sweep report is missing thresholds", report)
    print(
        json.dumps(
            {
                "ok": True,
                "candidate_count": report.get("candidate_count"),
                "dry_run": report.get("dry_run"),
                "report_path": str(report_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
