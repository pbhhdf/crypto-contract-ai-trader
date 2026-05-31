from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT_DIR / "reports"
PYTHON = sys.executable


def utc_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def terminate_process_tree(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                cwd=ROOT_DIR,
                text=True,
                capture_output=True,
                timeout=10,
            )
        else:
            os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=5)
    except Exception:
        try:
            if os.name == "nt":
                process.kill()
            else:
                os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)
        except Exception:
            pass


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def run_step(name: str, command: list[str], timeout: int, dry_run: bool = False) -> dict[str, Any]:
    if dry_run:
        return {
            "name": name,
            "ok": True,
            "dry_run": True,
            "returncode": 0,
            "duration_seconds": 0,
            "command": command,
            "stdout": "",
            "stderr": "",
        }
    started = time.time()
    env = os.environ.copy()
    process: subprocess.Popen[str] | None = None
    stdout = ""
    stderr = ""
    timed_out = False
    launch_error = ""
    try:
        popen_kwargs = {"start_new_session": True} if os.name != "nt" else {}
        process = subprocess.Popen(
            command,
            cwd=ROOT_DIR,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            **popen_kwargs,
        )
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
            terminate_process_tree(process)
            try:
                more_stdout, more_stderr = process.communicate(timeout=5)
            except subprocess.TimeoutExpired as final_exc:
                more_stdout = final_exc.stdout or ""
                more_stderr = "\n".join(
                    item
                    for item in [
                        str(final_exc.stderr or "").strip(),
                        "Process did not exit cleanly after timeout termination.",
                    ]
                    if item
                )
            stdout = "".join([stdout, more_stdout or ""])
            stderr = "".join([stderr, more_stderr or ""])
    except Exception as exc:  # noqa: BLE001 - readiness runner must report launch failures.
        launch_error = f"{exc.__class__.__name__}: {exc}"
    returncode = process.returncode if process is not None else 1
    if timed_out:
        stderr = "\n".join(item for item in [stderr.strip(), f"Timed out after {timeout}s"] if item)
    if launch_error:
        stderr = "\n".join(item for item in [stderr.strip(), launch_error] if item)
    ok = returncode == 0 and not timed_out and not launch_error
    return {
        "name": name,
        "ok": ok,
        "dry_run": False,
        "returncode": returncode,
        "duration_seconds": round(time.time() - started, 2),
        "command": command,
        "stdout": stdout.strip(),
        "stderr": stderr.strip(),
        "timed_out": timed_out,
    }


def write_report(report: dict[str, Any]) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"server-live-readiness-runner-{utc_slug()}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def add_step(steps: list[dict[str, Any]], name: str, command: list[str], timeout: int, dry_run: bool) -> bool:
    step = run_step(name, command, timeout=timeout, dry_run=dry_run)
    steps.append(step)
    return bool(step.get("ok"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the server-side sequence that gathers evidence before Binance live mode: "
            "deployment profile, checks, strategy sweep, optional real Testnet drill, audit, backup, and final live report."
        )
    )
    parser.add_argument("--dry-run", action="store_true", help="Only write the planned step list.")
    parser.add_argument("--skip-full-checks", action="store_true", help="Skip scripts/run_all_checks.py.")
    parser.add_argument("--skip-strategy-sweep", action="store_true", help="Skip multi-market strategy-quality sweep.")
    parser.add_argument("--run-testnet-drill", action="store_true", help="Run real Testnet drill cycles after checks.")
    parser.add_argument("--testnet-mode", default=os.getenv("TRADER_TESTNET_DRILL_MODE", "binance_testnet_validate"))
    parser.add_argument("--target-cycles", type=int, default=int(os.getenv("GO_LIVE_MIN_TESTNET_DRILL_CYCLES", "24")))
    parser.add_argument("--interval-seconds", type=float, default=float(os.getenv("TRADER_TESTNET_DRILL_INTERVAL_SECONDS", "60")))
    parser.add_argument("--allow-testnet-placement", action="store_true")
    parser.add_argument("--strict", action="store_true", help="Return non-zero when final live readiness is still blocked.")
    return parser


