from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.live_launch_plan import build_live_launch_plan  # noqa: E402


def fail(message: str, payload: dict | None = None) -> int:
    print(f"FAILED: {message}", file=sys.stderr)
    if payload is not None:
        print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
    return 1


def main() -> int:
    evidence = {
        "app_env": "server",
        "exchange_mode": "live_guarded",
        "readiness": {"overall": "pass"},
        "live_env_profile": {
            "status": "pass",
            "failed_checks": [],
            "safe_env_snapshot": {
                "APP_ENV": "server",
                "BINANCE_LIVE_API_SECRET": "[SET:sha256:abcdef123456]",
            },
            "secret_fingerprints": {"BINANCE_LIVE_API_SECRET": "sha256:abcdef123456"},
        },
        "go_live_gate": {
            "status": "ready",
            "ready_to_enable_live": True,
            "ready_to_arm_live": True,
            "ready_for_live_order": True,
            "blocking_gates": [],
        },
        "final_live_ready_prearm": {"ok": True, "failures": []},
        "final_live_ready_armed": {"ok": True, "failures": []},
        "go_live_report": {
            "verdict": {
                "status": "ready",
                "ready_for_live_order": True,
                "blocking_gate_ids": [],
            }
        },
        "server_live_readiness": {"status": "completed"},
        "ai_operator": {
            "ready": True,
            "allow_file_write": True,
            "allow_shell": True,
        },
        "paths": {
            "latest_go_live_report": "reports/go-live-report-example.json",
            "latest_server_go_live_audit": "reports/server-go-live-audit-example.json",
            "latest_server_bundle": "reports/server-bundles/example.zip",
        },
    }
    plan = build_live_launch_plan(evidence)
    if not plan.get("ok") or plan.get("status") != "ready_for_live_order":
        return fail("known-good evidence did not produce a ready plan", plan)
    if len(plan.get("stages") or []) < 5:
        return fail("live launch plan is missing expected stages", plan)
    markdown = str(plan.get("markdown") or "")
    for phrase in (
        "MVP 服务器",
        "Binance Testnet",
        "实盘保护模式",
        "ARM_LIVE_TRADING",
        "run_guarded_live_pilot_once.py",
        "LAUNCH_LIVE_PILOT",
        "guarded-live-pilot",
    ):
        if phrase not in markdown:
            return fail(f"live launch markdown missing {phrase!r}", plan)
    serialized = json.dumps(plan, ensure_ascii=False)
    if "live-secret-value" in serialized or "testnet-secret-value" in serialized:
        return fail("live launch plan leaked raw secret-like values", plan)

    blocked = dict(evidence)
    blocked["go_live_gate"] = {
        "status": "blocked",
        "ready_for_live_order": False,
        "blocking_gates": [
            {
                "id": "testnet_drill_cycles",
                "label": "Testnet 演练周期",
                "status": "fail",
                "detail": "仍需真实 Testnet 演练周期。",
                "blocks_live_order": True,
            }
        ],
    }
    blocked_plan = build_live_launch_plan(blocked)
    if blocked_plan.get("ok") or not blocked_plan.get("blockers"):
        return fail("blocked evidence did not produce blockers", blocked_plan)

    print(
        json.dumps(
            {
                "ok": True,
                "ready_status": plan.get("status"),
                "stage_count": len(plan.get("stages") or []),
                "blocked_status": blocked_plan.get("status"),
                "blocked_count": len(blocked_plan.get("blockers") or []),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
