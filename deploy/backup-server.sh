#!/usr/bin/env bash
set -euo pipefail

OUTPUT_DIR="${1:-reports/backups}"

python3 scripts/backup_state.py --output-dir "${OUTPUT_DIR}" --include-env-example

cat <<EOF

Backup completed.
Copy the generated zip off the server before enabling or changing live trading.

EOF
