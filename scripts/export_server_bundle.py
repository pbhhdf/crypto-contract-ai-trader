from __future__ import annotations

import argparse
import hashlib
import json
import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "reports" / "server-bundles"
INCLUDE_ROOT_FILES = {
    ".dockerignore",
    ".env.example",
    "Dockerfile",
    "README.md",
    "requirements.txt",
}
INCLUDE_DIRS = {
    "app",
    "deploy",
    "docs",
    "scripts",
}
EXCLUDE_DIR_NAMES = {
    "__pycache__",
    ".git",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
}
EXCLUDE_FILE_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".sqlite",
    ".sqlite3",
    ".db",
    ".zip",
}
EXCLUDE_FILE_NAMES = {
    ".env",
}


def utc_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def should_include(path: Path) -> bool:
    relative = path.relative_to(ROOT_DIR)
    parts = relative.parts
    if any(part in EXCLUDE_DIR_NAMES for part in parts):
        return False
    if any(part in {"data", "reports"} for part in parts):
        return False
    if path.name in EXCLUDE_FILE_NAMES:
        return False
    if path.suffix.lower() in EXCLUDE_FILE_SUFFIXES:
        return False
    if len(parts) == 1:
        return path.name in INCLUDE_ROOT_FILES
    return parts[0] in INCLUDE_DIRS


def iter_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT_DIR.rglob("*"):
        if path.is_file() and should_include(path):
            files.append(path)
    return sorted(files, key=lambda item: item.relative_to(ROOT_DIR).as_posix())


def write_bundle(output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    bundle_name = f"crypto-contract-ai-trader-server-bundle-{utc_slug()}.zip"
    bundle_path = output_dir / bundle_name
    files = iter_files()
    manifest = {
        "created_at": created_at,
        "project_root": str(ROOT_DIR),
        "bundle_name": bundle_name,
        "security_note": (
            "This bundle intentionally excludes .env, data/, reports/, SQLite databases, "
            "runtime backups, and generated audit artifacts."
        ),
        "recommended_server": {
            "os": "Ubuntu Server 24.04 LTS",
            "arch": "x86_64/amd64",
            "cpu": "4 vCPU",
            "ram": "16 GB",
            "disk": "160 GB SSD",
            "access": "Tailscale private network; do not expose port 8787 publicly.",
        },
        "files": [],
    }
    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for file_path in files:
            relative = file_path.relative_to(ROOT_DIR).as_posix()
            stat = file_path.stat()
            digest = sha256_file(file_path)
            archive.write(file_path, relative)
            manifest["files"].append(
                {
                    "path": relative,
                    "bytes": stat.st_size,
                    "sha256": digest,
                }
            )
        manifest_bytes = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
        archive.writestr("SERVER_BUNDLE_MANIFEST.json", manifest_bytes)

    return {
        "ok": True,
        "bundle_path": str(bundle_path),
        "bytes": bundle_path.stat().st_size,
        "sha256": sha256_file(bundle_path),
        "file_count": len(files),
        "manifest_path": "SERVER_BUNDLE_MANIFEST.json",
        "excluded": [".env", "data/", "reports/", "*.db", "*.zip", "__pycache__/"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Export a deployable server bundle without secrets or runtime data.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory to place the server bundle zip.")
    args = parser.parse_args()
    result = write_bundle(Path(args.output_dir).resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
