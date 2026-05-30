#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="${REPO_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "${REPO_ROOT}"

COMPOSE_FILE="${COMPOSE_FILE:-deploy/docker-compose.yml}"
ENV_FILE="${ENV_FILE:-.env}"
APP_PORT_DEFAULT="8787"

fail() {
  echo "FAILED: $*" >&2
  exit 1
}

get_env() {
  local key="$1"
  local default="${2:-}"
  if [ -n "${!key:-}" ]; then
    printf '%s' "${!key}"
    return
  fi
  if [ -f "${ENV_FILE}" ]; then
    local raw
    raw="$(grep -E "^${key}=" "${ENV_FILE}" | tail -n 1 | cut -d= -f2- || true)"
    if [ -n "${raw}" ]; then
      raw="${raw%\"}"
      raw="${raw#\"}"
      raw="${raw%\'}"
      raw="${raw#\'}"
      printf '%s' "${raw}"
      return
    fi
  fi
  printf '%s' "${default}"
}

require_env_file() {
  [ -f "${ENV_FILE}" ] || fail "Missing ${ENV_FILE}. Copy deploy/server.env.example to .env and fill server secrets first."
}

validate_server_env() {
  local app_env app_user app_password bind_ip operator_shell operator_backup live_enabled live_places live_mode
  app_env="$(get_env APP_ENV)"
  app_user="$(get_env APP_BASIC_AUTH_USER)"
  app_password="$(get_env APP_BASIC_AUTH_PASSWORD)"
  bind_ip="$(get_env TRADER_BIND_IP 127.0.0.1)"
  operator_shell="$(get_env AI_OPERATOR_ALLOW_SHELL false)"
  operator_backup="$(get_env AI_OPERATOR_BACKUP_BEFORE_SHELL true)"
  live_enabled="$(get_env ENABLE_BINANCE_LIVE false)"
  live_places="$(get_env BINANCE_PLACE_LIVE_ORDERS false)"
  live_mode="$(get_env EXCHANGE_MODE paper)"

  [ "${app_env}" = "server" ] || fail "APP_ENV must be server for this deployment script."
  [ -n "${app_user}" ] || fail "APP_BASIC_AUTH_USER is required on the server."
  [ -n "${app_password}" ] || fail "APP_BASIC_AUTH_PASSWORD is required on the server."
  [ "${#app_password}" -ge 16 ] || fail "APP_BASIC_AUTH_PASSWORD must be at least 16 characters."
  [[ "${app_password}" != *"<"* ]] || fail "APP_BASIC_AUTH_PASSWORD still looks like a placeholder."
  [ -n "${bind_ip}" ] || fail "TRADER_BIND_IP is required. Use the Tailscale IPv4 or 127.0.0.1 behind a tunnel."
  [ "${bind_ip}" != "0.0.0.0" ] || fail "TRADER_BIND_IP=0.0.0.0 is not allowed for the Tailscale-first server profile."

  if [ "${operator_shell}" = "true" ] && [ "${operator_backup}" != "true" ]; then
    fail "AI_OPERATOR_BACKUP_BEFORE_SHELL=true is required when AI_OPERATOR_ALLOW_SHELL=true."
  fi

  if { [ "${live_enabled}" = "true" ] || [ "${live_places}" = "true" ] || [ "${live_mode}" = "live_guarded" ]; } \
    && [ "${TRADER_ALLOW_LIVE_DEPLOY:-false}" != "true" ]; then
    fail "Live flags are present. Set TRADER_ALLOW_LIVE_DEPLOY=true to run the pre-arm live verifier during deployment."
  fi
}

wait_for_health() {
  local port base_url
  port="$(get_env APP_PORT "${APP_PORT_DEFAULT}")"
  base_url="${TRADER_BASE_URL:-http://127.0.0.1:${port}}"
  export TRADER_BASE_URL="${base_url}"
  export TRADER_AUTH_USER="${TRADER_AUTH_USER:-$(get_env APP_BASIC_AUTH_USER)}"
  export TRADER_AUTH_PASSWORD="${TRADER_AUTH_PASSWORD:-$(get_env APP_BASIC_AUTH_PASSWORD)}"

  python3 - <<'PY'
from __future__ import annotations

import base64
import json
import os
import time
from urllib.request import Request, urlopen

base_url = os.environ["TRADER_BASE_URL"].rstrip("/")
auth_user = os.environ.get("TRADER_AUTH_USER", "")
auth_password = os.environ.get("TRADER_AUTH_PASSWORD", "")
deadline = time.time() + int(os.environ.get("TRADER_HEALTH_WAIT_SECONDS", "90"))
headers = {"Accept": "application/json"}
if auth_user and auth_password:
    token = base64.b64encode(f"{auth_user}:{auth_password}".encode("utf-8")).decode("ascii")
    headers["Authorization"] = f"Basic {token}"

last_error = ""
while time.time() < deadline:
    try:
        request = Request(f"{base_url}/api/health", headers=headers)
        with urlopen(request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if payload.get("ok") is True:
            print(json.dumps({"ok": True, "base_url": base_url}, ensure_ascii=False))
            raise SystemExit(0)
        last_error = f"unexpected payload: {payload!r}"
    except Exception as exc:  # noqa: BLE001 - health polling should report the final failure.
        last_error = f"{exc.__class__.__name__}: {exc}"
    time.sleep(2)

print(json.dumps({"ok": False, "base_url": base_url, "error": last_error}, ensure_ascii=False))
raise SystemExit(1)
PY
}

require_env_file
validate_server_env
if { [ "$(get_env ENABLE_BINANCE_LIVE false)" = "true" ] || [ "$(get_env BINANCE_PLACE_LIVE_ORDERS false)" = "true" ] || [ "$(get_env EXCHANGE_MODE paper)" = "live_guarded" ]; }; then
  python3 scripts/live_env_profile.py --env-file "${ENV_FILE}" --target live_guarded --strict
else
  python3 scripts/live_env_profile.py --env-file "${ENV_FILE}" --target mvp_server --strict
fi

mkdir -p data reports reports/backups

docker compose -f "${COMPOSE_FILE}" up -d --build
wait_for_health

bash deploy/verify-server.sh
python3 scripts/server_go_live_audit.py
python3 scripts/export_live_launch_plan.py
python3 scripts/export_live_ops_handoff.py
python3 scripts/export_server_bundle.py
python3 scripts/export_live_env_pack.py
python3 scripts/export_live_launch_kit.py
bash deploy/backup-server.sh

if [ "${TRADER_ALLOW_LIVE_DEPLOY:-false}" = "true" ]; then
  TRADER_FINAL_LIVE_REQUIRE_ARMED=false python3 scripts/check_final_live_ready.py
fi

cat <<'EOF'

Server deployment completed.

Review:
- reports/server-go-live-audit-*.md
- reports/go-live-report-*.md
- reports/live-launch-plan-*.md
- reports/live-ops-handoff-*.md
- reports/server-bundles/*.zip
- reports/live-env-packs/*.zip
- reports/live-launch-kits/*.zip
- reports/backups/trader-state-backup-*.zip

To gather all available pre-live evidence and run real Testnet drills:
python3 scripts/run_server_live_readiness.py --run-testnet-drill --target-cycles 24 --interval-seconds 60

Live trading remains blocked unless the Go-live gate, live attestation,
real Testnet drill cycles, strategy walk-forward gate, and short live arming
all pass on the server.

EOF
