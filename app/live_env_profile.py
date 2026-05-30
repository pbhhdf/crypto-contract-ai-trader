from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SENSITIVE_KEY_RE = re.compile(
    r"(SECRET|PASSWORD|TOKEN|API[_-]?KEY|PRIVATE[_-]?KEY|WEBHOOK[_-]?URL|CHAT[_-]?ID)",
    re.IGNORECASE,
)

PLACEHOLDER_VALUES = {
    "",
    "<choose-long-random-password>",
    "<binance-futures-testnet-key>",
    "<binance-futures-testnet-secret>",
    "<binance-live-key>",
    "<binance-live-secret>",
    "<internal-webhook-url>",
    "<telegram-bot-token>",
    "<telegram-chat-id>",
    "<smtp-host>",
    "<alerts-from-address>",
    "<operator-address>",
    "password",
    "changeme",
    "change-me",
    "your-password",
    "choose-long-random-password",
}

STAGE_ORDER = ["mvp_server", "testnet_validate", "testnet_place", "live_guarded"]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def merged_env(env_file: Path | None = None, prefer_process_env: bool = False) -> dict[str, str]:
    file_values = read_env_file(env_file) if env_file else {}
    process_values = {key: str(value) for key, value in os.environ.items()}
    if prefer_process_env:
        merged = dict(file_values)
        merged.update(process_values)
        return merged
    merged = dict(process_values)
    merged.update(file_values)
    return merged


def clean(value: Any) -> str:
    return str(value or "").strip()


def bool_value(env: dict[str, str], name: str, default: bool = False) -> bool:
    value = env.get(name)
    if value is None:
        return default
    return clean(value).lower() in {"1", "true", "yes", "on", "enabled"}


def number_value(env: dict[str, str], name: str, default: float = 0.0) -> float:
    try:
        return float(clean(env.get(name, default)))
    except (TypeError, ValueError):
        return default


def is_placeholder(value: Any) -> bool:
    text = clean(value)
    lowered = text.lower()
    return not text or lowered in PLACEHOLDER_VALUES or (lowered.startswith("<") and lowered.endswith(">"))


def is_sensitive_key(name: str) -> bool:
    return bool(SENSITIVE_KEY_RE.search(name))


