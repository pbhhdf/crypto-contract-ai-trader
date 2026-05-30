from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "reports" / "live-env-packs"
SERVER_ENV_EXAMPLE = ROOT_DIR / "deploy" / "server.env.example"
FORBIDDEN_MARKERS = ("sk-proj-", "sk-test-", "live-secret-value", "testnet-secret-value")


def utc_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


BASE_OVERRIDES: dict[str, str] = {
    "APP_ENV": "server",
    "APP_HOST": "0.0.0.0",
    "APP_PORT": "8787",
    "APP_BASIC_AUTH_USER": "admin",
    "APP_BASIC_AUTH_PASSWORD": "<choose-long-random-password>",
    "TRADER_BIND_IP": "<tailscale-ipv4>",
    "AI_PROVIDER": "rules",
    "AI_OPERATOR_ENABLED": "true",
    "AI_OPERATOR_PROVIDER": "rules",
    "AI_OPERATOR_ALLOW_FILE_READ": "true",
    "AI_OPERATOR_ALLOW_FILE_WRITE": "true",
    "AI_OPERATOR_ALLOW_SHELL": "true",
    "AI_OPERATOR_APPLY_MODEL_FILE_ACTIONS": "true",
    "AI_OPERATOR_SNAPSHOT_WRITES": "true",
    "AI_OPERATOR_BACKUP_BEFORE_SHELL": "true",
    "GO_LIVE_REQUIRE_ALERT_WEBHOOK": "true",
    "GO_LIVE_REQUIRE_PRIVATE_STREAM": "true",
    "LIVE_ARMING_MAX_SECONDS": "900",
    "LIVE_ARMING_MAX_ORDERS": "1",
    "MAX_ORDER_NOTIONAL_USDT": "50",
    "LIVE_PILOT_MAX_WALLET_USDT": "500",
    "BINANCE_SYNC_MARGIN_TYPE_BEFORE_ORDER": "true",
    "BINANCE_TARGET_MARGIN_TYPE": "ISOLATED",
    "BINANCE_SYNC_LEVERAGE_BEFORE_ORDER": "true",
    "BINANCE_REQUIRE_ONE_WAY_POSITION_MODE": "true",
}


STAGE_OVERRIDES: dict[str, dict[str, str]] = {
    "mvp_server": {
        "EXCHANGE_MODE": "paper",
        "ENABLE_BINANCE_TESTNET": "false",
        "BINANCE_PLACE_TESTNET_ORDERS": "false",
        "ENABLE_BINANCE_LIVE": "false",
        "BINANCE_PLACE_LIVE_ORDERS": "false",
        "LIVE_TRADING_CONFIRMATION": "",
    },
    "testnet_validate": {
        "EXCHANGE_MODE": "binance_testnet_validate",
        "ENABLE_BINANCE_TESTNET": "true",
        "BINANCE_API_KEY": "<binance-futures-testnet-key>",
        "BINANCE_API_SECRET": "<binance-futures-testnet-secret>",
        "BINANCE_PLACE_TESTNET_ORDERS": "false",
        "ENABLE_BINANCE_LIVE": "false",
        "BINANCE_PLACE_LIVE_ORDERS": "false",
        "LIVE_TRADING_CONFIRMATION": "",
    },
    "testnet_place": {
        "EXCHANGE_MODE": "binance_testnet_place_order",
        "ENABLE_BINANCE_TESTNET": "true",
        "BINANCE_API_KEY": "<binance-futures-testnet-key>",
        "BINANCE_API_SECRET": "<binance-futures-testnet-secret>",
        "BINANCE_PLACE_TESTNET_ORDERS": "true",
        "ENABLE_BINANCE_LIVE": "false",
        "BINANCE_PLACE_LIVE_ORDERS": "false",
        "LIVE_TRADING_CONFIRMATION": "",
    },
    "live_guarded": {
        "EXCHANGE_MODE": "live_guarded",
        "ENABLE_BINANCE_TESTNET": "true",
        "BINANCE_API_KEY": "<binance-futures-testnet-key>",
        "BINANCE_API_SECRET": "<binance-futures-testnet-secret>",
        "BINANCE_PLACE_TESTNET_ORDERS": "true",
        "ENABLE_BINANCE_LIVE": "true",
        "BINANCE_LIVE_API_KEY": "<binance-live-key>",
        "BINANCE_LIVE_API_SECRET": "<binance-live-secret>",
        "BINANCE_PLACE_LIVE_ORDERS": "true",
        "LIVE_TRADING_CONFIRMATION": "I_UNDERSTAND_LIVE_RISK",
        "ALERT_WEBHOOK_ENABLED": "true",
        "ALERT_WEBHOOK_URL": "<internal-webhook-url>",
    },
}


