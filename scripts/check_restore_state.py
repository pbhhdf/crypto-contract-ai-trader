from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DB_PATH = ROOT_DIR / "data" / "trader.db"


def fail(message: str) -> int:
    print(f"FAILED: {message}", file=sys.stderr)
    return 1


def record_restore_drill(backup_path: Path) -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        conn.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            ("restore_state_drill_last_at", datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )
        conn.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            ("restore_state_drill_last_backup", str(backup_path)),
        )
        conn.commit()
    finally:
        conn.close()


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="trader-restore-check-") as tmp_raw:
        tmp = Path(tmp_raw)
        backup_result = subprocess.run(
            [sys.executable, "scripts/backup_state.py", "--output-dir", str(tmp / "backups")],
            cwd=ROOT_DIR,
            text=True,
            capture_output=True,
            timeout=60,
        )
        if backup_result.returncode != 0:
            return fail(backup_result.stderr.strip() or backup_result.stdout.strip() or "backup_state.py failed")
        backup_payload = json.loads(backup_result.stdout)
        backup_path = Path(backup_payload["backup_path"])

        dry_run = subprocess.run(
            [sys.executable, "scripts/restore_state.py", "--backup", str(backup_path), "--dry-run"],
            cwd=ROOT_DIR,
            text=True,
            capture_output=True,
            timeout=60,
        )
        if dry_run.returncode != 0:
            return fail(dry_run.stderr.strip() or dry_run.stdout.strip() or "restore_state.py dry-run failed")
        dry_payload = json.loads(dry_run.stdout)
        if not dry_payload.get("ok") or dry_payload.get("restored"):
            return fail("restore dry-run did not validate cleanly")

        missing_confirmation = subprocess.run(
            [sys.executable, "scripts/restore_state.py", "--backup", str(backup_path), "--db-path", str(tmp / "blocked.db")],
            cwd=ROOT_DIR,
            text=True,
            capture_output=True,
            timeout=60,
        )
        if missing_confirmation.returncode == 0:
            return fail("restore without confirmation was not rejected")

        target_db = tmp / "restored-trader.db"
        restore_result = subprocess.run(
            [
                sys.executable,
                "scripts/restore_state.py",
                "--backup",
                str(backup_path),
                "--db-path",
                str(target_db),
                "--pre-restore-dir",
                str(tmp / "pre-restore"),
                "--confirm",
                "RESTORE_TRADER_STATE",
            ],
            cwd=ROOT_DIR,
            text=True,
            capture_output=True,
            timeout=60,
        )
        if restore_result.returncode != 0:
            return fail(restore_result.stderr.strip() or restore_result.stdout.strip() or "restore_state.py restore failed")
        restore_payload = json.loads(restore_result.stdout)
        if not restore_payload.get("ok") or not restore_payload.get("restored"):
            return fail("restore did not report a completed restore")
        if not target_db.exists() or target_db.stat().st_size == 0:
            return fail("restored temp database is missing or empty")
        conn = sqlite3.connect(target_db)
        try:
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('settings', 'orders', 'audit_log')"
                )
            }
        finally:
            conn.close()
        if integrity != "ok":
            return fail(f"restored temp database integrity failed: {integrity}")
        if "settings" not in tables:
            return fail("restored temp database missing settings table")

        record_restore_drill(backup_path)

        print(
            json.dumps(
                {
                    "ok": True,
                    "backup_path": str(backup_path),
                    "dry_run": dry_payload,
                    "missing_confirmation_rejected": True,
                    "restore": restore_payload,
                    "tables_checked": sorted(tables),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