def secret_fingerprint(value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
    return f"sha256:{digest}"


def safe_value(name: str, value: Any) -> str:
    text = clean(value)
    if is_sensitive_key(name):
        if is_placeholder(text):
            return "[MISSING]"
        return f"[SET:{secret_fingerprint(text)}]"
    if name in {"TRADER_BIND_IP"} and text:
        return text
    if name.endswith("_URL") and text:
        return "[SET]" if not is_placeholder(text) else "[MISSING]"
    return text if text else "[MISSING]"


def present(env: dict[str, str], name: str) -> bool:
    return not is_placeholder(env.get(name, ""))


def status_rank(status: str) -> int:
    return {"pass": 0, "warn": 1, "fail": 2}.get(status, 2)


def check_item(
    stage: str,
    item_id: str,
    label: str,
    status: str,
    detail: str,
    env_vars: list[str] | None = None,
    required: bool = True,
) -> dict[str, Any]:
    return {
        "stage": stage,
        "id": item_id,
        "label": label,
        "status": status,
        "detail": detail,
        "env_vars": env_vars or [],
        "required": required,
    }


def ip_profile(value: str) -> tuple[str, str]:
    text = clean(value)
    if is_placeholder(text):
        return "fail", "TRADER_BIND_IP 还没有填写 Tailscale IPv4。"
    if text in {"0.0.0.0", "::"}:
        return "fail", "TRADER_BIND_IP 不能是 0.0.0.0/::；控制台应只绑定私有入口。"
    try:
        ip = ipaddress.ip_address(text)
    except ValueError:
        return "warn", "TRADER_BIND_IP 不是标准 IP；如果这是内网主机名，请确认防火墙只允许 Tailscale。"
    tailscale_range = ipaddress.ip_network("100.64.0.0/10")
    if ip.version == 4 and ip in tailscale_range:
        return "pass", "TRADER_BIND_IP 是 Tailscale CGNAT 地址。"
    if ip.is_private or ip.is_loopback:
        return "warn", "TRADER_BIND_IP 是私有地址；请确认它来自 Tailscale 或仅内网可达。"
    return "fail", "TRADER_BIND_IP 看起来是公网地址；首阶段不应把交易控制台暴露公网。"


def alert_ready(env: dict[str, str]) -> tuple[bool, list[str]]:
    channels: list[str] = []
    if bool_value(env, "ALERT_WEBHOOK_ENABLED") and present(env, "ALERT_WEBHOOK_URL"):
        channels.append("webhook")
    if bool_value(env, "ALERT_TELEGRAM_ENABLED") and present(env, "ALERT_TELEGRAM_BOT_TOKEN") and present(env, "ALERT_TELEGRAM_CHAT_ID"):
        channels.append("telegram")
    if (
        bool_value(env, "ALERT_EMAIL_ENABLED")
        and present(env, "ALERT_EMAIL_SMTP_HOST")
        and present(env, "ALERT_EMAIL_FROM")
        and present(env, "ALERT_EMAIL_TO")
    ):
        channels.append("email")
    return bool(channels), channels


def mvp_checks(env: dict[str, str], target: str) -> list[dict[str, Any]]:
    stage = "mvp_server"
    checks: list[dict[str, Any]] = []
    app_env = clean(env.get("APP_ENV", "local")).lower()
    checks.append(
        check_item(
            stage,
            "app_env_server",
            "服务器运行模式",
            "pass" if app_env == "server" else "fail",
            "APP_ENV=server 已设置。" if app_env == "server" else "需要 APP_ENV=server；本地模式不能进入实盘。",
            ["APP_ENV"],
        )
    )
    app_host = clean(env.get("APP_HOST", "127.0.0.1"))
    checks.append(
        check_item(
            stage,
            "app_host",
            "服务监听地址",
            "pass" if app_host in {"0.0.0.0", "::", "127.0.0.1"} else "warn",
            "APP_HOST 已设置；Tailscale/UFW 负责外层访问控制。" if app_host else "APP_HOST 未设置，将使用默认值。",
            ["APP_HOST", "TRADER_BIND_IP"],
            required=False,
        )
    )
    auth_user_ready = present(env, "APP_BASIC_AUTH_USER")
    password = clean(env.get("APP_BASIC_AUTH_PASSWORD", ""))
    password_ok = present(env, "APP_BASIC_AUTH_PASSWORD") and len(password) >= 16
    checks.append(
        check_item(
            stage,
            "basic_auth",
            "Basic Auth",
            "pass" if auth_user_ready and password_ok else "fail",
            "Basic Auth 用户和强密码已配置。" if auth_user_ready and password_ok else "服务器必须配置 APP_BASIC_AUTH_USER 和至少 16 位强密码。",
            ["APP_BASIC_AUTH_USER", "APP_BASIC_AUTH_PASSWORD"],
        )
    )
    bind_status, bind_detail = ip_profile(clean(env.get("TRADER_BIND_IP", "127.0.0.1")))
    checks.append(check_item(stage, "private_bind", "Tailscale 私有入口", bind_status, bind_detail, ["TRADER_BIND_IP"]))
    ai_provider = clean(env.get("AI_PROVIDER", "rules")).lower()
    checks.append(
        check_item(
            stage,
            "ai_out_of_hot_path",
            "AI 不进入下单热路径",
            "pass" if ai_provider == "rules" else "warn",
            "AI_PROVIDER=rules，执行路径保持确定性。" if ai_provider == "rules" else "AI_PROVIDER 不是 rules；请确认模型只产出结构化建议，不直接下单。",
            ["AI_PROVIDER"],
            required=False,
        )
    )
    live_flags = bool_value(env, "ENABLE_BINANCE_LIVE") or bool_value(env, "BINANCE_PLACE_LIVE_ORDERS")
    checks.append(
        check_item(
            stage,
            "mvp_live_flags",
            "首阶段实盘开关",
            "pass" if target == "live_guarded" or not live_flags else "fail",
            "当前目标允许检查实盘开关。" if target == "live_guarded" else "首阶段应保持 ENABLE_BINANCE_LIVE=false 且 BINANCE_PLACE_LIVE_ORDERS=false。",
            ["ENABLE_BINANCE_LIVE", "BINANCE_PLACE_LIVE_ORDERS"],
        )
    )
    operator_enabled = bool_value(env, "AI_OPERATOR_ENABLED", True)
    operator_write = bool_value(env, "AI_OPERATOR_ALLOW_FILE_WRITE", False)
    operator_shell = bool_value(env, "AI_OPERATOR_ALLOW_SHELL", False)
    operator_apply = bool_value(env, "AI_OPERATOR_APPLY_MODEL_FILE_ACTIONS", False)
    operator_snapshots = bool_value(env, "AI_OPERATOR_SNAPSHOT_WRITES", True)
    operator_backup = bool_value(env, "AI_OPERATOR_BACKUP_BEFORE_SHELL", True)
    operator_ok = operator_enabled and operator_write and operator_shell and operator_apply and operator_snapshots and operator_backup
    checks.append(
        check_item(
            stage,
            "codex_operator_high_permission",
            "内置 Codex 高权限操作员",
            "pass" if operator_ok else "fail",
            "文件读写、Shell、自动应用、写前快照和 Shell 前备份均已启用。"
            if operator_ok
            else "需要启用 AI_OPERATOR_ALLOW_FILE_WRITE、AI_OPERATOR_ALLOW_SHELL、AI_OPERATOR_APPLY_MODEL_FILE_ACTIONS、AI_OPERATOR_SNAPSHOT_WRITES、AI_OPERATOR_BACKUP_BEFORE_SHELL。",
            [
                "AI_OPERATOR_ENABLED",
                "AI_OPERATOR_ALLOW_FILE_WRITE",
                "AI_OPERATOR_ALLOW_SHELL",
                "AI_OPERATOR_APPLY_MODEL_FILE_ACTIONS",
                "AI_OPERATOR_SNAPSHOT_WRITES",
                "AI_OPERATOR_BACKUP_BEFORE_SHELL",
            ],
        )
    )
    return checks


def testnet_validate_checks(env: dict[str, str], target: str) -> list[dict[str, Any]]:
    stage = "testnet_validate"
    enabled = bool_value(env, "ENABLE_BINANCE_TESTNET")
    keys = present(env, "BINANCE_API_KEY") and present(env, "BINANCE_API_SECRET")
    place = bool_value(env, "BINANCE_PLACE_TESTNET_ORDERS")
    mode = clean(env.get("EXCHANGE_MODE", "paper")).lower()
    pure_validation = target == "testnet_validate"
    return [
        check_item(
            stage,
            "testnet_keys",
            "Binance Testnet 密钥",
            "pass" if enabled and keys else "fail",
            "Testnet 已启用且 key/secret 已配置。" if enabled and keys else "验证阶段需要 ENABLE_BINANCE_TESTNET=true、BINANCE_API_KEY、BINANCE_API_SECRET。",
            ["ENABLE_BINANCE_TESTNET", "BINANCE_API_KEY", "BINANCE_API_SECRET"],
        ),
        check_item(
            stage,
            "testnet_validate_mode",
            "Testnet 验证模式",
            "pass" if mode in {"binance_testnet_validate", "binance_testnet_place_order", "live_guarded", "paper"} else "warn",
            "验证阶段会使用 /fapi/v1/order/test，不产生真实 testnet 挂单。" if not place else "BINANCE_PLACE_TESTNET_ORDERS=true 已打开；这不是纯验证模式。",
            ["EXCHANGE_MODE", "BINANCE_PLACE_TESTNET_ORDERS"],
            required=False,
        ),
        check_item(
            stage,
            "testnet_no_real_order",
            "验证阶段不下真实 Testnet 单",
            "pass" if not place or not pure_validation else "fail",
            "BINANCE_PLACE_TESTNET_ORDERS=false。"
            if not place
            else "当前目标已经超过纯验证阶段；真实 Testnet 下单仍由独立开关和门禁控制。",
            ["BINANCE_PLACE_TESTNET_ORDERS"],
            required=pure_validation,
        ),
    ]


def testnet_place_checks(env: dict[str, str], target: str) -> list[dict[str, Any]]:
    stage = "testnet_place"
    enabled = bool_value(env, "ENABLE_BINANCE_TESTNET")
    keys = present(env, "BINANCE_API_KEY") and present(env, "BINANCE_API_SECRET")
    place = bool_value(env, "BINANCE_PLACE_TESTNET_ORDERS")
    mode = clean(env.get("EXCHANGE_MODE", "paper")).lower()
    target_is_testnet_place = target == "testnet_place"
    place_ready = enabled and keys and ((place and mode == "binance_testnet_place_order") if target_is_testnet_place else mode in {"binance_testnet_place_order", "live_guarded", "paper"})
    sync_margin = bool_value(env, "BINANCE_SYNC_MARGIN_TYPE_BEFORE_ORDER", True)
    sync_leverage = bool_value(env, "BINANCE_SYNC_LEVERAGE_BEFORE_ORDER", True)
    return [
        check_item(
            stage,
            "testnet_place_flags",
            "真实 Testnet 下单开关",
            "pass" if place_ready else "fail" if target_is_testnet_place else "warn",
            "真实 Testnet 下单模式已完整显式启用。"
            if enabled and keys and place and mode == "binance_testnet_place_order"
            else "当前目标不要求保持 Testnet 下单开关开启；仍需要 Testnet key/secret 和已记录的演练周期。"
            if enabled and keys and not target_is_testnet_place
            else "真实 Testnet 下单需要 EXCHANGE_MODE=binance_testnet_place_order、ENABLE_BINANCE_TESTNET=true、BINANCE_PLACE_TESTNET_ORDERS=true 和 Testnet key/secret。",
            ["EXCHANGE_MODE", "ENABLE_BINANCE_TESTNET", "BINANCE_PLACE_TESTNET_ORDERS", "BINANCE_API_KEY", "BINANCE_API_SECRET"],
            required=target_is_testnet_place,
        ),
        check_item(
            stage,
            "testnet_order_safety_sync",
            "Testnet 保证金与杠杆同步",
            "pass" if sync_margin and sync_leverage else "fail",
            "下单前会同步保证金类型和杠杆。" if sync_margin and sync_leverage else "真实 Testnet 下单前必须启用保证金类型和杠杆同步。",
            ["BINANCE_SYNC_MARGIN_TYPE_BEFORE_ORDER", "BINANCE_SYNC_LEVERAGE_BEFORE_ORDER"],
        ),
    ]


def live_checks(env: dict[str, str]) -> list[dict[str, Any]]:
    stage = "live_guarded"
    mode = clean(env.get("EXCHANGE_MODE", "paper")).lower()
    live_enabled = bool_value(env, "ENABLE_BINANCE_LIVE")
    place_live = bool_value(env, "BINANCE_PLACE_LIVE_ORDERS")
    live_keys = present(env, "BINANCE_LIVE_API_KEY") and present(env, "BINANCE_LIVE_API_SECRET")
    confirmation = clean(env.get("LIVE_TRADING_CONFIRMATION", "")) == "I_UNDERSTAND_LIVE_RISK"
    alerts_ok, channels = alert_ready(env)
    max_notional = number_value(env, "MAX_ORDER_NOTIONAL_USDT", -1.0)
    min_reward_risk = number_value(env, "MIN_PROTECTION_REWARD_RISK_RATIO", -1.0)
    wallet_cap = number_value(env, "LIVE_PILOT_MAX_WALLET_USDT", -1.0)
    drill_cycles = int(number_value(env, "GO_LIVE_MIN_TESTNET_DRILL_CYCLES", 0))
    max_time_drift = int(number_value(env, "BINANCE_MAX_TIME_DRIFT_MS", 0))
    target_margin = clean(env.get("BINANCE_TARGET_MARGIN_TYPE", "ISOLATED")).upper()
    sync_margin = bool_value(env, "BINANCE_SYNC_MARGIN_TYPE_BEFORE_ORDER", True)
    sync_leverage = bool_value(env, "BINANCE_SYNC_LEVERAGE_BEFORE_ORDER", True)
    one_way = bool_value(env, "BINANCE_REQUIRE_ONE_WAY_POSITION_MODE", True)
    walkforward_folds = int(number_value(env, "GO_LIVE_MIN_WALKFORWARD_FOLDS", 0))
    positive_rate = number_value(env, "GO_LIVE_MIN_WALKFORWARD_POSITIVE_FOLD_RATE_PCT", -1.0)
    max_drawdown = number_value(env, "GO_LIVE_MAX_WALKFORWARD_DRAWDOWN_PCT", -1.0)
    return [
        check_item(
            stage,
            "live_explicit_flags",
            "实盘显式开关",
            "pass" if mode == "live_guarded" and live_enabled and place_live and live_keys and confirmation else "fail",
            "live_guarded、实盘 key、真实下单开关和风险确认短语均已设置。"
            if mode == "live_guarded" and live_enabled and place_live and live_keys and confirmation
            else "实盘需要 EXCHANGE_MODE=live_guarded、ENABLE_BINANCE_LIVE=true、BINANCE_PLACE_LIVE_ORDERS=true、实盘 key/secret 和 LIVE_TRADING_CONFIRMATION=I_UNDERSTAND_LIVE_RISK。",
            ["EXCHANGE_MODE", "ENABLE_BINANCE_LIVE", "BINANCE_PLACE_LIVE_ORDERS", "BINANCE_LIVE_API_KEY", "BINANCE_LIVE_API_SECRET", "LIVE_TRADING_CONFIRMATION"],
        ),
        check_item(
            stage,
            "live_alert_channel",
            "实盘外部告警",
            "pass" if alerts_ok else "fail",
            f"已配置告警通道：{', '.join(channels)}。" if alerts_ok else "实盘必须至少配置 Webhook、Telegram 或 Email 之一。",
            ["ALERT_WEBHOOK_ENABLED", "ALERT_WEBHOOK_URL", "ALERT_TELEGRAM_ENABLED", "ALERT_TELEGRAM_BOT_TOKEN", "ALERT_TELEGRAM_CHAT_ID", "ALERT_EMAIL_ENABLED", "ALERT_EMAIL_SMTP_HOST", "ALERT_EMAIL_FROM", "ALERT_EMAIL_TO"],
        ),
        check_item(
            stage,
            "live_pilot_caps",
            "小额试运行资金上限",
            "pass" if max_notional > 0 and wallet_cap > 0 and min_reward_risk >= 1 else "fail",
            f"单笔名义上限 {max_notional:g} USDT，钱包试运行上限 {wallet_cap:g} USDT，最小保护单盈亏比 {min_reward_risk:g}。"
            if max_notional > 0 and wallet_cap > 0 and min_reward_risk >= 1
            else "实盘必须设置 MAX_ORDER_NOTIONAL_USDT 和 LIVE_PILOT_MAX_WALLET_USDT 为正数，且 MIN_PROTECTION_REWARD_RISK_RATIO 至少为 1。",
            ["MAX_ORDER_NOTIONAL_USDT", "LIVE_PILOT_MAX_WALLET_USDT", "MIN_PROTECTION_REWARD_RISK_RATIO"],
        ),
        check_item(
            stage,
            "live_exchange_safety",
            "交易所执行安全同步",
            "pass" if sync_margin and sync_leverage and one_way and target_margin in {"ISOLATED", "CROSSED"} else "fail",
            f"保证金类型同步={sync_margin}，杠杆同步={sync_leverage}，单向持仓要求={one_way}，目标保证金={target_margin}。",
            ["BINANCE_SYNC_MARGIN_TYPE_BEFORE_ORDER", "BINANCE_SYNC_LEVERAGE_BEFORE_ORDER", "BINANCE_REQUIRE_ONE_WAY_POSITION_MODE", "BINANCE_TARGET_MARGIN_TYPE"],
        ),
        check_item(
            stage,
            "live_testnet_drill_requirement",
            "Testnet 演练门槛",
            "pass" if drill_cycles >= 24 else "fail",
            f"门槛为 {drill_cycles} 次；服务器仍需真实跑满这些周期并被 go-live gate 记录。" if drill_cycles >= 24 else "GO_LIVE_MIN_TESTNET_DRILL_CYCLES 至少应为 24。",
            ["GO_LIVE_MIN_TESTNET_DRILL_CYCLES"],
        ),
        check_item(
            stage,
            "live_strategy_quality_thresholds",
            "策略滚动验证阈值",
            "pass" if walkforward_folds >= 1 and 0 <= positive_rate <= 100 and 0 <= max_drawdown <= 100 else "fail",
            f"Walk-forward folds={walkforward_folds}，正收益 fold 率阈值={positive_rate:g}%，最大回撤阈值={max_drawdown:g}%。",
            ["GO_LIVE_MIN_WALKFORWARD_FOLDS", "GO_LIVE_MIN_WALKFORWARD_POSITIVE_FOLD_RATE_PCT", "GO_LIVE_MAX_WALKFORWARD_DRAWDOWN_PCT"],
        ),
        check_item(
            stage,
            "live_time_drift_threshold",
            "Binance 时间漂移阈值",
            "pass" if 50 <= max_time_drift <= 1000 else "warn",
            f"BINANCE_MAX_TIME_DRIFT_MS={max_time_drift}；实际时间漂移仍需服务器检查通过。" if max_time_drift else "BINANCE_MAX_TIME_DRIFT_MS 未正确设置。",
            ["BINANCE_MAX_TIME_DRIFT_MS"],
            required=False,
        ),
    ]


def build_live_env_profile(
    env: dict[str, str] | None = None,
    target: str = "live_guarded",
    source: str = "runtime",
) -> dict[str, Any]:
    env = {key: str(value) for key, value in (env or os.environ).items()}
    target = clean(target or "live_guarded").lower()
    if target not in STAGE_ORDER:
        target = "live_guarded"
    checked_stages = STAGE_ORDER[: STAGE_ORDER.index(target) + 1]
    all_checks = (
        mvp_checks(env, target)
        + testnet_validate_checks(env, target)
        + testnet_place_checks(env, target)
        + live_checks(env)
    )
    checks = [item for item in all_checks if item["stage"] in checked_stages]
    stage_reports: dict[str, dict[str, Any]] = {}
    for stage in checked_stages:
        stage_checks = [item for item in checks if item["stage"] == stage]
        worst = max((status_rank(item["status"]) for item in stage_checks), default=0)
        stage_status = "fail" if worst >= 2 else "warn" if worst == 1 else "pass"
        stage_reports[stage] = {
            "status": stage_status,
            "ok": stage_status != "fail",
            "checks": stage_checks,
        }
    failed = [item for item in checks if item["status"] == "fail"]
    warned = [item for item in checks if item["status"] == "warn"]
    required_vars = sorted({var for item in checks if item.get("required") for var in item.get("env_vars", [])})
    missing_required_vars = sorted(
        var
        for var in required_vars
        if is_placeholder(env.get(var, "")) and var not in {"BINANCE_PLACE_TESTNET_ORDERS", "ENABLE_BINANCE_LIVE", "BINANCE_PLACE_LIVE_ORDERS"}
    )
    snapshot_keys = [
        "APP_ENV",
        "APP_HOST",
        "APP_PORT",
        "TRADER_BIND_IP",
        "EXCHANGE_MODE",
        "AI_PROVIDER",
        "AI_OPERATOR_PROVIDER",
        "AI_OPERATOR_ALLOW_FILE_WRITE",
        "AI_OPERATOR_ALLOW_SHELL",
        "AI_OPERATOR_APPLY_MODEL_FILE_ACTIONS",
        "AI_OPERATOR_SNAPSHOT_WRITES",
        "AI_OPERATOR_BACKUP_BEFORE_SHELL",
        "ENABLE_BINANCE_TESTNET",
        "BINANCE_PLACE_TESTNET_ORDERS",
        "ENABLE_BINANCE_LIVE",
        "BINANCE_PLACE_LIVE_ORDERS",
        "LIVE_TRADING_CONFIRMATION",
        "MAX_ORDER_NOTIONAL_USDT",
        "MIN_PROTECTION_REWARD_RISK_RATIO",
        "LIVE_PILOT_MAX_WALLET_USDT",
        "GO_LIVE_MIN_TESTNET_DRILL_CYCLES",
        "BINANCE_TARGET_MARGIN_TYPE",
    ]
    fingerprint_keys = set(snapshot_keys) | {
        "APP_BASIC_AUTH_PASSWORD",
        "OPENAI_API_KEY",
        "BINANCE_API_KEY",
        "BINANCE_API_SECRET",
        "BINANCE_LIVE_API_KEY",
        "BINANCE_LIVE_API_SECRET",
        "ALERT_WEBHOOK_URL",
        "ALERT_WEBHOOK_SECRET",
        "ALERT_TELEGRAM_BOT_TOKEN",
        "ALERT_TELEGRAM_CHAT_ID",
        "ALERT_EMAIL_SMTP_PASSWORD",
    }
    secret_fingerprints = {
        key: secret_fingerprint(clean(env.get(key, "")))
        for key in sorted(fingerprint_keys)
        if is_sensitive_key(key) and not is_placeholder(env.get(key, ""))
    }
    safe_snapshot = {key: safe_value(key, env.get(key, "")) for key in snapshot_keys}
    next_actions = [
        f"{item['label']}：{item['detail']}"
        for item in failed[:8]
    ]
    if not next_actions and warned:
        next_actions = [f"{item['label']}：{item['detail']}" for item in warned[:5]]
    if not next_actions:
        next_actions = [
            "环境变量剖面已通过；仍需 go-live gate、真实 Testnet 周期、人工证据和短时武装窗口全部通过后才会真实下单。"
        ]
    status = "fail" if failed else "warn" if warned else "pass"
    return {
        "ok": not failed,
        "status": status,
        "target": target,
        "checked_stages": checked_stages,
        "generated_at": utc_now(),
        "source": source,
        "stage_reports": stage_reports,
        "checks": checks,
        "failed_checks": failed,
        "warnings": warned,
        "missing_required_vars": missing_required_vars,
        "safe_env_snapshot": safe_snapshot,
        "secret_fingerprints": secret_fingerprints,
        "next_actions": next_actions,
        "note": "该审计只验证服务器环境剖面，不会替代 go-live gate、人工证据、连续 Testnet 演练或 ARM_LIVE_TRADING 短时授权。",
    }


def dumps_report(report: dict[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2)
