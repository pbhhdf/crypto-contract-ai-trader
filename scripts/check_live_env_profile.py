from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.live_env_profile import build_live_env_profile  # noqa: E402


def fail(message: str, payload: dict | None = None) -> int:
    print(
        json.dumps(
            {
                "ok": False,
                "error": message,
                "payload": payload or {},
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 1


def good_env() -> dict[str, str]:
    return {
        "APP_ENV": "server",
        "APP_HOST": "0.0.0.0",
        "APP_PORT": "8787",
        "APP_BASIC_AUTH_USER": "admin",
        "APP_BASIC_AUTH_PASSWORD": "very-long-server-password",
        "TRADER_BIND_IP": "100.80.1.2",
        "AI_PROVIDER": "rules",
        "AI_OPERATOR_ENABLED": "true",
        "AI_OPERATOR_PROVIDER": "codex",
        "AI_OPERATOR_ALLOW_FILE_WRITE": "true",
        "AI_OPERATOR_ALLOW_SHELL": "true",
        "AI_OPERATOR_APPLY_MODEL_FILE_ACTIONS": "true",
        "AI_OPERATOR_SNAPSHOT_WRITES": "true",
        "AI_OPERATOR_BACKUP_BEFORE_SHELL": "true",
        "EXCHANGE_MODE": "live_guarded",
        "ENABLE_BINANCE_TESTNET": "true",
        "BINANCE_API_KEY": "testnet-key-value",
        "BINANCE_API_SECRET": "testnet-secret-value",
        "BINANCE_PLACE_TESTNET_ORDERS": "true",
        "ENABLE_BINANCE_LIVE": "true",
        "BINANCE_LIVE_API_KEY": "live-key-value",
        "BINANCE_LIVE_API_SECRET": "live-secret-value",
        "BINANCE_PLACE_LIVE_ORDERS": "true",
        "LIVE_TRADING_CONFIRMATION": "I_UNDERSTAND_LIVE_RISK",
        "MAX_ORDER_NOTIONAL_USDT": "50",
        "MIN_PROTECTION_REWARD_RISK_RATIO": "1.0",
        "LIVE_PILOT_MAX_WALLET_USDT": "500",
        "GO_LIVE_MIN_TESTNET_DRILL_CYCLES": "24",
        "GO_LIVE_MIN_WALKFORWARD_FOLDS": "2",
        "GO_LIVE_MIN_WALKFORWARD_POSITIVE_FOLD_RATE_PCT": "50",
        "GO_LIVE_MAX_WALKFORWARD_DRAWDOWN_PCT": "10",
        "BINANCE_SYNC_MARGIN_TYPE_BEFORE_ORDER": "true",
        "BINANCE_TARGET_MARGIN_TYPE": "ISOLATED",
        "BINANCE_SYNC_LEVERAGE_BEFORE_ORDER": "true",
        "BINANCE_REQUIRE_ONE_WAY_POSITION_MODE": "true",
        "BINANCE_MAX_TIME_DRIFT_MS": "1000",
        "ALERT_WEBHOOK_ENABLED": "true",
        "ALERT_WEBHOOK_URL": "https://alerts.internal/hook",
    }


def contains_secret(serialized: str) -> bool:
    leaked_values = [
        "very-long-server-password",
        "testnet-key-value",
        "testnet-secret-value",
        "live-key-value",
        "live-secret-value",
        "https://alerts.internal/hook",
    ]
    return any(value in serialized for value in leaked_values)


def main() -> int:
    env = good_env()
    live_report = build_live_env_profile(env, target="live_guarded", source="unit")
    if not live_report.get("ok"):
        return fail("known-good live env did not pass", live_report)
    serialized = json.dumps(live_report, ensure_ascii=False)
    if contains_secret(serialized):
        return fail("live env profile leaked secret values")
    if not live_report.get("secret_fingerprints", {}).get("BINANCE_LIVE_API_SECRET"):
        return fail("live env profile did not include secret fingerprints")

    missing_env = dict(env)
    missing_env["BINANCE_LIVE_API_SECRET"] = ""
    missing_env["TRADER_BIND_IP"] = "8.8.8.8"
    missing_report = build_live_env_profile(missing_env, target="live_guarded", source="unit")
    if missing_report.get("ok"):
        return fail("missing live secret/public bind unexpectedly passed", missing_report)
    failed_ids = {item.get("id") for item in missing_report.get("failed_checks", [])}
    if not {"live_explicit_flags", "private_bind"}.issubset(failed_ids):
        return fail("missing profile did not surface expected failing checks", missing_report)

    mvp_env = dict(env)
    mvp_env.update(
        {
            "EXCHANGE_MODE": "paper",
            "ENABLE_BINANCE_TESTNET": "false",
            "BINANCE_API_KEY": "",
            "BINANCE_API_SECRET": "",
            "BINANCE_PLACE_TESTNET_ORDERS": "false",
            "ENABLE_BINANCE_LIVE": "false",
            "BINANCE_LIVE_API_KEY": "",
            "BINANCE_LIVE_API_SECRET": "",
            "BINANCE_PLACE_LIVE_ORDERS": "false",
            "LIVE_TRADING_CONFIRMATION": "",
        }
    )
    mvp_report = build_live_env_profile(mvp_env, target="mvp_server", source="unit")
    if not mvp_report.get("ok"):
        return fail("safe MVP server profile did not pass", mvp_report)

    print(
        json.dumps(
            {
                "ok": True,
                "checked": ["mvp_server", "live_guarded", "redaction"],
                "live_status": live_report.get("status"),
                "missing_status": missing_report.get("status"),
                "mvp_status": mvp_report.get("status"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
