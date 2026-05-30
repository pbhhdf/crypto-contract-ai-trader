from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
REPORT_DIR = ROOT_DIR / "reports"
DB_PATH = DATA_DIR / "trader.db"


def utc_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_sqlite_backup(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if not source.exists():
        return
    src = sqlite3.connect(source)
    dst = sqlite3.connect(target)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()


def add_file(zf: zipfile.ZipFile, path: Path, arcname: str, manifest: list[dict[str, object]]) -> None:
    if not path.exists() or not path.is_file():
        return
    zf.write(path, arcname)
    manifest.append(
        {
            "path": arcname,
            "bytes": path.stat().st_size,
            "sha256": file_sha256(path),
        }
    )


def fail(message: str) -> int:
    print(f"FAILED: {message}", file=sys.stderr)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a restorable backup of trader runtime state.")
    parser.add_argument("--output-dir", default=str(REPORT_DIR / "backups"))
    parser.add_argument("--include-env-example", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    slug = utc_slug()
    backup_path = output_dir / f"trader-state-backup-{slug}.zip"
    manifest: list[dict[str, object]] = []

    with tempfile.TemporaryDirectory(prefix="trader-backup-") as tmp_raw:
        tmp = Path(tmp_raw)
        db_copy = tmp / "trader.db"
        copy_sqlite_backup(DB_PATH, db_copy)
        manifest_payload = {
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "project_root": str(ROOT_DIR),
            "source_db": str(DB_PATH),
            "notes": [
                "Runtime secrets are not included.",
                "Restore by stopping the service, replacing data/trader.db, then starting the service.",
            ],
        }
        manifest_file = tmp / "backup-manifest.json"
        manifest_file.write_text(json.dumps(manifest_payload, ensure_ascii=False, indent=2), encoding="utf-8")

        with zipfile.ZipFile(backup_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            add_file(zf, db_copy, "data/trader.db", manifest)
            add_file(zf, manifest_file, "backup-manifest.json", manifest)
            for pattern in ("local-readiness-*.json", "go-live-report-*.json", "go-live-report-*.md"):
                for report in sorted(REPORT_DIR.glob(pattern))[-5:]:
                    add_file(zf, report, f"reports/{report.name}", manifest)
            if args.include_env_example:
                add_file(zf, ROOT_DIR / ".env.example", ".env.example", manifest)
                add_file(zf, ROOT_DIR / "deploy" / "server.env.example", "deploy/server.env.example", manifest)
            summary = {
                "created_at": manifest_payload["created_at"],
                "files": manifest,
                "archive_sha256_pending": True,
            }
            zf.writestr("backup-summary.json", json.dumps(summary, ensure_ascii=False, indent=2))

    if not backup_path.exists() or backup_path.stat().st_size == 0:
        return fail("backup archive was not created")
    archive_sha = file_sha256(backup_path)
    print(
        json.dumps(
            {
                "ok": True,
                "backup_path": str(backup_path),
                "bytes": backup_path.stat().st_size,
                "sha256": archive_sha,
                "file_count": len(manifest),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
