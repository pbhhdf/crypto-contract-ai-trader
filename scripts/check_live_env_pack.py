from __future__ import annotations

import json
import subprocess
import sys
import zipfile
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
REQUIRED_STAGES = {"mvp_server", "testnet_validate", "testnet_place", "live_guarded"}


def fail(message: str, payload: object | None = None) -> int:
    print(f"FAILED: {message}", file=sys.stderr)
    if payload is not None:
        print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
    return 1


def main() -> int:
    completed = subprocess.run(
        [sys.executable, "scripts/export_live_env_pack.py"],
        cwd=ROOT_DIR,
        text=True,
        capture_output=True,
        timeout=60,
    )
    if completed.returncode != 0:
        return fail("export_live_env_pack.py failed", {"stdout": completed.stdout, "stderr": completed.stderr})
    try:
        payload = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError as exc:
        return fail(f"live env pack exporter did not print JSON: {exc}", completed.stdout)
    pack_path = Path(str(payload.get("pack_path") or ""))
    if not pack_path.exists() or pack_path.stat().st_size < 8_000:
        return fail("live env pack is missing or unexpectedly small", payload)
    with zipfile.ZipFile(pack_path) as archive:
        names = set(archive.namelist())
        required = {"LIVE_ENV_PACK_MANIFEST.json", "README-LIVE-ENV-PACK.md"} | {
            f"env/{stage}.env" for stage in REQUIRED_STAGES
        }
        missing = sorted(required - names)
        if missing:
            return fail("live env pack is missing required entries", {"missing": missing, "names": sorted(names)})
        manifest = json.loads(archive.read("LIVE_ENV_PACK_MANIFEST.json").decode("utf-8"))
        if set(manifest.get("stages") or []) != REQUIRED_STAGES:
            return fail("live env pack manifest stages are wrong", manifest)
        live_env = archive.read("env/live_guarded.env").decode("utf-8")
        for needle in (
            "EXCHANGE_MODE=live_guarded",
            "ENABLE_BINANCE_LIVE=true",
            "BINANCE_PLACE_LIVE_ORDERS=true",
            "LIVE_TRADING_CONFIRMATION=I_UNDERSTAND_LIVE_RISK",
            "AI_OPERATOR_ALLOW_FILE_WRITE=true",
            "AI_OPERATOR_ALLOW_SHELL=true",
            "AI_OPERATOR_BACKUP_BEFORE_SHELL=true",
            "TRADER_BIND_IP=<tailscale-ipv4>",
        ):
            if needle not in live_env:
                return fail(f"live_guarded template is missing {needle}", live_env[:2000])
        text_payload = "\n".join(
            archive.read(name).decode("utf-8", errors="replace")
            for name in names
            if name.endswith((".env", ".json", ".md", ".txt"))
        )
        for forbidden in ("sk-proj-", "sk-test-", "live-secret-value", "testnet-secret-value"):
            if forbidden in text_payload:
                return fail(f"live env pack leaked forbidden marker {forbidden}", sorted(names))
    print(
        json.dumps(
            {
                "ok": True,
                "pack_path": str(pack_path),
                "entry_count": len(names),
                "bytes": pack_path.stat().st_size,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
