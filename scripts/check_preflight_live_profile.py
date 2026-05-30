from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def fail(message: str) -> int:
    print(f"FAILED: {message}", file=sys.stderr)
    return 1


def run_preflight(overrides: dict[str, str]) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(
        {
            "MARKET_DATA_SOURCE": "synthetic",
            "APP_BASIC_AUTH_USER": "",
            "APP_BASIC_AUTH_PASSWORD": "",
            "ALERT_WEBHOOK_ENABLED": "false",
            "ALERT_TELEGRAM_ENABLED": "false",
            "ALERT_EMAIL_ENABLED": "false",
        }
    )
    env.update(overrides)
    return subprocess.run(
        [sys.executable, "scripts/preflight.py"],
        cwd=ROOT_DIR,
        text=True,
        capture_output=True,
        timeout=45,
        env=env,
    )


def parse_stdout(completed: subprocess.CompletedProcess[str]) -> dict[str, object]:
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"preflight stdout was not JSON: {exc}: {completed.stdout[:500]}") from exc
    if not isinstance(payload, dict):
        raise AssertionError("preflight stdout did not decode to an object")
    return payload


def main() -> int:
    local_live = run_preflight(
        {
            "APP_ENV": "local",
            "EXCHANGE_MODE": "live_guarded",
            "ENABLE_BINANCE_LIVE": "true",
            "BINANCE_PLACE_LIVE_ORDERS": "true",
            "BINANCE_LIVE_API_KEY": "dummy-live-key",
            "BINANCE_LIVE_API_SECRET": "dummy-live-secret",
            "LIVE_TRADING_CONFIRMATION": "I_UNDERSTAND_LIVE_RISK",
        }
    )
    if local_live.returncode == 0:
        return fail("preflight allowed live_guarded while APP_ENV=local")
    try:
        local_payload = parse_stdout(local_live)
    except AssertionError as exc:
        return fail(str(exc))
    local_errors = local_payload.get("errors") or []
    if not any("APP_ENV=server" in str(item) for item in local_errors):
        return fail(f"local live preflight did not require APP_ENV=server: {local_errors}")

    server_missing_auth = run_preflight(
        {
            "APP_ENV": "server",
            "TRADER_BIND_IP": "100.64.0.10",
            "EXCHANGE_MODE": "paper",
        }
    )
    if server_missing_auth.returncode == 0:
        return fail("preflight allowed APP_ENV=server without Basic Auth")
    try:
        auth_payload = parse_stdout(server_missing_auth)
    except AssertionError as exc:
        return fail(str(exc))
    auth_errors = auth_payload.get("errors") or []
    if not any("APP_BASIC_AUTH_USER" in str(item) for item in auth_errors):
        return fail(f"server preflight did not require Basic Auth: {auth_errors}")

    print(
        json.dumps(
            {
                "ok": True,
                "local_live_errors": local_errors,
                "server_auth_errors": auth_errors,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
