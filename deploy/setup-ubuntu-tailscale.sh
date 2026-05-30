#!/usr/bin/env bash
set -euo pipefail

TRADER_PORT="${TRADER_PORT:-8787}"

if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root: sudo bash deploy/setup-ubuntu-tailscale.sh" >&2
  exit 1
fi

apt-get update
apt-get install -y ca-certificates curl git gnupg ufw chrony
systemctl enable --now chrony || true

if ! command -v docker >/dev/null 2>&1; then
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  . /etc/os-release
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
    >/etc/apt/sources.list.d/docker.list
  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi

systemctl enable --now docker

if ! command -v tailscale >/dev/null 2>&1; then
  curl -fsSL https://tailscale.com/install.sh | sh
fi

if ! tailscale status >/dev/null 2>&1; then
  if [ -n "${TAILSCALE_AUTHKEY:-}" ]; then
    tailscale up --ssh --authkey "${TAILSCALE_AUTHKEY}"
  else
    tailscale up --ssh
  fi
fi

TAILSCALE_IP="$(tailscale ip -4 | head -n 1)"
if [ -z "${TAILSCALE_IP}" ]; then
  echo "Could not detect a Tailscale IPv4 address." >&2
  exit 1
fi

ufw allow OpenSSH
ufw default deny incoming
ufw default allow outgoing
ufw allow in on tailscale0 to any port "${TRADER_PORT}" proto tcp
ufw --force enable

cat <<EOF

Host baseline is ready.

Use this value in .env:
TRADER_BIND_IP=${TAILSCALE_IP}

Then deploy from the repository root:
cp deploy/server.env.example .env
python3 - <<'PY'
from pathlib import Path
path = Path('.env')
text = path.read_text()
text = text.replace('<tailscale-ipv4>', '${TAILSCALE_IP}')
path.write_text(text)
PY
docker compose -f deploy/docker-compose.yml up -d --build

EOF
