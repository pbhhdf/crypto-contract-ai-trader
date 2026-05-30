#!/usr/bin/env bash
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root: sudo bash deploy/setup-ubuntu-time-sync.sh" >&2
  exit 1
fi

REPO_ROOT="${REPO_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

apt-get update
apt-get install -y ca-certificates curl chrony

install -d -m 0755 /etc/chrony/conf.d
cat >/etc/chrony/conf.d/crypto-contract-ai-trader.conf <<'EOF'
# Crypto Contract AI Trader live-order preflight.
# Binance signed requests are timestamp-sensitive; keep wall-clock drift small.
pool time.cloudflare.com iburst
pool ntp.ubuntu.com iburst
makestep 0.25 10
rtcsync
EOF

timedatectl set-ntp true || true
systemctl enable --now chrony
systemctl restart chrony

if command -v chronyc >/dev/null 2>&1; then
  chronyc -a 'burst 4/4' || true
  chronyc -a makestep || true
  chronyc tracking || true
  chronyc sources -v || true
fi

cd "${REPO_ROOT}"
if command -v python3 >/dev/null 2>&1; then
  BINANCE_TIME_DRIFT_REQUIRE_PASS=true python3 scripts/check_binance_time_drift.py
else
  echo "python3 is not installed; run BINANCE_TIME_DRIFT_REQUIRE_PASS=true python3 scripts/check_binance_time_drift.py after Python is available." >&2
fi

cat <<'EOF'

Time synchronization baseline is ready.

Before enabling live mode, this command must pass:
BINANCE_TIME_DRIFT_REQUIRE_PASS=true python3 scripts/check_binance_time_drift.py

EOF
