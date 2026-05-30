from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def fail(message: str, payload: object | None = None) -> int:
    print(f"FAILED: {message}", file=sys.stderr)
    if payload is not None:
        print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
    return 1


def run_command(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=ROOT_DIR,
        text=True,
        capture_output=True,
        timeout=60,
    )


def parse_json_output(output: str) -> dict[str, object]:
    decoder = json.JSONDecoder()
    text = output.strip()
    while text:
        try:
            value, _ = decoder.raw_decode(text)
            return value if isinstance(value, dict) else {}
        except json.JSONDecodeError:
            text = text[text.find("{") + 1 :] if "{" in text[1:] else ""
            if text:
                text = "{" + text
    return {}


def main() -> int:
    plan = run_command([PYTHON, "scripts/run_guarded_live_pilot_once.py", "--plan-only"])
    if plan.returncode != 0:
        return fail("guarded live pilot plan-only run failed", {"stdout": plan.stdout, "stderr": plan.stderr})
    plan_payload = parse_json_output(plan.stdout)
    if plan_payload.get("ok") is not True or plan_payload.get("plan_only") is not True:
        return fail("guarded live pilot plan-only report is not ok", plan_payload)
    for key in ("initial_final_live_ready_prearm", "initial_final_live_ready_armed", "initial_live_pilot", "report_path"):
        if key not in plan_payload:
            return fail(f"guarded live pilot plan-only report missing {key}", plan_payload)

    rejected = run_command([
        PYTHON,
        "scripts/run_guarded_live_pilot_once.py",
        "--arm",
        "--arm-confirmation",
        "WRONG",
        "--ttl-seconds",
        "60",
    ])
    if rejected.returncode == 0:
        return fail("guarded live pilot accepted a wrong arming confirmation", rejected.stdout)
    rejected_payload = parse_json_output(rejected.stderr or rejected.stdout)
    if "ARM_LIVE_TRADING" not in json.dumps(rejected_payload, ensure_ascii=False):
        return fail("wrong arming confirmation report did not explain ARM_LIVE_TRADING", rejected_payload)

    print(json.dumps({
        "ok": True,
        "plan_report_path": plan_payload.get("report_path"),
        "wrong_arm_rejected": True,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
