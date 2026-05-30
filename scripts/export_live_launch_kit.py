from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT_DIR / "reports"
DEFAULT_OUTPUT_DIR = REPORT_DIR / "live-launch-kits"
PYTHON = sys.executable
FORBIDDEN_MARKERS = ("sk-proj-", "sk-test-", "live-secret-value", "testnet-secret-value")


def utc_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_json_step(name: str, command: list[str], timeout: int = 180) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=ROOT_DIR,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    result = {
        "name": name,
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }
    if completed.returncode != 0:
        raise RuntimeError(f"{name} failed: {completed.stderr or completed.stdout or completed.returncode}")
    try:
        payload = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{name} did not print JSON: {exc}") from exc
    result["payload"] = payload
    return result


def safe_existing_path(path_value: Any) -> Path | None:
    if not path_value:
        return None
    path = Path(str(path_value)).resolve()
    if not path.exists() or not path.is_file():
        return None
    try:
        path.relative_to(ROOT_DIR)
    except ValueError as exc:
        raise RuntimeError(f"refusing to include path outside project root: {path}") from exc
    return path


def add_file(archive: zipfile.ZipFile, file_path: Path, arcname: str, files: list[dict[str, Any]]) -> None:
    if file_path.suffix.lower() in {".json", ".md", ".txt"}:
        text = file_path.read_text(encoding="utf-8", errors="replace")
        for marker in FORBIDDEN_MARKERS:
            if marker in text:
                raise RuntimeError(f"refusing to package forbidden marker {marker!r} from {file_path}")
    archive.write(file_path, arcname)
    files.append(
        {
            "path": arcname,
            "source": str(file_path),
            "bytes": file_path.stat().st_size,
            "sha256": sha256_file(file_path),
        }
    )


def write_readme(manifest: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Live Launch Kit",
            "",
            f"- Created: `{manifest['created_at']}`",
            "- Purpose: copy one zip containing the deployable server bundle and latest live-readiness evidence.",
            "- Secrets: `.env`, databases, runtime data, and API secrets are intentionally not included.",
            "",
            "## Use Order",
            "",
            "1. Extract `server-bundle/*.zip` on the Ubuntu server.",
            "2. Copy `deploy/server.env.example` to `.env` and fill only on the server.",
            "3. Run `sudo bash deploy/setup-ubuntu-tailscale.sh` and `sudo bash deploy/setup-ubuntu-time-sync.sh`.",
            "4. Run `bash deploy/deploy-server.sh`.",
            "5. Run `python3 scripts/run_server_live_readiness.py --run-testnet-drill --target-cycles 24 --interval-seconds 60`.",
            "6. Review `evidence/live-ops-handoff-*.md` and `evidence/live-launch-plan-*.md` before any live flag change.",
            "7. Use `python3 scripts/run_guarded_live_pilot_once.py --plan-only` before the first live pilot.",
            "8. After a guarded pilot, run `python3 scripts/check_live_pilot_postflight.py` or `/live-postflight BTCUSDT` to review OMS, alerts, audit chain, exchange snapshot, and disarming evidence.",
            "9. Use `env-pack/*.zip` for stage-specific `.env` templates; fill placeholders only on the server.",
            "",
            "## Emergency Commands",
            "",
            "- `/panic-stop --confirm PANIC_STOP`",
            "- `/panic-stop --confirm PANIC_STOP --flatten --flatten-confirm FLATTEN_POSITIONS`",
            "- `python3 scripts/check_exchange_emergency.py`",
            "",
        ]
    )


def write_launch_kit(output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    slug = utc_slug()
    steps = [
        run_json_step("server_bundle", [PYTHON, "scripts/export_server_bundle.py"], timeout=120),
        run_json_step("go_live_report", [PYTHON, "scripts/export_go_live_report.py"], timeout=120),
        run_json_step("server_go_live_audit", [PYTHON, "scripts/server_go_live_audit.py"], timeout=240),
        run_json_step("live_launch_plan", [PYTHON, "scripts/export_live_launch_plan.py"], timeout=120),
        run_json_step("live_ops_handoff", [PYTHON, "scripts/export_live_ops_handoff.py"], timeout=120),
        run_json_step("live_env_pack", [PYTHON, "scripts/export_live_env_pack.py"], timeout=120),
    ]
    package_specs: list[tuple[str, Path | None]] = []
    for step in steps:
        payload = step.get("payload") or {}
        name = step["name"]
        if name == "server_bundle":
            package_specs.append((f"server-bundle/{Path(str(payload.get('bundle_path'))).name}", safe_existing_path(payload.get("bundle_path"))))
        elif name == "live_env_pack":
            package_specs.append((f"env-pack/{Path(str(payload.get('pack_path'))).name}", safe_existing_path(payload.get("pack_path"))))
        else:
            for key, folder in (("json_path", "evidence"), ("markdown_path", "evidence")):
                path = safe_existing_path(payload.get(key))
                if path:
                    package_specs.append((f"{folder}/{path.name}", path))

    manifest = {
        "created_at": created_at,
        "project_root": str(ROOT_DIR),
        "kit_name": f"crypto-contract-ai-trader-live-launch-kit-{slug}.zip",
        "security_note": "No .env, SQLite database, runtime data, API secret, or raw key material is intentionally included.",
        "steps": [
            {
                "name": step["name"],
                "returncode": step["returncode"],
                "payload": step.get("payload"),
            }
            for step in steps
        ],
        "files": [],
    }
    kit_path = output_dir / manifest["kit_name"]
    with zipfile.ZipFile(kit_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for arcname, file_path in package_specs:
            if file_path:
                add_file(archive, file_path, arcname, manifest["files"])
        readme = write_readme(manifest)
        archive.writestr("README-LIVE-LAUNCH-KIT.md", readme)
        manifest["files"].append(
            {
                "path": "README-LIVE-LAUNCH-KIT.md",
                "source": "generated",
                "bytes": len(readme.encode("utf-8")),
                "sha256": hashlib.sha256(readme.encode("utf-8")).hexdigest(),
            }
        )
        manifest_bytes = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
        archive.writestr("LIVE_LAUNCH_KIT_MANIFEST.json", manifest_bytes)

    return {
        "ok": True,
        "kit_path": str(kit_path),
        "bytes": kit_path.stat().st_size,
        "sha256": sha256_file(kit_path),
        "file_count": len(manifest["files"]),
        "manifest_path": "LIVE_LAUNCH_KIT_MANIFEST.json",
        "server_bundle": next((step.get("payload", {}).get("bundle_path") for step in steps if step["name"] == "server_bundle"), None),
        "excluded": [".env", "data/", "reports/*.db", "*.sqlite", "api secrets"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Export one zip with the server bundle and latest live-launch evidence.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory to place the live launch kit zip.")
    args = parser.parse_args()
    try:
        result = write_launch_kit(Path(args.output_dir).resolve())
    except Exception as exc:  # noqa: BLE001 - CLI should present packaging failures clearly.
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
