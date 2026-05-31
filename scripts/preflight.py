from __future__ import annotations

import ipaddress
import json
import os
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT_DIR = Path(__file__).resolve().parents[1]
TAILSCALE_CGNAT = ipaddress.ip_network("100.64.0.0/10")


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def bool_env(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).lower() == "true"


def has_placeholder(value: str) -> bool:
    lowered = value.strip().lower()
    return not lowered or lowered.startswith("<") or lowered in {
        "password",
        "changeme",
        "change-me",
        "your-password",
        "choose-long-random-password",
    }


def private_bind_profile(value: str) -> dict[str, Any]:
    text = str(value or "").strip()
    if has_placeholder(text):
        return {
            "ok": False,
            "status": "fail",
            "category": "placeholder",
            "detail": "TRADER_BIND_IP still looks like a placeholder; use 127.0.0.1, a private IP, or a Tailscale 100.64.0.0/10 address.",
        }
    if text in {"0.0.0.0", "::"}:
        return {
            "ok": False,
            "status": "fail",
            "category": "wildcard",
            "detail": "TRADER_BIND_IP must not be 0.0.0.0/:: in the Tailscale-first server profile.",
        }
    try:
        ip = ipaddress.ip_address(text)
    except ValueError:
        return {
            "ok": False,
            "status": "fail",
            "category": "invalid_ip",
            "detail": "TRADER_BIND_IP must be an explicit IP address: 127.0.0.1, a private IP, or a Tailscale 100.64.0.0/10 address.",
        }
    if ip.version == 4 and ip in TAILSCALE_CGNAT:
        category = "tailscale_cgnat"
        detail = "TRADER_BIND_IP is a Tailscale CGNAT address."
    elif ip.is_loopback:
        category = "loopback"
        detail = "TRADER_BIND_IP is loopback; use this behind Tailscale Serve, an SSH tunnel, or a local reverse proxy."
    elif ip.is_link_local:
        category = "link_local"
        detail = "TRADER_BIND_IP is link-local; confirm the server is not reachable from the public internet."
    elif ip.is_private:
        category = "private"
        detail = "TRADER_BIND_IP is private; confirm the firewall only allows trusted private network or Tailscale access."
    else:
        return {
            "ok": False,
            "status": "fail",
            "category": "public",
            "detail": "TRADER_BIND_IP looks like a public address; do not expose the trading console directly to the internet.",
        }
    return {"ok": True, "status": "pass", "category": category, "detail": detail}


def check_binance_public() -> dict[str, Any]:
    base_url = os.getenv("BINANCE_FAPI_BASE", "https://fapi.binance.com").rstrip("/")
    query = urlencode({"symbol": os.getenv("TRADER_SYMBOL", "BTCUSDT")})
    request = Request(
        f"{base_url}/fapi/v1/premiumIndex?{query}",
        headers={"User-Agent": "crypto-contract-ai-trader-preflight/0.1"},
    )
    timeout = float(os.getenv("HTTP_TIMEOUT_SECONDS", "8"))
    retries = int(os.getenv("HTTP_RETRIES", "2"))
    for attempt in range(retries + 1):
        try:
            with urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
            break
        except HTTPError as exc:
            if exc.code not in {418, 429, 500, 502, 503, 504} or attempt >= retries:
                raise
            time.sleep(0.6 * (attempt + 1))
    return {
        "base_url": base_url,
        "symbol": payload.get("symbol"),
        "mark_price": payload.get("markPrice"),
        "last_funding_rate": payload.get("lastFundingRate"),
    }


