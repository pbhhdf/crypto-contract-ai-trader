from __future__ import annotations

import json
import sys
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
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
