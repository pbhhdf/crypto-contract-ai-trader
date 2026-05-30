from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.live_ops_handoff import build_live_ops_handoff  # noqa: E402


def fail(message: str, payload: object | None = None) -> int:
    print(f"FAILED: {message}", file=sys.stderr)
    if payload is not None:
        print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
    return 1


def main() -> int:
    evidence = {
        "generated_at": "2026-05-30T00:00:00+00:00",
        "symbol": "BTCUSDT",
        "app_env": "server",
        "exchange_mode": "live_guarded",
        "go_live_gate": {
            "status": "ready",
            "ready_to_enable_live": True,
            "ready_to_arm_live": True,
            "ready_for_live_order": True,
            "blocking_gates": [],
        },
        "final_live_ready_prearm": {"ok": True, "failures": []},
        "final_live_ready_armed": {"ok": True, "failures": []},
        "live_pilot": {"status": "ready", "can_launch": True, "symbol": "BTCUSDT"},
        "live_launch_plan": {
            "evidence_paths": {
                "latest_go_live_report": "reports/go-live-report-example.json",
                "latest_live_launch_plan_md": "reports/live-launch-plan-example.md",
            }
        },
        "server_live_readiness": {
            "status": "completed",
            "running": False,
            "run_id": "SLR-EXAMPLE",
            "last_report_path": "reports/server-live-readiness-runner-example.json",
            "last_summary": {
                "final_live_ready": True,
                "evidence_paths": {
                    "server_bundle": "reports/server-bundles/example.zip",
                    "state_backup": "reports/backups/example.zip",
                },
            },
        },
        "ai_operator": {
            "enabled": True,
            "ready": True,
            "provider": "codex",
            "allow_file_write": True,
            "allow_shell": True,
            "apply_model_file_actions": True,
        },
        "paths": {"latest_server_go_live_audit_md": "reports/server-go-live-audit-example.md"},
    }
    handoff = build_live_ops_handoff(evidence)
    if handoff.get("status") != "ready_for_live_order" or not handoff.get("ok"):
        return fail("known-good evidence did not produce a ready handoff", handoff)
    markdown = str(handoff.get("markdown") or "")
    required_markers = {
        "run_guarded_live_pilot_once.py",
        "LIVE_ATTESTATION_CONFIRMED",
        "ARM_LIVE_TRADING",
        "LAUNCH_LIVE_PILOT",
        "PANIC_STOP",
        "FLATTEN_POSITIONS",
        "/handoff",
    }
    missing = sorted(marker for marker in required_markers if marker not in markdown)
    if missing:
        return fail("handoff markdown is missing required live markers", {"missing": missing, "markdown": markdown})

    blocked = dict(evidence)
    blocked["go_live_gate"] = {
        "status": "blocked",
        "ready_to_enable_live": False,
        "ready_to_arm_live": False,
        "ready_for_live_order": False,
        "blocking_gates": [
            {
                "id": "testnet_drill_cycles",
                "label": "Testnet drill cycles",
                "status": "fail",
                "detail": "Need real Testnet cycles.",
            }
        ],
    }
    blocked["final_live_ready_armed"] = {"ok": False, "failures": ["ARM_LIVE_TRADING is not active."]}
    blocked_handoff = build_live_ops_handoff(blocked)
    if blocked_handoff.get("ok") or not blocked_handoff.get("blockers"):
        return fail("blocked evidence did not produce a blocked handoff", blocked_handoff)

    print(
        json.dumps(
            {
                "ok": True,
                "ready_status": handoff.get("status"),
                "blocked_status": blocked_handoff.get("status"),
                "command_group_count": len(handoff.get("command_groups") or []),
                "ai_command_count": len(handoff.get("ai_commands") or []),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
