from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def read_text(path: str) -> str:
    return (ROOT_DIR / path).read_text(encoding="utf-8")


def fail(message: str, details: object | None = None) -> int:
    print(f"FAILED: {message}", file=sys.stderr)
    if details is not None:
        print(json.dumps(details, ensure_ascii=False, indent=2), file=sys.stderr)
    return 1


def require_contains(path: str, text: str, needle: str, failures: list[str]) -> None:
    if needle not in text:
        failures.append(f"{path} is missing {needle!r}")


def main() -> int:
    required_files = [
        "deploy/docker-compose.yml",
        "deploy/server.env.example",
        "deploy/setup-ubuntu-tailscale.sh",
        "deploy/setup-ubuntu-time-sync.sh",
        "deploy/verify-server.sh",
        "deploy/backup-server.sh",
        "deploy/restore-server.sh",
        "deploy/deploy-server.sh",
        "scripts/live_env_profile.py",
        "scripts/check_live_env_profile.py",
        "scripts/export_live_launch_plan.py",
        "scripts/check_live_launch_plan.py",
        "scripts/check_live_launch_plan_api.py",
        "scripts/export_live_ops_handoff.py",
        "scripts/check_live_ops_handoff.py",
        "scripts/check_live_ops_handoff_api.py",
        "scripts/export_server_bundle.py",
        "scripts/export_live_launch_kit.py",
        "scripts/check_live_launch_kit.py",
        "scripts/check_live_launch_kit_api.py",
        "scripts/export_live_env_pack.py",
        "scripts/check_live_env_pack.py",
        "scripts/check_live_env_pack_api.py",
        "scripts/check_live_blocker_resolution.py",
        "scripts/check_live_pilot_postflight.py",
    ]
    missing = [path for path in required_files if not (ROOT_DIR / path).exists()]
    if missing:
        return fail("server deployment files are missing", missing)

    compose = read_text("deploy/docker-compose.yml")
    env_example = read_text("deploy/server.env.example")
    setup_tailnet = read_text("deploy/setup-ubuntu-tailscale.sh")
    setup_time = read_text("deploy/setup-ubuntu-time-sync.sh")
    verify = read_text("deploy/verify-server.sh")
    deploy = read_text("deploy/deploy-server.sh")
    restore = read_text("deploy/restore-server.sh")

    failures: list[str] = []

    require_contains("deploy/docker-compose.yml", compose, "${TRADER_BIND_IP:-127.0.0.1}", failures)
    require_contains("deploy/docker-compose.yml", compose, "env_file:", failures)
    require_contains("deploy/docker-compose.yml", compose, "../data:/app/data", failures)

    require_contains("deploy/server.env.example", env_example, "APP_ENV=server", failures)
    require_contains("deploy/server.env.example", env_example, "TRADER_BIND_IP=<tailscale-ipv4>", failures)
    require_contains("deploy/server.env.example", env_example, "APP_BASIC_AUTH_PASSWORD=<choose-long-random-password>", failures)
    require_contains("deploy/server.env.example", env_example, "AUTH_FAILURE_LIMIT=8", failures)
    require_contains("deploy/server.env.example", env_example, "AUTH_FAILURE_WINDOW_SECONDS=300", failures)
    require_contains("deploy/server.env.example", env_example, "AUTH_LOCKOUT_SECONDS=900", failures)
    require_contains("deploy/server.env.example", env_example, "AI_OPERATOR_ALLOW_FILE_WRITE=true", failures)
    require_contains("deploy/server.env.example", env_example, "AI_OPERATOR_ALLOW_SHELL=true", failures)
    require_contains("deploy/server.env.example", env_example, "AI_OPERATOR_APPLY_MODEL_FILE_ACTIONS=true", failures)
    require_contains("deploy/server.env.example", env_example, "AI_OPERATOR_BACKUP_BEFORE_SHELL=true", failures)
    require_contains("deploy/server.env.example", env_example, "ENABLE_BINANCE_LIVE=false", failures)
    require_contains("deploy/server.env.example", env_example, "BINANCE_PLACE_LIVE_ORDERS=false", failures)
    require_contains("deploy/server.env.example", env_example, "GO_LIVE_REQUIRE_ALERT_WEBHOOK=true", failures)
    require_contains("deploy/server.env.example", env_example, "LIVE_ARMING_MAX_ORDERS=1", failures)
    if "TRADER_BIND_IP=0.0.0.0" in env_example:
        failures.append("deploy/server.env.example must not suggest TRADER_BIND_IP=0.0.0.0")

    require_contains("deploy/setup-ubuntu-tailscale.sh", setup_tailnet, "tailscale up --ssh", failures)
    require_contains("deploy/setup-ubuntu-tailscale.sh", setup_tailnet, "ufw allow OpenSSH", failures)
    require_contains("deploy/setup-ubuntu-tailscale.sh", setup_tailnet, "ufw allow in on tailscale0", failures)
    require_contains("deploy/setup-ubuntu-time-sync.sh", setup_time, "chrony", failures)
    require_contains("deploy/setup-ubuntu-time-sync.sh", setup_time, "BINANCE_TIME_DRIFT_REQUIRE_PASS=true", failures)

    for needle in (
        "python3 scripts/preflight.py",
        "python3 scripts/live_env_profile.py --target live_guarded",
        "python3 scripts/run_all_checks.py",
        "python3 scripts/server_go_live_audit.py",
        "python3 scripts/export_live_launch_plan.py",
        "python3 scripts/export_live_ops_handoff.py",
        "python3 scripts/export_server_bundle.py",
        "python3 scripts/export_live_env_pack.py",
        "python3 scripts/export_live_launch_kit.py",
    ):
        require_contains("deploy/verify-server.sh", verify, needle, failures)

    for needle in (
        "APP_ENV must be server",
        "TRADER_BIND_IP=0.0.0.0 is not allowed",
        "APP_BASIC_AUTH_PASSWORD must be at least 16 characters",
        "AI_OPERATOR_BACKUP_BEFORE_SHELL=true is required",
        "TRADER_BIND_IP=:: is not allowed",
        "TRADER_BIND_IP looks like a public address",
        "docker compose -f",
        "bash deploy/verify-server.sh",
        "python3 scripts/server_go_live_audit.py",
        "python3 scripts/export_live_launch_plan.py",
        "python3 scripts/export_live_ops_handoff.py",
        "python3 scripts/export_server_bundle.py",
        "python3 scripts/export_live_env_pack.py",
        "python3 scripts/export_live_launch_kit.py",
        "bash deploy/backup-server.sh",
        "TRADER_ALLOW_LIVE_DEPLOY=true",
        "TRADER_FINAL_LIVE_REQUIRE_ARMED=false python3 scripts/check_final_live_ready.py",
        "python3 scripts/live_env_profile.py --env-file",
    ):
        require_contains("deploy/deploy-server.sh", deploy, needle, failures)

    for needle in (
        "docker compose -f deploy/docker-compose.yml down",
        "python3 scripts/restore_state.py",
        "--confirm RESTORE_TRADER_STATE",
        "docker compose -f deploy/docker-compose.yml up -d",
    ):
        require_contains("deploy/restore-server.sh", restore, needle, failures)

    if failures:
        return fail("server deployment profile is incomplete or unsafe", failures)

    print(
        json.dumps(
            {
                "ok": True,
                "checked_files": required_files,
                "private_network_required": True,
                "basic_auth_required": True,
                "live_defaults_locked": True,
                "high_permission_operator_guarded_by_backups": True,
                "one_command_deploy": "deploy/deploy-server.sh",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
