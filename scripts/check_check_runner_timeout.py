from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from scripts import run_all_checks, run_server_live_readiness  # noqa: E402


def fail(message: str, payload: object | None = None) -> int:
    print(f"FAILED: {message}", file=sys.stderr)
    if payload is not None:
        print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
    return 1


def assert_timeout_step(step: dict[str, Any], label: str) -> int | None:
    if step.get("ok"):
        return fail(f"{label} timeout step unexpectedly passed", step)
    if step.get("timed_out") is not True:
        return fail(f"{label} did not expose timed_out=true", step)
    if "Timed out after 1s" not in str(step.get("stderr") or ""):
        return fail(f"{label} did not preserve timeout reason", step)
    return None


def main() -> int:
    observed_progress: list[tuple[str, str]] = []
    previous_writer = run_all_checks.ACTIVE_REPORT_WRITER
    run_all_checks.ACTIVE_REPORT_WRITER = lambda name, status: observed_progress.append((name, status))
    try:
        success_step = run_all_checks.run_step(
            "success_smoke",
            [sys.executable, "-c", "print('runner-ok')"],
            timeout=5,
        )
    finally:
        run_all_checks.ACTIVE_REPORT_WRITER = previous_writer
    if not success_step.get("ok"):
        return fail("run_all_checks success smoke failed", success_step)
    if ("success_smoke", "running") not in observed_progress or ("success_smoke", "done") not in observed_progress:
        return fail("run_all_checks did not emit active report progress callbacks", observed_progress)
    report = run_all_checks.build_readiness_report(
        status="running",
        started_at="2026-01-01T00:00:00+00:00",
        steps=[success_step],
        current_step={"name": "success_smoke", "status": "done"},
    )
    if report.get("completed_step_count") != 1 or report.get("current_step", {}).get("name") != "success_smoke":
        return fail("incremental report payload is missing progress metadata", report)
    with tempfile.TemporaryDirectory() as tmp_dir:
        report_path = Path(tmp_dir) / "local-readiness-active.json"
        run_all_checks.write_json_atomic(report_path, report)
        loaded = json.loads(report_path.read_text(encoding="utf-8"))
    if loaded.get("status") != "running" or loaded.get("completed_step_count") != 1:
        return fail("incremental report did not round-trip through atomic writer", loaded)

    command = [sys.executable, "-c", "import time; time.sleep(30)"]
    all_checks_step = run_all_checks.run_step("timeout_smoke", command, timeout=1)
    failed = assert_timeout_step(all_checks_step, "run_all_checks")
    if failed is not None:
        return failed

    readiness_step = run_server_live_readiness.run_step("timeout_smoke", command, timeout=1)
    failed = assert_timeout_step(readiness_step, "run_server_live_readiness")
    if failed is not None:
        return failed

    print(
        json.dumps(
            {
                "ok": True,
                "all_checks_returncode": all_checks_step.get("returncode"),
                "readiness_returncode": readiness_step.get("returncode"),
                "progress_events": observed_progress,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