def render_stage_env(stage: str) -> str:
    if not SERVER_ENV_EXAMPLE.exists():
        raise RuntimeError("deploy/server.env.example is missing")
    overrides = dict(BASE_OVERRIDES)
    overrides.update(STAGE_OVERRIDES[stage])
    seen: set[str] = set()
    rendered: list[str] = [
        f"# Generated live environment template: {stage}",
        "# Copy this file to .env on the Ubuntu server and replace every <placeholder> on the server only.",
        "# Do not commit filled secrets. Keep access behind Tailscale and Basic Auth.",
        "",
    ]
    for raw_line in SERVER_ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#") or "=" not in raw_line:
            rendered.append(raw_line)
            continue
        key, _value = raw_line.split("=", 1)
        clean_key = key.strip()
        if clean_key in overrides:
            rendered.append(f"{clean_key}={overrides[clean_key]}")
            seen.add(clean_key)
        else:
            rendered.append(raw_line)
    missing = [(key, value) for key, value in overrides.items() if key not in seen]
    if missing:
        rendered.append("")
        rendered.append("# Added by export_live_env_pack.py")
        for key, value in sorted(missing):
            rendered.append(f"{key}={value}")
    return "\n".join(rendered).rstrip() + "\n"


def scan_text(name: str, text: str) -> None:
    for marker in FORBIDDEN_MARKERS:
        if marker in text:
            raise RuntimeError(f"refusing to package forbidden marker {marker!r} in {name}")


def write_readme(created_at: str) -> str:
    return "\n".join(
        [
            "# Live Environment Pack",
            "",
            f"- Created: `{created_at}`",
            "- Purpose: provide stage-specific `.env` templates for Ubuntu server cutover.",
            "- Secrets: this pack contains placeholders only. Fill keys and passwords on the server.",
            "",
            "## Stages",
            "",
            "- `env/mvp_server.env`: paper trading and high-permission Codex operator, live disabled.",
            "- `env/testnet_validate.env`: Binance Futures Testnet `/fapi/v1/order/test`, no real testnet order.",
            "- `env/testnet_place.env`: real Binance Futures Testnet order/cancel drills.",
            "- `env/live_guarded.env`: guarded Binance live profile; still requires go-live gate, attestation, and short arming.",
            "",
            "## Server Use",
            "",
            "1. Extract this pack on the server.",
            "2. Copy the desired stage file to `.env`.",
            "3. Replace every `<placeholder>` on the server only.",
            "4. Run `python3 scripts/live_env_profile.py --env-file .env --target <stage> --strict`.",
            "5. Run `python3 scripts/run_server_live_readiness.py --run-testnet-drill --target-cycles 24 --interval-seconds 60` before live.",
            "",
            "This pack does not arm live trading and does not bypass `ARM_LIVE_TRADING`.",
            "",
        ]
    )


def write_pack(output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    slug = utc_slug()
    pack_name = f"crypto-contract-ai-trader-live-env-pack-{slug}.zip"
    pack_path = output_dir / pack_name
    files: list[dict[str, Any]] = []
    manifest: dict[str, Any] = {
        "created_at": created_at,
        "project_root": str(ROOT_DIR),
        "pack_name": pack_name,
        "security_note": "Templates contain placeholders only; no .env or API secret is included.",
        "stages": list(STAGE_OVERRIDES),
        "files": files,
    }
    with zipfile.ZipFile(pack_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for stage in STAGE_OVERRIDES:
            text = render_stage_env(stage)
            scan_text(f"env/{stage}.env", text)
            payload = text.encode("utf-8")
            arcname = f"env/{stage}.env"
            archive.writestr(arcname, payload)
            files.append({"path": arcname, "bytes": len(payload), "sha256": sha256_bytes(payload)})
        readme = write_readme(created_at)
        scan_text("README-LIVE-ENV-PACK.md", readme)
        readme_bytes = readme.encode("utf-8")
        archive.writestr("README-LIVE-ENV-PACK.md", readme_bytes)
        files.append(
            {
                "path": "README-LIVE-ENV-PACK.md",
                "bytes": len(readme_bytes),
                "sha256": sha256_bytes(readme_bytes),
            }
        )
        manifest_bytes = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
        archive.writestr("LIVE_ENV_PACK_MANIFEST.json", manifest_bytes)

    return {
        "ok": True,
        "pack_path": str(pack_path),
        "bytes": pack_path.stat().st_size,
        "sha256": sha256_file(pack_path),
        "file_count": len(files),
        "manifest_path": "LIVE_ENV_PACK_MANIFEST.json",
        "stages": list(STAGE_OVERRIDES),
        "excluded": [".env", "api secrets", "runtime data", "databases"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Export stage-specific server .env templates without secrets.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory to place the live env pack zip.")
    args = parser.parse_args()
    try:
        result = write_pack(Path(args.output_dir).resolve())
    except Exception as exc:  # noqa: BLE001 - packaging errors should be direct in CLI output.
        print(f"FAILED: {exc}", file=__import__("sys").stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
