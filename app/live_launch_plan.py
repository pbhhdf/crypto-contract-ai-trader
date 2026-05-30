from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def compact_gate(gate_payload: dict[str, Any]) -> dict[str, Any]:
    gate = gate_payload.get("go_live_gate") if isinstance(gate_payload.get("go_live_gate"), dict) else gate_payload
    blockers = gate.get("blocking_gates") or []
    return {
        "status": gate.get("status"),
        "ready_to_enable_live": gate.get("ready_to_enable_live"),
        "ready_to_arm_live": gate.get("ready_to_arm_live"),
        "ready_for_live_order": gate.get("ready_for_live_order"),
        "blocking_count": len(blockers),
        "blocking_gates": [
            {
                "id": item.get("id"),
                "label": item.get("label"),
                "status": item.get("status"),
                "detail": item.get("detail"),
                "blocks_live_order": item.get("blocks_live_order"),
            }
            for item in blockers
        ],
    }


def stage_status(required_done: bool, blockers: list[Any]) -> str:
    if required_done and not blockers:
        return "pass"
    if blockers:
        return "fail"
    return "warn"


def evidence_path(paths: dict[str, str], key: str) -> str:
    return paths.get(key) or ""


def build_actions() -> list[dict[str, Any]]:
    return [
        {
            "stage": "mvp_server",
            "title": "部署 MVP 服务器",
            "goal": "让中文控制台、纸交易、风控、OMS、回测、调度、AI/Codex 操作员在 Ubuntu 私有网络中稳定运行。",
            "commands": [
                "bash deploy/setup-ubuntu-tailscale.sh",
                "bash deploy/setup-ubuntu-time-sync.sh",
                "cp deploy/server.env.example .env",
                "python3 scripts/live_env_profile.py --env-file .env --target mvp_server --strict",
                "bash deploy/deploy-server.sh",
            ],
            "env_changes": [
                "APP_ENV=server",
                "APP_HOST=0.0.0.0",
                "TRADER_BIND_IP=<tailscale-ipv4>",
                "APP_BASIC_AUTH_USER=<choose-user>",
                "APP_BASIC_AUTH_PASSWORD=<long-random-password>",
                "AI_PROVIDER=rules",
                "EXCHANGE_MODE=paper",
                "ENABLE_BINANCE_LIVE=false",
                "BINANCE_PLACE_LIVE_ORDERS=false",
            ],
            "proof": [
                "GET /api/health 返回 ok=true。",
                "中文 UI 可通过 Tailscale IP + Basic Auth 打开。",
                "python3 scripts/run_all_checks.py 无失败步骤。",
            ],
        },
        {
            "stage": "testnet_validate",
            "title": "Binance Testnet 签名验证",
            "goal": "只调用 Binance USD-M Futures Testnet `/fapi/v1/order/test`，确认签名、时间、风控和 OMS 流程，不产生真实 Testnet 挂单。",
            "commands": [
                "python3 scripts/live_env_profile.py --env-file .env --target testnet_validate --strict",
                "TRADER_CHECK_TESTNET=true python3 scripts/run_all_checks.py",
                "python3 scripts/run_testnet_drill_until_ready.py --mode binance_testnet_validate --target-cycles 24 --interval-seconds 60",
            ],
            "env_changes": [
                "ENABLE_BINANCE_TESTNET=true",
                "BINANCE_API_KEY=<binance-futures-testnet-key>",
                "BINANCE_API_SECRET=<binance-futures-testnet-secret>",
                "EXCHANGE_MODE=binance_testnet_validate",
                "BINANCE_PLACE_TESTNET_ORDERS=false",
            ],
            "proof": [
                "readiness 中 testnet key ready。",
                "Testnet drill real_completed_cycles 达到 go-live gate 要求。",
                "OMS 状态显示已验证，无真实订单。",
            ],
        },
        {
            "stage": "testnet_place",
            "title": "真实 Testnet 下单演练",
            "goal": "在 Binance Testnet 小额提交并撤销/对账测试订单，验证真实订单状态机、幂等、杠杆/保证金同步和恢复路径。",
            "commands": [
                "python3 scripts/live_env_profile.py --env-file .env --target testnet_place --strict",
                "TRADER_CHECK_TESTNET_PLACE=true python3 scripts/run_all_checks.py",
                "python3 scripts/run_server_live_readiness.py --run-testnet-drill --target-cycles 24 --interval-seconds 60",
            ],
            "env_changes": [
                "EXCHANGE_MODE=binance_testnet_place_order",
                "BINANCE_PLACE_TESTNET_ORDERS=true",
                "BINANCE_SYNC_MARGIN_TYPE_BEFORE_ORDER=true",
                "BINANCE_TARGET_MARGIN_TYPE=ISOLATED",
                "BINANCE_SYNC_LEVERAGE_BEFORE_ORDER=true",
            ],
            "proof": [
                "无重复订单。",
                "OMS reconcile 后无未知状态订单。",
                "exchange recovery 能恢复本地状态。",
            ],
        },
        {
            "stage": "live_guarded_prearm",
            "title": "实盘保护模式预武装",
            "goal": "只让系统进入 guarded live 配置和最终检查，不打开短时真实下单窗口。",
            "commands": [
                "python3 scripts/live_env_profile.py --env-file .env --target live_guarded --strict",
                "TRADER_ALLOW_LIVE_DEPLOY=true bash deploy/deploy-server.sh",
                "TRADER_FINAL_LIVE_REQUIRE_ARMED=false python3 scripts/check_final_live_ready.py",
                "python3 scripts/export_go_live_report.py",
                "python3 scripts/server_go_live_audit.py",
                "bash deploy/backup-server.sh",
            ],
            "env_changes": [
                "EXCHANGE_MODE=live_guarded",
                "ENABLE_BINANCE_LIVE=true",
                "BINANCE_PLACE_LIVE_ORDERS=true",
                "BINANCE_LIVE_API_KEY=<binance-live-key-without-withdrawal>",
                "BINANCE_LIVE_API_SECRET=<binance-live-secret>",
                "LIVE_TRADING_CONFIRMATION=I_UNDERSTAND_LIVE_RISK",
                "MAX_ORDER_NOTIONAL_USDT=<small-pilot-order-cap>",
                "LIVE_PILOT_MAX_WALLET_USDT=<small-pilot-wallet-cap>",
                "至少启用 Webhook、Telegram 或 Email 一个外部告警通道。",
            ],
            "proof": [
                "final live pre-arm check 通过，且 armed check 只剩短时武装窗口阻塞。",
                "实盘 API 已禁用提现并绑定服务器出口 IP。",
                "最新备份和审计包已复制到服务器外部。",
            ],
        },
        {
            "stage": "live_arm_window",
            "title": "短时小额实盘窗口",
            "goal": "只在所有门禁通过后，短时武装一次，允许极小额首单验证真实交易链路。",
            "commands": [
                "在 UI 保存 LIVE_ATTESTATION_CONFIRMED 人工证据。",
                "在 UI 输入 ARM_LIVE_TRADING 并设置短 TTL。",
                "python3 scripts/check_final_live_ready.py",
                "python3 scripts/run_guarded_live_pilot_once.py --plan-only",
                "python3 scripts/run_guarded_live_pilot_once.py --attest --attestation-confirmation LIVE_ATTESTATION_CONFIRMED --arm --arm-confirmation ARM_LIVE_TRADING --launch --launch-confirmation LAUNCH_LIVE_PILOT",
                "python3 scripts/check_live_pilot_postflight.py",
                "python3 scripts/check_guarded_live_pilot_runner.py",
                "仅执行一笔小额 live_guarded 订单，然后立即复核 OMS、仓位、告警和审计链。",
            ],
            "env_changes": [
                "LIVE_ARMING_MAX_ORDERS=1",
                "LIVE_ARMING_MAX_SECONDS<=900",
            ],
            "proof": [
                "ready_for_live_order=true。",
                "首单后 OMS 对账通过。",
                "首单 postflight 检查已覆盖 OMS、告警、审计链、交易所快照和解除武装状态。",
                "guarded-live-pilot 报告已记录 plan、武装、首单、OMS 对账和解除武装结果。",
                "可随时使用紧急停止并取消开放订单。",
            ],
        },
    ]