def main() -> int:
    load_env_file(ROOT_DIR / ".env")
    args = build_parser().parse_args()
    steps: list[dict[str, Any]] = []

    plan: list[tuple[str, list[str], int]] = [
        ("preflight", [PYTHON, "scripts/preflight.py"], 60),
        ("server_deploy_profile", [PYTHON, "scripts/check_server_deploy_profile.py"], 30),
        ("binance_time_drift", [PYTHON, "scripts/check_binance_time_drift.py"], 60),
    ]
    if not args.skip_full_checks:
        plan.append(("all_checks", [PYTHON, "scripts/run_all_checks.py"], 900))
    if not args.skip_strategy_sweep:
        plan.append(
            (
                "strategy_quality_sweep",
                [
                    PYTHON,
                    "scripts/run_strategy_quality_sweep.py",
                    "--symbols",
                    os.getenv("TRADER_SWEEP_SYMBOLS", "BTCUSDT,ETHUSDT,SOLUSDT"),
                    "--intervals",
                    os.getenv("TRADER_SWEEP_INTERVALS", "5m,15m,1h"),
                    "--bars",
                    os.getenv("TRADER_SWEEP_BARS", "240"),
                    "--promote-best",
                ],
                360,
            )
        )
    if args.run_testnet_drill:
        drill_command = [
            PYTHON,
            "scripts/run_testnet_drill_until_ready.py",
            "--mode",
            args.testnet_mode,
            "--target-cycles",
            str(args.target_cycles),
            "--interval-seconds",
            str(args.interval_seconds),
        ]
        if args.allow_testnet_placement:
            drill_command.append("--allow-testnet-placement")
        plan.append(("testnet_drill_until_ready", drill_command, max(120, int(args.target_cycles * args.interval_seconds + 300))))
    plan.extend(
        [
            ("go_live_report", [PYTHON, "scripts/check_go_live_report.py"], 180),
            ("server_go_live_audit", [PYTHON, "scripts/server_go_live_audit.py"], 240),
            ("export_live_launch_plan", [PYTHON, "scripts/export_live_launch_plan.py"], 120),
            ("export_live_ops_handoff", [PYTHON, "scripts/export_live_ops_handoff.py"], 120),
            ("export_server_bundle", [PYTHON, "scripts/export_server_bundle.py"], 120),
            ("export_live_env_pack", [PYTHON, "scripts/export_live_env_pack.py"], 120),
            ("export_live_launch_kit", [PYTHON, "scripts/export_live_launch_kit.py"], 360),
            ("backup_state", [PYTHON, "scripts/backup_state.py", "--include-env-example"], 120),
            ("final_live_ready_api", [PYTHON, "scripts/check_final_live_ready_api.py"], 180),
        ]
    )

    ok_so_far = True
    for name, command, timeout in plan:
        if ok_so_far or name in {
            "go_live_report",
            "server_go_live_audit",
            "export_live_launch_plan",
            "export_live_ops_handoff",
            "export_server_bundle",
            "export_live_env_pack",
            "export_live_launch_kit",
            "backup_state",
            "final_live_ready_api",
        }:
            ok_so_far = add_step(steps, name, command, timeout, args.dry_run) and ok_so_far
        else:
            steps.append(
                {
                    "name": name,
                    "ok": False,
                    "skipped": True,
                    "returncode": None,
                    "duration_seconds": 0,
                    "command": command,
                    "stdout": "",
                    "stderr": "Skipped because an earlier prerequisite step failed.",
                }
            )

    final_step = next((step for step in reversed(steps) if step["name"] == "final_live_ready_api"), {})
    final_stdout = final_step.get("stdout") or "{}"
    try:
        final_payload = json.loads(final_stdout)
    except json.JSONDecodeError:
        final_payload = {}
    evidence_paths: dict[str, Any] = {}
    for step in steps:
        stdout = step.get("stdout") or "{}"
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            continue
        if step.get("name") == "go_live_report":
            exported = payload.get("exported") if isinstance(payload, dict) else None
            if isinstance(exported, dict):
                evidence_paths["go_live_report_json"] = exported.get("json_path")
                evidence_paths["go_live_report_markdown"] = exported.get("markdown_path")
        elif step.get("name") == "server_go_live_audit":
            evidence_paths["server_go_live_audit_json"] = payload.get("json_path")
            evidence_paths["server_go_live_audit_markdown"] = payload.get("markdown_path")
        elif step.get("name") == "export_live_launch_plan":
            evidence_paths["live_launch_plan_json"] = payload.get("json_path")
            evidence_paths["live_launch_plan_markdown"] = payload.get("markdown_path")
        elif step.get("name") == "export_live_ops_handoff":
            evidence_paths["live_ops_handoff_json"] = payload.get("json_path")
            evidence_paths["live_ops_handoff_markdown"] = payload.get("markdown_path")
        elif step.get("name") == "export_server_bundle":
            evidence_paths["server_bundle"] = payload.get("bundle_path")
            evidence_paths["server_bundle_sha256"] = payload.get("sha256")
        elif step.get("name") == "export_live_env_pack":
            evidence_paths["live_env_pack"] = payload.get("pack_path")
            evidence_paths["live_env_pack_sha256"] = payload.get("sha256")
        elif step.get("name") == "export_live_launch_kit":
            evidence_paths["live_launch_kit"] = payload.get("kit_path")
            evidence_paths["live_launch_kit_sha256"] = payload.get("sha256")
        elif step.get("name") == "backup_state":
            evidence_paths["state_backup"] = payload.get("backup_path")
    if args.dry_run:
        for key in (
            "go_live_report_json",
            "go_live_report_markdown",
            "server_go_live_audit_json",
            "server_go_live_audit_markdown",
            "live_launch_plan_json",
            "live_launch_plan_markdown",
            "live_ops_handoff_json",
            "live_ops_handoff_markdown",
            "server_bundle",
            "server_bundle_sha256",
            "live_env_pack",
            "live_env_pack_sha256",
            "live_launch_kit",
            "live_launch_kit_sha256",
            "state_backup",
        ):
            evidence_paths.setdefault(key, None)
    final_ready = bool(final_payload.get("endpoint_ok"))
    report = {
        "ok": all(step.get("ok") for step in steps),
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dry_run": args.dry_run,
        "strict": args.strict,
        "base_url": os.getenv("TRADER_BASE_URL", "http://127.0.0.1:8787"),
        "run_testnet_drill": args.run_testnet_drill,
        "steps": steps,
        "evidence_paths": evidence_paths,
        "final_live_ready": final_payload,
    }
    path = write_report(report)
    summary = {
        "ok": report["ok"] and (final_ready or not args.strict),
        "steps_ok": report["ok"],
        "final_live_ready": final_ready,
        "blocking_gates": final_payload.get("blocking_gates"),
        "evidence_paths": evidence_paths,
        "report_path": str(path),
        "dry_run": args.dry_run,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.strict and not final_ready:
        return 1
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
