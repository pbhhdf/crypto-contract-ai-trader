from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import socket
import sqlite3
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
REPORT_DIR = ROOT_DIR / "reports"
DB_PATH = DATA_DIR / "trader.db"
DB_MEMBER = "data/trader.db"
CONFIRMATION = "RESTORE_TRADER_STATE"


def utc_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def fail(message: str) -> int:
    print(f"FAILED: {message}", file=sys.stderr)
    return 1


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def bytes_sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def read_json_member(zf: zipfile.ZipFile, name: str) -> dict[str, Any]:
    if name not in zf.namelist():
        return {}
    try:
        return json.loads(zf.read(name).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}


def expected_sha_from_summary(summary: dict[str, Any], member: str) -> str | None:
    files = summary.get("files")
    if not isinstance(files, list):
        return None
    for item in files:
        if isinstance(item, dict) and item.get("path") == member and isinstance(item.get("sha256"), str):
            return item["sha256"]
    return None


def sqlite_integrity(path: Path) -> str:
    conn = sqlite3.connect(path)
    try:
        row = conn.execute("PRAGMA integrity_check").fetchone()
    finally:
        conn.close()
    return str(row[0] if row else "")


def copy_sqlite_or_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        src = sqlite3.connect(source)
        dst = sqlite3.connect(target)
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()
    except sqlite3.Error:
        shutil.copy2(source, target)


def service_port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.35):
            return True
    except OSError:
        return False


def extract_db_to_temp(zf: zipfile.ZipFile, tmp: Path) -> Path:
    restored = tmp / "trader.db"
    with zf.open(DB_MEMBER) as src, restored.open("wb") as dst:
        shutil.copyfileobj(src, dst)
    return restored


def main() -> int:
    parser = argparse.ArgumentParser(description="Restore trader runtime state from a backup zip.")
    parser.add_argument("--backup", required=True, help="Path to trader-state-backup-*.zip")
    parser.add_argument("--db-path", default=str(DB_PATH), help="Target SQLite database path.")
    parser.add_argument("--pre-restore-dir", default=str(REPORT_DIR / "backups"), help="Directory for pre-restore copies.")
    parser.add_argument("--confirm", default="", help=f"Required for non-dry-run restores: {CONFIRMATION}")
    parser.add_argument("--dry-run", action="store_true", help="Validate the backup without replacing the target database.")
    parser.add_argument("--allow-running", action="store_true", help="Allow restoring while the local HTTP port is reachable.")
    parser.add_argument("--service-host", default="127.0.0.1")
    parser.add_argument("--service-port", type=int, default=int(os.getenv("APP_PORT", "8787")))
    args = parser.parse_args()

    backup_path = Path(args.backup)
    target_db = Path(args.db_path)
    pre_restore_dir = Path(args.pre_restore_dir)
    if not backup_path.exists() or not backup_path.is_file():
        return fail(f"backup archive not found: {backup_path}")
    if backup_path.suffix.lower() != ".zip":
        return fail("backup archive must be a .zip file")
    if not args.dry_run and args.confirm != CONFIRMATION:
        return fail(f"non-dry-run restore requires --confirm {CONFIRMATION}")

    default_target = target_db.resolve(strict=False) == DB_PATH.resolve(strict=False)
    target_existed_before = target_db.exists()
    running = service_port_open(args.service_host, args.service_port)
    if not args.dry_run and default_target and running and not args.allow_running:
        return fail(
            f"service appears to be running on {args.service_host}:{args.service_port}; stop it first or pass --allow-running"
        )

    with tempfile.TemporaryDirectory(prefix="trader-restore-") as tmp_raw:
        tmp = Path(tmp_raw)
        try:
            with zipfile.ZipFile(backup_path) as zf:
                names = set(zf.namelist())
                if DB_MEMBER not in names:
                    return fail(f"backup archive missing {DB_MEMBER}")
                if "backup-summary.json" not in names:
                    return fail("backup archive missing backup-summary.json")
                if "backup-manifest.json" not in names:
                    return fail("backup archive missing backup-manifest.json")
                bad = zf.testzip()
                if bad:
                    return fail(f"backup archive has a corrupt member: {bad}")
                summary = read_json_member(zf, "backup-summary.json")
                expected_sha = expected_sha_from_summary(summary, DB_MEMBER)
                db_payload = zf.read(DB_MEMBER)
                actual_sha = bytes_sha256(db_payload)
                if expected_sha and expected_sha != actual_sha:
                    return fail(f"{DB_MEMBER} sha256 mismatch")
                extracted_db = tmp / "trader.db"
                extracted_db.write_bytes(db_payload)
        except zipfile.BadZipFile:
            return fail("backup archive is not a valid zip file")

        integrity = sqlite_integrity(extracted_db)
        if integrity != "ok":
            return fail(f"restored database failed integrity_check: {integrity}")

        pre_restore_copy: Path | None = None
        replaced = False
        if not args.dry_run:
            if target_db.exists():
                pre_restore_dir.mkdir(parents=True, exist_ok=True)
                pre_restore_copy = pre_restore_dir / f"pre-restore-{target_db.stem}-{utc_slug()}.db"
                copy_sqlite_or_file(target_db, pre_restore_copy)
            target_db.parent.mkdir(parents=True, exist_ok=True)
            replacement = target_db.with_name(f".{target_db.name}.restore-{utc_slug()}.tmp")
            shutil.copy2(extracted_db, replacement)
            os.replace(replacement, target_db)
            replaced = True

        payload = {
            "ok": True,
            "dry_run": args.dry_run,
            "restored": replaced,
            "backup_path": str(backup_path),
            "backup_sha256": file_sha256(backup_path),
            "target_db": str(target_db),
            "target_existed_before": target_existed_before,
            "pre_restore_copy": str(pre_restore_copy) if pre_restore_copy else None,
            "service_running_detected": running,
            "sqlite_integrity": integrity,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