def collect_blockers(
    env_profile: dict[str, Any],
    gate: dict[str, Any],
    final_prearm: dict[str, Any],
    final_armed: dict[str, Any],
) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for item in env_profile.get("failed_checks") or []:
        blockers.append(
            {
                "source": "live_env_profile",
                "id": item.get("id"),
                "label": item.get("label"),
                "detail": item.get("detail"),
                "env_vars": item.get("env_vars") or [],
            }
        )
    for item in gate.get("blocking_gates") or []:
        blockers.append(
            {
                "source": "go_live_gate",
                "id": item.get("id"),
                "label": item.get("label"),
                "detail": item.get("detail"),
                "env_vars": [],
            }
        )
    for failure in final_prearm.get("failures") or []:
        blockers.append(
            {
                "source": "final_live_ready_prearm",
                "id": "final_prearm_failure",
                "label": "最终预武装检查",
                "detail": failure,
                "env_vars": [],
            }
        )
    if final_armed.get("failures"):
        blockers.append(
            {
                "source": "final_live_ready_armed",
                "id": "armed_window",
                "label": "短时武装窗口",
                "detail": "仍需要 ARM_LIVE_TRADING 短时授权或其余 armed-window 条件。",
                "env_vars": ["LIVE_ARMING_MAX_SECONDS", "LIVE_ARMING_MAX_ORDERS"],
            }
        )
    unique: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in blockers:
        key = (str(item.get("source")), str(item.get("id")), str(item.get("detail")))
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def build_live_launch_plan(evidence: dict[str, Any]) -> dict[str, Any]:
    env_profile = evidence.get("live_env_profile") or {}
    readiness = evidence.get("readiness") or {}
    gate = compact_gate(evidence.get("go_live_gate") or {})
    final_prearm = evidence.get("final_live_ready_prearm") or {}
    final_armed = evidence.get("final_live_ready_armed") or {}
    go_live_report = evidence.get("go_live_report") or {}
    server_runner = evidence.get("server_live_readiness") or {}
    ai_operator = evidence.get("ai_operator") or {}
    paths = evidence.get("paths") or {}
    blockers = collect_blockers(env_profile, gate, final_prearm, final_armed)
    actions = build_actions()
    current_summary = {
        "app_env": evidence.get("app_env"),
        "exchange_mode": evidence.get("exchange_mode"),
        "readiness": readiness.get("overall"),
        "env_profile_status": env_profile.get("status"),
        "go_live_gate_status": gate.get("status"),
        "ready_to_enable_live": gate.get("ready_to_enable_live"),
        "ready_to_arm_live": gate.get("ready_to_arm_live"),
        "ready_for_live_order": gate.get("ready_for_live_order"),
        "final_prearm_ok": final_prearm.get("ok"),
        "final_armed_ok": final_armed.get("ok"),
        "ai_operator_ready": ai_operator.get("ready"),
        "ai_operator_file_write": ai_operator.get("allow_file_write"),
        "ai_operator_shell": ai_operator.get("allow_shell"),
        "server_runner_status": server_runner.get("status"),
    }
    evidence_paths = {
        "latest_go_live_report": evidence_path(paths, "latest_go_live_report"),
        "latest_go_live_report_md": evidence_path(paths, "latest_go_live_report_md"),
        "latest_server_go_live_audit": evidence_path(paths, "latest_server_go_live_audit"),
        "latest_server_go_live_audit_md": evidence_path(paths, "latest_server_go_live_audit_md"),
        "latest_server_bundle": evidence_path(paths, "latest_server_bundle"),
        "latest_local_readiness": evidence_path(paths, "latest_local_readiness"),
    }
    plan = {
        "ok": not blockers and bool(gate.get("ready_for_live_order")),
        "status": "ready_for_live_order" if gate.get("ready_for_live_order") else "blocked",
        "generated_at": utc_now(),
        "current_summary": current_summary,
        "blockers": blockers,
        "next_actions": [
            item.get("detail") for item in blockers[:8]
        ]
        or [
            "所有已知执行计划阻塞项已清空；最终仍以 final live verifier 和短时武装窗口为真实下单准入。"
        ],
        "stages": actions,
        "evidence_paths": evidence_paths,
        "safe_env_snapshot": env_profile.get("safe_env_snapshot") or {},
        "secret_fingerprints": env_profile.get("secret_fingerprints") or {},
        "go_live_report_summary": {
            "verdict": (go_live_report.get("verdict") or {}).get("status"),
            "ready_for_live_order": (go_live_report.get("verdict") or {}).get("ready_for_live_order"),
            "blocking_gate_ids": (go_live_report.get("verdict") or {}).get("blocking_gate_ids") or [],
        },
        "safety_note": (
            "该计划不会开启实盘、不会写入密钥、不会绕过风控/OMS/go-live gate。"
            "真实下单仍必须满足 live_guarded、人工证据、连续 Testnet 演练、final live verifier 和 ARM_LIVE_TRADING。"
        ),
    }
    plan["markdown"] = live_launch_plan_markdown(plan)
    return plan