def main() -> int:
    load_env_file(ROOT_DIR / ".env")
    errors: list[str] = []
    warnings: list[str] = []

    required_files = [
        "app/server.py",
        "app/live_ops_handoff.py",
        "app/static/index.html",
        "app/static/app.js",
        "deploy/docker-compose.yml",
        "deploy/server.env.example",
        "deploy/setup-ubuntu-tailscale.sh",
        "deploy/setup-ubuntu-time-sync.sh",
        "deploy/backup-server.sh",
        "deploy/restore-server.sh",
        "scripts/backup_state.py",
        "scripts/restore_state.py",
        "scripts/check_restore_state.py",
        "scripts/check_panic_stop.py",
        "scripts/check_walkforward_quality_gate.py",
        "scripts/check_exchange_emergency.py",
        "scripts/check_live_attestation.py",
        "scripts/check_final_live_ready.py",
        "scripts/check_final_live_ready_api.py",
        "scripts/live_env_profile.py",
        "scripts/check_live_env_profile.py",
        "scripts/export_live_launch_plan.py",
        "scripts/check_live_launch_plan.py",
        "scripts/check_live_launch_plan_api.py",
        "scripts/export_live_ops_handoff.py",
        "scripts/check_live_ops_handoff.py",
        "scripts/check_live_ops_handoff_api.py",
        "scripts/export_live_launch_kit.py",
        "scripts/check_live_launch_kit.py",
        "scripts/check_live_launch_kit_api.py",
        "scripts/export_live_env_pack.py",
        "scripts/check_live_env_pack.py",
        "scripts/check_live_env_pack_api.py",
        "scripts/check_live_blocker_resolution.py",
        "scripts/check_live_pilot_postflight.py",
        "scripts/server_go_live_audit.py",
        "scripts/check_server_go_live_audit.py",
        "scripts/check_server_go_live_audit_api.py",
        "scripts/export_go_live_report.py",
        ".dockerignore",
        ".env.example",
    ]
    missing = [path for path in required_files if not (ROOT_DIR / path).exists()]
    if missing:
        errors.append(f"Missing required files: {', '.join(missing)}")

    app_env = os.getenv("APP_ENV", "local")
    auth_user = os.getenv("APP_BASIC_AUTH_USER", "")
    auth_password = os.getenv("APP_BASIC_AUTH_PASSWORD", "")
    if app_env == "server" and not (auth_user and auth_password):
        errors.append("APP_ENV=server requires APP_BASIC_AUTH_USER and APP_BASIC_AUTH_PASSWORD.")
    if app_env == "server" and auth_password and len(auth_password) < 16:
        errors.append("APP_BASIC_AUTH_PASSWORD must be at least 16 characters in server mode.")
    if app_env == "server" and has_placeholder(auth_password):
        errors.append("APP_BASIC_AUTH_PASSWORD still looks like a placeholder.")

    bind_ip = os.getenv("TRADER_BIND_IP", "127.0.0.1").strip()
    bind_profile = private_bind_profile(bind_ip)
    if app_env == "server" and not bind_profile["ok"]:
        errors.append(str(bind_profile["detail"]))

    try:
        max_order_notional = float(os.getenv("MAX_ORDER_NOTIONAL_USDT", "1000"))
    except ValueError:
        max_order_notional = -1.0
    try:
        min_protection_reward_risk = float(os.getenv("MIN_PROTECTION_REWARD_RISK_RATIO", "1.0"))
    except ValueError:
        min_protection_reward_risk = -1.0
    try:
        live_pilot_max_wallet = float(os.getenv("LIVE_PILOT_MAX_WALLET_USDT", "5000"))
    except ValueError:
        live_pilot_max_wallet = -1.0
    try:
        account_snapshot_max_age = int(float(os.getenv("EXCHANGE_ACCOUNT_SNAPSHOT_MAX_AGE_SECONDS", "30")))
    except ValueError:
        account_snapshot_max_age = 0
    try:
        max_time_drift_ms = int(float(os.getenv("BINANCE_MAX_TIME_DRIFT_MS", "1000")))
    except ValueError:
        max_time_drift_ms = 0
    try:
        live_attestation_max_age_days = int(float(os.getenv("LIVE_ATTESTATION_MAX_AGE_DAYS", "30")))
    except ValueError:
        live_attestation_max_age_days = 0
    try:
        walkforward_min_folds = int(float(os.getenv("GO_LIVE_MIN_WALKFORWARD_FOLDS", "2")))
    except ValueError:
        walkforward_min_folds = 0
    try:
        walkforward_min_return = float(os.getenv("GO_LIVE_MIN_WALKFORWARD_TOTAL_RETURN_PCT", "0"))
    except ValueError:
        walkforward_min_return = -999999.0
    try:
        walkforward_min_positive_rate = float(os.getenv("GO_LIVE_MIN_WALKFORWARD_POSITIVE_FOLD_RATE_PCT", "50"))
    except ValueError:
        walkforward_min_positive_rate = -1.0
    try:
        walkforward_max_drawdown = float(os.getenv("GO_LIVE_MAX_WALKFORWARD_DRAWDOWN_PCT", "10"))
    except ValueError:
        walkforward_max_drawdown = -1.0
    if max_order_notional < 0:
        errors.append("MAX_ORDER_NOTIONAL_USDT must be a non-negative number.")
    if not (0 <= min_protection_reward_risk <= 100):
        errors.append("MIN_PROTECTION_REWARD_RISK_RATIO must be between 0 and 100.")
    if live_pilot_max_wallet < 0:
        errors.append("LIVE_PILOT_MAX_WALLET_USDT must be a non-negative number.")
    if account_snapshot_max_age < 1:
        errors.append("EXCHANGE_ACCOUNT_SNAPSHOT_MAX_AGE_SECONDS must be at least 1 second.")
    if max_time_drift_ms < 50:
        errors.append("BINANCE_MAX_TIME_DRIFT_MS must be at least 50 milliseconds.")
    if live_attestation_max_age_days < 1:
        errors.append("LIVE_ATTESTATION_MAX_AGE_DAYS must be at least 1 day.")
    if walkforward_min_folds < 1:
        errors.append("GO_LIVE_MIN_WALKFORWARD_FOLDS must be at least 1.")
    if not (-100 <= walkforward_min_return <= 100000):
        errors.append("GO_LIVE_MIN_WALKFORWARD_TOTAL_RETURN_PCT is outside the allowed range.")
    if not (0 <= walkforward_min_positive_rate <= 100):
        errors.append("GO_LIVE_MIN_WALKFORWARD_POSITIVE_FOLD_RATE_PCT must be between 0 and 100.")
    if not (0 <= walkforward_max_drawdown <= 100):
        errors.append("GO_LIVE_MAX_WALKFORWARD_DRAWDOWN_PCT must be between 0 and 100.")
    if (bool_env("ENABLE_BINANCE_LIVE") or bool_env("BINANCE_PLACE_LIVE_ORDERS") or os.getenv("EXCHANGE_MODE", "paper") == "live_guarded") and max_order_notional <= 0:
        errors.append("Live mode requires MAX_ORDER_NOTIONAL_USDT to be greater than 0.")
    if (bool_env("ENABLE_BINANCE_LIVE") or bool_env("BINANCE_PLACE_LIVE_ORDERS") or os.getenv("EXCHANGE_MODE", "paper") == "live_guarded") and live_pilot_max_wallet <= 0:
        errors.append("Live mode requires LIVE_PILOT_MAX_WALLET_USDT to be greater than 0.")

    exchange_mode = os.getenv("EXCHANGE_MODE", "paper")
    places_testnet_orders = bool_env("BINANCE_PLACE_TESTNET_ORDERS")
    places_live_orders = bool_env("BINANCE_PLACE_LIVE_ORDERS")
    if exchange_mode not in {"paper", "binance_testnet_validate", "binance_testnet_place_order", "live_guarded"}:
        errors.append("EXCHANGE_MODE must be paper, binance_testnet_validate, binance_testnet_place_order, or live_guarded in this build.")

    if os.getenv("AI_PROVIDER", "rules") != "rules":
        warnings.append("AI_PROVIDER is not rules. The MVP server plan keeps AI out of the execution path.")
    operator_provider = os.getenv("AI_OPERATOR_PROVIDER", os.getenv("AI_PROVIDER", "rules")).lower()
    if operator_provider not in {"rules", "openai", "codex"}:
        errors.append("AI_OPERATOR_PROVIDER must be rules, openai, or codex.")
    if operator_provider in {"openai", "codex"} and not os.getenv("OPENAI_API_KEY", ""):
        warnings.append("AI_OPERATOR_PROVIDER uses a model provider but OPENAI_API_KEY is not configured; operator chat will fall back to local rules.")
    operator_write_default = "true" if app_env == "local" else "false"
    operator_write_enabled = bool_env("AI_OPERATOR_ALLOW_FILE_WRITE", operator_write_default)
    operator_shell_default = "true" if app_env == "local" else "false"
    operator_shell_enabled = bool_env("AI_OPERATOR_ALLOW_SHELL", operator_shell_default)
    if app_env == "server" and operator_write_enabled:
        warnings.append(
            "AI_OPERATOR_ALLOW_FILE_WRITE=true lets the authenticated UI modify workspace files; keep it on a private tailnet and audit operator messages."
        )
    if app_env == "server" and operator_shell_enabled:
        warnings.append(
            "AI_OPERATOR_ALLOW_SHELL=true lets the authenticated UI run OS commands as the service user; keep it on a private tailnet, require strong Basic Auth, and keep backups."
        )
    operator_auto_apply = bool_env(
        "AI_OPERATOR_APPLY_MODEL_FILE_ACTIONS",
        "true" if operator_write_enabled and operator_shell_enabled else "false",
    )
    operator_snapshot_writes = bool_env("AI_OPERATOR_SNAPSHOT_WRITES", "true")
    operator_backup_before_shell = bool_env("AI_OPERATOR_BACKUP_BEFORE_SHELL", "true")
    if app_env == "server" and operator_auto_apply:
        warnings.append(
            "AI_OPERATOR_APPLY_MODEL_FILE_ACTIONS=true lets the model apply file actions automatically; use only after backups and access controls are verified."
        )
    if app_env == "server" and operator_write_enabled and not operator_snapshot_writes:
        warnings.append(
            "AI_OPERATOR_SNAPSHOT_WRITES=false disables automatic pre-write file snapshots for the high-permission operator."
        )
    if app_env == "server" and operator_shell_enabled and not operator_backup_before_shell:
        errors.append(
            "AI_OPERATOR_BACKUP_BEFORE_SHELL=true is required when server Shell access is enabled."
        )

    testnet_enabled = bool_env("ENABLE_BINANCE_TESTNET")
    testnet_key_ready = bool(os.getenv("BINANCE_API_KEY", "") and os.getenv("BINANCE_API_SECRET", ""))
    live_enabled = bool_env("ENABLE_BINANCE_LIVE")
    live_key_ready = bool(os.getenv("BINANCE_LIVE_API_KEY", "") and os.getenv("BINANCE_LIVE_API_SECRET", ""))
    live_confirmation_ready = os.getenv("LIVE_TRADING_CONFIRMATION", "") == "I_UNDERSTAND_LIVE_RISK"
    sync_margin_type_before_order = bool_env("BINANCE_SYNC_MARGIN_TYPE_BEFORE_ORDER", "true")
    target_margin_type = os.getenv("BINANCE_TARGET_MARGIN_TYPE", "ISOLATED").upper().strip()
    sync_leverage_before_order = bool_env("BINANCE_SYNC_LEVERAGE_BEFORE_ORDER", "true")
    require_one_way_position_mode = bool_env("BINANCE_REQUIRE_ONE_WAY_POSITION_MODE", "true")
    if places_testnet_orders and not (testnet_enabled and testnet_key_ready):
        errors.append("BINANCE_PLACE_TESTNET_ORDERS=true requires ENABLE_BINANCE_TESTNET=true plus Binance testnet keys.")
    if places_testnet_orders and exchange_mode != "binance_testnet_place_order":
        warnings.append("BINANCE_PLACE_TESTNET_ORDERS=true is set, but EXCHANGE_MODE is not binance_testnet_place_order.")
    if places_live_orders and not (live_enabled and live_key_ready and live_confirmation_ready):
        errors.append("BINANCE_PLACE_LIVE_ORDERS=true requires ENABLE_BINANCE_LIVE=true, Binance live keys, and LIVE_TRADING_CONFIRMATION=I_UNDERSTAND_LIVE_RISK.")
    if exchange_mode == "live_guarded" and not (live_enabled and live_key_ready and places_live_orders and live_confirmation_ready):
        errors.append("EXCHANGE_MODE=live_guarded requires explicit live enablement, live keys, live order flag, and confirmation text.")
    if (live_enabled or places_live_orders or exchange_mode == "live_guarded") and app_env != "server":
        errors.append("Live mode requires APP_ENV=server; local mode is limited to paper trading, backtests, and drills.")
    if testnet_enabled and not testnet_key_ready:
        errors.append("ENABLE_BINANCE_TESTNET=true requires BINANCE_API_KEY and BINANCE_API_SECRET.")
    if exchange_mode in {"binance_testnet_validate", "binance_testnet_place_order"} and not (testnet_enabled and testnet_key_ready):
        errors.append("Binance testnet exchange modes require ENABLE_BINANCE_TESTNET=true plus testnet keys.")
    if target_margin_type not in {"ISOLATED", "CROSSED"}:
        errors.append("BINANCE_TARGET_MARGIN_TYPE must be ISOLATED or CROSSED.")
    if (places_testnet_orders or live_enabled or places_live_orders or exchange_mode == "live_guarded") and not sync_margin_type_before_order:
        errors.append("Real Binance testnet/live order modes require BINANCE_SYNC_MARGIN_TYPE_BEFORE_ORDER=true.")
    if (places_testnet_orders or live_enabled or places_live_orders or exchange_mode == "live_guarded") and not sync_leverage_before_order:
        errors.append("Real Binance testnet/live order modes require BINANCE_SYNC_LEVERAGE_BEFORE_ORDER=true.")
    if (live_enabled or places_live_orders or exchange_mode == "live_guarded") and not require_one_way_position_mode:
        errors.append("Live mode requires BINANCE_REQUIRE_ONE_WAY_POSITION_MODE=true.")

    webhook_ready = bool_env("ALERT_WEBHOOK_ENABLED") and bool(os.getenv("ALERT_WEBHOOK_URL", ""))
    telegram_ready = bool_env("ALERT_TELEGRAM_ENABLED") and bool(
        os.getenv("ALERT_TELEGRAM_BOT_TOKEN", "") and os.getenv("ALERT_TELEGRAM_CHAT_ID", "")
    )
    email_recipients = [item.strip() for item in os.getenv("ALERT_EMAIL_TO", "").replace(";", ",").split(",") if item.strip()]
    email_ready = bool_env("ALERT_EMAIL_ENABLED") and bool(
        os.getenv("ALERT_EMAIL_SMTP_HOST", "") and os.getenv("ALERT_EMAIL_FROM", "") and email_recipients
    )
    alert_channel_ready = webhook_ready or telegram_ready or email_ready
    alert_required = bool_env("GO_LIVE_REQUIRE_ALERT_WEBHOOK", "true" if app_env == "server" else "false")
    if alert_required and (live_enabled or places_live_orders or exchange_mode == "live_guarded") and not alert_channel_ready:
        errors.append("Live mode requires at least one configured alert channel: Webhook, Telegram, or Email.")
    if app_env == "server" and not alert_channel_ready:
        warnings.append("No external alert channel is configured; unattended server operation should use Webhook, Telegram, or Email.")

    market_check: dict[str, Any] | None = None
    try:
        if os.getenv("MARKET_DATA_SOURCE", "binance_public") == "binance_public":
            market_check = check_binance_public()
    except Exception as exc:
        warnings.append(f"Binance public market check failed: {exc.__class__.__name__}: {exc}")

    report = {
        "ok": not errors,
        "python": sys.version.split()[0],
        "project_root": str(ROOT_DIR),
        "app_env": app_env,
        "server_deployment_profile_ready": app_env == "server" and bool(auth_user and auth_password) and bool(bind_profile["ok"]),
        "auth_configured": bool(auth_user and auth_password),
        "trader_bind_ip": bind_ip,
        "trader_bind_profile": bind_profile,
        "max_order_notional_usdt": max_order_notional,
        "live_pilot_max_wallet_usdt": live_pilot_max_wallet,
        "go_live_min_walkforward_folds": walkforward_min_folds,
        "go_live_min_walkforward_total_return_pct": walkforward_min_return,
        "go_live_min_walkforward_positive_fold_rate_pct": walkforward_min_positive_rate,
        "go_live_max_walkforward_drawdown_pct": walkforward_max_drawdown,
        "exchange_account_snapshot_max_age_seconds": account_snapshot_max_age,
        "binance_max_time_drift_ms": max_time_drift_ms,
        "live_attestation_max_age_days": live_attestation_max_age_days,
        "exchange_mode": exchange_mode,
        "binance_testnet_enabled": testnet_enabled,
        "binance_testnet_key_ready": testnet_key_ready,
        "binance_places_testnet_orders": places_testnet_orders,
        "binance_live_enabled": live_enabled,
        "binance_live_key_ready": live_key_ready,
        "binance_places_live_orders": places_live_orders,
        "binance_live_confirmation_ready": live_confirmation_ready,
        "binance_sync_margin_type_before_order": sync_margin_type_before_order,
        "binance_target_margin_type": target_margin_type,
        "binance_sync_leverage_before_order": sync_leverage_before_order,
        "binance_require_one_way_position_mode": require_one_way_position_mode,
        "ai_provider": os.getenv("AI_PROVIDER", "rules"),
        "ai_operator_provider": operator_provider,
        "ai_operator_enabled": bool_env("AI_OPERATOR_ENABLED", "true"),
        "ai_operator_allow_file_write": operator_write_enabled,
        "ai_operator_allow_shell": operator_shell_enabled,
        "ai_operator_apply_model_file_actions": operator_auto_apply,
        "ai_operator_snapshot_writes": operator_snapshot_writes,
        "ai_operator_backup_before_shell": operator_backup_before_shell,
        "alert_webhook_ready": webhook_ready,
        "alert_telegram_ready": telegram_ready,
        "alert_email_ready": email_ready,
        "alert_channel_ready": alert_channel_ready,
        "market_data_source": os.getenv("MARKET_DATA_SOURCE", "binance_public"),
        "market_check": market_check,
        "warnings": warnings,
        "errors": errors,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
