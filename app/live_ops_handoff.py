from __future__ import annotations

from typing import Any


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _path_items(plan: dict[str, Any], runner: dict[str, Any], paths: dict[str, Any]) -> dict[str, Any]:
    evidence = dict(plan.get("evidence_paths") or {})
    summary = runner.get("last_summary") or {}
    evidence.update({key: value for key, value in (summary.get("evidence_paths") or {}).items() if value})
    evidence.update({key: value for key, value in paths.items() if value})
    return evidence


def _blocker_items(gate: dict[str, Any], final_prearm: dict[str, Any], final_armed: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for item in _as_list(gate.get("blocking_gates")):
        blockers.append(
            {
                "id": item.get("id"),
                "label": item.get("label") or item.get("id"),
                "status": item.get("status"),
                "detail": item.get("detail"),
                "source": "go_live_gate",
            }
        )
    for source, payload in (("final_prearm", final_prearm), ("final_armed", final_armed)):
        for index, failure in enumerate(_as_list(payload.get("failures"))):
            blockers.append(
                {
                    "id": f"{source}_{index + 1}",
                    "label": source,
                    "status": "fail",
                    "detail": str(failure),
                    "source": source,
                }
            )
    return blockers


def build_live_ops_handoff(evidence: dict[str, Any]) -> dict[str, Any]:
    gate = evidence.get("go_live_gate") or {}
    final_prearm = evidence.get("final_live_ready_prearm") or {}
    final_armed = evidence.get("final_live_ready_armed") or {}
    live_pilot = evidence.get("live_pilot") or {}
    plan = evidence.get("live_launch_plan") or {}
    runner = evidence.get("server_live_readiness") or {}
    ai_operator = evidence.get("ai_operator") or {}
    paths = evidence.get("paths") or {}
    blockers = _blocker_items(gate, final_prearm, final_armed)
    evidence_paths = _path_items(plan, runner, paths)
    ready = bool(gate.get("ready_for_live_order")) and bool(final_armed.get("ok"))
    prearm_ready = bool(gate.get("ready_to_arm_live")) and bool(final_prearm.get("ok"))
    symbol = str(evidence.get("symbol") or live_pilot.get("symbol") or "BTCUSDT").upper()
    runner_summary = runner.get("last_summary") or {}
    command_groups = [
        {
            "title": "服务器部署与基础验证",
            "commands": [
                "sudo bash deploy/setup-ubuntu-tailscale.sh",
                "sudo bash deploy/setup-ubuntu-time-sync.sh",
                "cp deploy/server.env.example .env",
                "bash deploy/deploy-server.sh",
                "bash deploy/verify-server.sh",
            ],
        },
        {
            "title": "无人值守准入推进",
            "commands": [
                "python3 scripts/run_server_live_readiness.py --run-testnet-drill --target-cycles 24 --interval-seconds 60",
                "python3 scripts/export_live_launch_plan.py",
                "python3 scripts/server_go_live_audit.py",
                "python3 scripts/export_server_bundle.py",
                "bash deploy/backup-server.sh",
            ],
        },
        {
            "title": "实盘前最终验证",
            "commands": [
                "TRADER_FINAL_LIVE_REQUIRE_ARMED=false python3 scripts/check_final_live_ready.py",
                "python3 scripts/check_go_live_gate.py",
                "python3 scripts/check_go_live_report.py",
                "python3 scripts/check_final_live_ready_api.py",
            ],
        },
        {
            "title": "受控首单",
            "commands": [
                "python3 scripts/run_guarded_live_pilot_once.py --plan-only",
                (
                    "python3 scripts/run_guarded_live_pilot_once.py --attest "
                    "--attestation-confirmation LIVE_ATTESTATION_CONFIRMED --arm "
                    "--arm-confirmation ARM_LIVE_TRADING --launch "
                    "--launch-confirmation LAUNCH_LIVE_PILOT"
                ),
                "python3 scripts/check_live_pilot_postflight.py",
            ],
        },
        {
            "title": "事故处理",
            "commands": [
                "/panic-stop --confirm PANIC_STOP",
                "/panic-stop --confirm PANIC_STOP --flatten --flatten-confirm FLATTEN_POSITIONS",
                "python3 scripts/check_panic_stop.py",
                "python3 scripts/check_exchange_emergency.py",
            ],
        },
    ]
    ai_commands = [
        "/readiness",
        "/server-readiness-run --testnet --cycles 24 --interval 60",
        "/env-audit live_guarded",
        "/launch-plan",
        "/handoff",
        "/final-live-ready --prearm",
        f"/live-pilot {symbol}",
        "/live-attest --confirm LIVE_ATTESTATION_CONFIRMED",
        "/live-arm --confirm ARM_LIVE_TRADING --ttl-minutes 10",
        f"/live-pilot-run {symbol} --confirm LAUNCH_LIVE_PILOT",
        f"/live-postflight {symbol}",
        "/panic-stop --confirm PANIC_STOP",
    ]
    handoff = {
        "ok": ready,
        "status": "ready_for_live_order" if ready else ("ready_to_arm" if prearm_ready else "blocked"),
        "generated_at": evidence.get("generated_at"),
        "symbol": symbol,
        "app_env": evidence.get("app_env"),
        "exchange_mode": evidence.get("exchange_mode"),
        "ready_to_enable_live": gate.get("ready_to_enable_live"),
        "ready_to_arm_live": gate.get("ready_to_arm_live"),
        "ready_for_live_order": gate.get("ready_for_live_order"),
        "final_prearm_ok": final_prearm.get("ok"),
        "final_armed_ok": final_armed.get("ok"),
        "live_pilot_status": live_pilot.get("status"),
        "live_pilot_can_launch": live_pilot.get("can_launch"),
        "server_runner": {
            "status": runner.get("status"),
            "running": runner.get("running"),
            "run_id": runner.get("run_id"),
            "last_report_path": runner.get("last_report_path"),
            "last_final_live_ready": runner_summary.get("final_live_ready"),
            "last_blocking_gates": runner_summary.get("blocking_gates"),
        },
        "ai_operator": {
            "enabled": ai_operator.get("enabled"),
            "ready": ai_operator.get("ready"),
            "provider": ai_operator.get("provider"),
            "allow_file_write": ai_operator.get("allow_file_write"),
            "allow_shell": ai_operator.get("allow_shell"),
            "apply_model_file_actions": ai_operator.get("apply_model_file_actions"),
        },
        "blockers": blockers[:40],
        "evidence_paths": evidence_paths,
        "command_groups": command_groups,
        "ai_commands": ai_commands,
        "safety_note": (
            "交接单只描述下一步操作，不会开启 live flags、不会写入 API secret、不会绕过 "
            "Go-live gate、短时武装、确认短语、确定性风控或 OMS。"
        ),
    }
    handoff["markdown"] = live_ops_handoff_markdown(handoff)
    return handoff


def live_ops_handoff_markdown(handoff: dict[str, Any]) -> str:
    lines = [
        "# Live Ops Handoff",
        "",
        f"- Generated: `{handoff.get('generated_at')}`",
        f"- Status: `{handoff.get('status')}`",
        f"- Symbol: `{handoff.get('symbol')}`",
        f"- App environment: `{handoff.get('app_env')}`",
        f"- Exchange mode: `{handoff.get('exchange_mode')}`",
        f"- Ready to enable live: `{handoff.get('ready_to_enable_live')}`",
        f"- Ready to arm live: `{handoff.get('ready_to_arm_live')}`",
        f"- Ready for live order: `{handoff.get('ready_for_live_order')}`",
        f"- Final pre-arm OK: `{handoff.get('final_prearm_ok')}`",
        f"- Final armed OK: `{handoff.get('final_armed_ok')}`",
        "",
        "## Current Blockers",
        "",
    ]
    blockers = handoff.get("blockers") or []
    if blockers:
        for item in blockers:
            lines.append(f"- `{item.get('source')}` {item.get('label')}: {item.get('detail')}")
    else:
        lines.append("- none")
    lines.extend(["", "## Evidence Paths", ""])
    for key, value in (handoff.get("evidence_paths") or {}).items():
        lines.append(f"- {key}: `{value or '-'}`")
    lines.extend(["", "## Command Runbook", ""])
    for group in handoff.get("command_groups") or []:
        lines.extend([f"### {group.get('title')}", ""])
        for command in group.get("commands") or []:
            lines.append(f"- `{command}`")
        lines.append("")
    lines.extend(["## AI Operator Commands", ""])
    for command in handoff.get("ai_commands") or []:
        lines.append(f"- `{command}`")
    lines.extend(["", "## Safety Note", "", str(handoff.get("safety_note") or "")])
    return "\n".join(lines).rstrip() + "\n"