def live_launch_plan_markdown(plan: dict[str, Any]) -> str:
    summary = plan.get("current_summary") or {}
    lines = [
        "# Live Launch Plan",
        "",
        f"- Generated: `{plan.get('generated_at')}`",
        f"- Status: `{plan.get('status')}`",
        f"- App environment: `{summary.get('app_env')}`",
        f"- Exchange mode: `{summary.get('exchange_mode')}`",
        f"- Readiness: `{summary.get('readiness')}`",
        f"- Environment profile: `{summary.get('env_profile_status')}`",
        f"- Go-live gate: `{summary.get('go_live_gate_status')}`",
        f"- Ready for live order: `{summary.get('ready_for_live_order')}`",
        "",
        "## Current Blockers",
        "",
    ]
    blockers = plan.get("blockers") or []
    if blockers:
        for item in blockers[:30]:
            vars_text = ", ".join(item.get("env_vars") or [])
            suffix = f" Env: `{vars_text}`" if vars_text else ""
            lines.append(f"- `{item.get('source')}` {item.get('label')}: {item.get('detail')}{suffix}")
    else:
        lines.append("- none")
    lines.extend(["", "## Evidence Paths", ""])
    for key, value in (plan.get("evidence_paths") or {}).items():
        lines.append(f"- {key}: `{value or '-'}`")
    lines.extend(["", "## Execution Stages", ""])
    for stage in plan.get("stages") or []:
        lines.extend(
            [
                f"### {stage.get('title')}",
                "",
                stage.get("goal") or "",
                "",
                "Environment changes:",
            ]
        )
        for item in stage.get("env_changes") or []:
            lines.append(f"- `{item}`")
        lines.append("")
        lines.append("Commands:")
        for command in stage.get("commands") or []:
            lines.append(f"- `{command}`")
        lines.append("")
        lines.append("Proof:")
        for proof in stage.get("proof") or []:
            lines.append(f"- {proof}")
        lines.append("")
    lines.extend(["## Safety Note", "", plan.get("safety_note") or ""])
    return "\n".join(lines).strip() + "\n"


def dumps_report(report: dict[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2)
