#!/usr/bin/env bash
set -euo pipefail

get_env() {
  local key="$1"
  local default="${2:-}"
  if [ -n "${!key:-}" ]; then
    printf '%s' "${!key}"
    return
  fi
  if [ -f .env ]; then
    local raw
    raw="$(grep -E "^${key}=" .env | tail -n 1 | cut -d= -f2- || true)"
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

APP_PORT_VALUE="$(get_env APP_PORT 8787)"
export TRADER_BASE_URL="${TRADER_BASE_URL:-http://127.0.0.1:${APP_PORT_VALUE}}"
export TRADER_AUTH_USER="${TRADER_AUTH_USER:-$(get_env APP_BASIC_AUTH_USER)}"
export TRADER_AUTH_PASSWORD="${TRADER_AUTH_PASSWORD:-$(get_env APP_BASIC_AUTH_PASSWORD)}"

python3 scripts/preflight.py
python3 scripts/live_env_profile.py --target live_guarded
python3 scripts/check_binance_time_drift.py
python3 scripts/check_ui_chinese.py
python3 scripts/run_all_checks.py
python3 scripts/server_go_live_audit.py
python3 scripts/export_live_launch_plan.py
python3 scripts/export_live_ops_handoff.py
python3 scripts/export_server_bundle.py
python3 scripts/export_live_env_pack.py
python3 scripts/export_live_launch_kit.py

if [ "${TRADER_CHECK_FINAL_LIVE_READY:-false}" = "true" ]; then
  python3 scripts/check_final_live_ready.py
fi

cat <<EOF

Server verification completed.
Base URL checked: ${TRADER_BASE_URL}

To run Binance testnet validation after adding testnet keys:
TRADER_CHECK_TESTNET=true python3 scripts/run_all_checks.py

To run the hard final live verifier after live_guarded is configured and armed:
TRADER_CHECK_FINAL_LIVE_READY=true bash deploy/verify-server.sh

The verification run also writes reports/server-go-live-audit-*.json/.md,
reports/live-launch-plan-*.json/.md, and reports/server-bundles/*.zip.
It also writes reports/live-ops-handoff-*.json/.md for the final operator runbook.
The live environment templates are written under reports/live-env-packs/*.zip.
The combined live launch kit is written under reports/live-launch-kits/*.zip.

EOF
