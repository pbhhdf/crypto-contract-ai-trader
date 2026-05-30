from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def fail(message: str) -> int:
    print(f"FAILED: {message}", file=sys.stderr)
    return 1


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="trader-backup-check-") as tmp:
        result = subprocess.run(
            [sys.executable, "scripts/backup_state.py", "--output-dir", tmp],
            cwd=ROOT_DIR,
            text=True,
            capture_output=True,
            timeout=60,
        )
        if result.returncode != 0:
            return fail(result.stderr.strip() or result.stdout.strip() or "backup_state.py failed")
        payload = json.loads(result.stdout)
        backup_path = Path(payload["backup_path"])
        if not backup_path.exists() or backup_path.stat().st_size == 0:
            return fail(f"backup archive missing: {backup_path}")
        with zipfile.ZipFile(backup_path) as zf:
            names = set(zf.namelist())
            for required in {"data/trader.db", "backup-manifest.json", "backup-summary.json"}:
                if required not in names:
                    return fail(f"backup archive missing {required}")
            bad = zf.testzip()
            if bad:
                return fail(f"backup archive has a corrupt member: {bad}")
        print(json.dumps({"ok": True, **payload}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
