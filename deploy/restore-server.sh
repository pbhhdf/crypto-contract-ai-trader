#!/usr/bin/env bash
set -euo pipefail

BACKUP_PATH="${1:-}"

if [[ -z "${BACKUP_PATH}" ]]; then
  echo "Usage: bash deploy/restore-server.sh reports/backups/trader-state-backup-YYYYMMDDTHHMMSSZ.zip" >&2
  exit 2
fi

docker compose -f deploy/docker-compose.yml down
python3 scripts/restore_state.py \
  --backup "${BACKUP_PATH}" \
  --confirm RESTORE_TRADER_STATE
docker compose -f deploy/docker-compose.yml up -d

cat <<EOF

Restore completed and service restarted.
Run: python3 scripts/preflight.py
Run: TRADER_BASE_URL=http://127.0.0.1:8787 python3 scripts/run_all_checks.py

EOF
