from __future__ import annotations

import json
import os
import base64
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.error import URLError
from urllib.request import Request, urlopen


ROOT_DIR = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT_DIR / "reports"
ACTIVE_REPORT_WRITER: Callable[[str, str], None] | None = None


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env_file(ROOT_DIR / ".env")

BASE_URL = os.getenv("TRADER_BASE_URL", "http://127.0.0.1:8787").rstrip("/")
PYTHON = sys.executable
AUTH_USER = os.getenv("TRADER_AUTH_USER", os.getenv("APP_BASIC_AUTH_USER", ""))
AUTH_PASSWORD = os.getenv("TRADER_AUTH_PASSWORD", os.getenv("APP_BASIC_AUTH_PASSWORD", ""))


def auth_headers() -> dict[str, str]:
    headers = {"Accept": "application/json"}
    if AUTH_USER and AUTH_PASSWORD:
        token = base64.b64encode(f"{AUTH_USER}:{AUTH_PASSWORD}".encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {token}"
    return headers


def utc_now_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def emit_progress(name: str, status: str, **fields: Any) -> None:
    payload = {"step": name, "status": status, **fields}
    print(json.dumps(payload, ensure_ascii=False), file=sys.stderr, flush=True)


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(path)


def build_readiness_report(
    *,
    status: str,
    started_at: str,
    steps: list[dict[str, Any]],
    readiness: Any = None,
    ok: bool | None = None,
    current_step: dict[str, Any] | None = None,
    final_report_path: Path | None = None,
) -> dict[str, Any]:
    failed_steps = [step["name"] for step in steps if not step.get("ok")]
    return {
        "ok": bool(ok) if ok is not None else False,
        "status": status,
        "started_at": started_at,
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "project_root": str(ROOT_DIR),
        "base_url": BASE_URL,
        "current_step": current_step or {},
        "completed_step_count": len(steps),
        "failed_steps": failed_steps,
        "final_report_path": str(final_report_path) if final_report_path else "",
        "steps": steps,
        "readiness": readiness,
    }


def update_active_step(name: str, status: str) -> None:
    if ACTIVE_REPORT_WRITER is not None:
        ACTIVE_REPORT_WRITER(name, status)


class ReportingSteps(list[dict[str, Any]]):
    def __init__(self, on_append: Callable[[dict[str, Any]], None]) -> None:
        super().__init__()
        self.on_append = on_append

    def append(self, item: dict[str, Any]) -> None:
        super().append(item)
        self.on_append(item)


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


def run_step(name: str, args: list[str], timeout: int = 120) -> dict[str, Any]:
    started = time.time()
    env = os.environ.copy()
    if AUTH_USER and AUTH_PASSWORD:
        env.setdefault("TRADER_AUTH_USER", AUTH_USER)
        env.setdefault("TRADER_AUTH_PASSWORD", AUTH_PASSWORD)
    emit_progress(name, "start", timeout_seconds=timeout)
    update_active_step(name, "running")
    process: subprocess.Popen[str] | None = None
    stdout = ""
    stderr = ""
    timed_out = False
    launch_error = ""
    try:
        popen_kwargs = {"start_new_session": True} if os.name != "nt" else {}
        process = subprocess.Popen(
            args,
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
    except Exception as exc:  # noqa: BLE001 - validation runner must report launch failures as step failures.
        launch_error = f"{exc.__class__.__name__}: {exc}"
    returncode = process.returncode if process is not None else 1
    if timed_out:
        stderr = "\n".join(item for item in [stderr.strip(), f"Timed out after {timeout}s"] if item)
    if launch_error:
        stderr = "\n".join(item for item in [stderr.strip(), launch_error] if item)
    ok = returncode == 0 and not timed_out and not launch_error
    duration = round(time.time() - started, 2)
    emit_progress(name, "done", ok=ok, duration_seconds=duration, timed_out=timed_out)
    update_active_step(name, "done")
    return {
        "name": name,
        "ok": ok,
        "returncode": returncode,
        "duration_seconds": duration,
        "command": args,
        "stdout": stdout.strip(),
        "stderr": stderr.strip(),
        "timed_out": timed_out,
    }


def health_ok() -> bool:
    try:
        request = Request(f"{BASE_URL}/api/health", headers=auth_headers())
        with urlopen(request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return payload.get("ok") is True
    except (OSError, URLError, TimeoutError, json.JSONDecodeError):
        return False


def fetch_json(path: str) -> Any:
    request = Request(f"{BASE_URL}{path}", headers=auth_headers())
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def post_json(path: str, payload: dict[str, Any]) -> Any:
    body = json.dumps(payload).encode("utf-8")
    headers = auth_headers()
    headers["Content-Type"] = "application/json"
    request = Request(f"{BASE_URL}{path}", data=body, headers=headers, method="POST")
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def quiesce_background_work() -> dict[str, Any]:
    result: dict[str, Any] = {"ok": True, "actions": []}
    actions = [
        (
            "scheduler_disabled",
            "/api/scheduler",
            {"enabled": False, "symbol": "BTCUSDT", "mode": "paper", "interval_seconds": 3600},
        ),
        (
            "testnet_drill_disabled",
            "/api/testnet-drill",
            {"enabled": False, "symbol": "BTCUSDT", "mode": "binance_testnet_validate", "interval_minutes": 60},
        ),
    ]
    for name, path, payload in actions:
        try:
            post_json(path, payload)
            result["actions"].append({"name": name, "ok": True})
        except Exception as exc:  # noqa: BLE001 - capture all quiesce failures in the report.
            result["ok"] = False
            result["actions"].append({"name": name, "ok": False, "error": f"{exc.__class__.__name__}: {exc}"})
    return result


def wait_for_idle(timeout_seconds: int = 60) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    last_state: dict[str, Any] = {}
    while time.time() < deadline:
        try:
            scheduler = fetch_json("/api/scheduler").get("scheduler") or {}
            scheduler_active_runs = scheduler.get("active_runs") or []
            last_state = {
                "scheduler_active_runs": scheduler_active_runs,
            }
            if not scheduler_active_runs:
                return {"ok": True, **last_state}
        except Exception as exc:  # noqa: BLE001 - keep polling until timeout.
            last_state = {"error": f"{exc.__class__.__name__}: {exc}"}
        time.sleep(1)
    return {"ok": False, **last_state}


def run_server_step(name: str, args: list[str], timeout: int = 120) -> dict[str, Any]:
    idle_before = wait_for_idle()
    if not idle_before.get("ok"):
        return {
            "name": name,
            "ok": False,
            "returncode": 1,
            "duration_seconds": 0,
            "command": args,
            "stdout": "",
            "stderr": f"Service did not become idle before step: {json.dumps(idle_before, ensure_ascii=False)}",
        }
    step = run_step(name, args, timeout=timeout)
    idle_after = wait_for_idle()
    if not idle_after.get("ok") and step["ok"]:
        step["ok"] = False
        step["stderr"] = "\n".join(
            item
            for item in [
                step.get("stderr", ""),
                f"Service did not become idle after step: {json.dumps(idle_after, ensure_ascii=False)}",
            ]
            if item
        )
    return step


def main() -> int:
    global ACTIVE_REPORT_WRITER
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    run_slug = utc_now_slug()
    report_path = REPORT_DIR / f"local-readiness-{run_slug}.json"
    active_report_path = REPORT_DIR / "local-readiness-active.json"
    partial_report_path = REPORT_DIR / f"local-readiness-{run_slug}.partial.json"
    current_step: dict[str, Any] = {"name": "starting", "status": "starting"}

    def write_active_report(step_name: str = "", step_status: str = "") -> None:
        nonlocal current_step
        if step_name or step_status:
            current_step = {
                "name": step_name or current_step.get("name") or "",
                "status": step_status or current_step.get("status") or "",
                "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
        payload = build_readiness_report(
            status="running",
            started_at=started_at,
            steps=list(steps),
            readiness=None,
            current_step=current_step,
            final_report_path=report_path,
        )
        write_json_atomic(active_report_path, payload)
        write_json_atomic(partial_report_path, payload)

    steps: ReportingSteps = ReportingSteps(lambda step: write_active_report(str(step.get("name") or ""), "done"))
    ACTIVE_REPORT_WRITER = write_active_report
    write_active_report("starting", "running")

    steps.append(
        run_step(
            "compile",
            [
                PYTHON,
                "-m",
                "py_compile",
                "app/server.py",
                "app/live_ops_handoff.py",
                "scripts/check_public_data.py",
                "scripts/check_backtest.py",
                "scripts/check_compare.py",
                "scripts/check_walkforward.py",
                "scripts/check_walkforward_quality_gate.py",
                "scripts/check_strategy_quality_sweep.py",
                "scripts/check_server_live_readiness_runner.py",
                "scripts/check_server_live_readiness_cancel.py",
                "scripts/check_server_live_readiness_api.py",
                "scripts/check_local_readiness_api.py",
                "scripts/check_check_runner_timeout.py",
                "scripts/live_env_profile.py",
                "scripts/check_live_env_profile.py",
                "scripts/export_live_launch_plan.py",
                "scripts/check_live_launch_plan.py",
                "scripts/check_live_launch_plan_api.py",
                "scripts/export_live_ops_handoff.py",
                "scripts/check_live_ops_handoff.py",
                "scripts/check_live_ops_handoff_api.py",
                "scripts/export_live_launch_kit.py",
                "scripts/check_live_launch_kit.py",
                "scripts/check_live_launch_kit_api.py",
                "scripts/export_live_env_pack.py",
                "scripts/check_live_env_pack.py",
                "scripts/check_live_env_pack_api.py",
                "scripts/check_live_blocker_resolution.py",
                "scripts/check_live_pilot.py",
                "scripts/check_live_pilot_postflight.py",
                "scripts/run_guarded_live_pilot_once.py",
                "scripts/check_guarded_live_pilot_runner.py",
                "scripts/check_live_protection_guard.py",
                "scripts/check_protection_unknown_submit.py",
                "scripts/check_sibling_protection_cleanup.py",
                "scripts/check_pre_submit_order_tests.py",
                "scripts/check_protection_geometry.py",
                "scripts/check_execution_market_freshness.py",
                "scripts/check_stateful_order_conflict.py",
                "scripts/check_stateful_risk_warning_blocks.py",
                "scripts/check_unknown_submit_reconcile.py",
                "scripts/check_exchange_open_order_gate.py",
                "scripts/check_exchange_position_gate.py",
                "scripts/check_parent_cancel_cascade.py",
                "scripts/check_orphan_protection_guard.py",
                "scripts/check_startup_disarms_live_arming.py",
                "scripts/check_scheduler.py",
                "scripts/check_risk_controls.py",
                "scripts/check_oms.py",
                "scripts/check_research_artifacts.py",
                "scripts/check_architecture_blueprint.py",
                "scripts/check_ai_operator_schema.py",
                "scripts/check_ai_operator.py",
                "scripts/check_panic_stop.py",
                "scripts/check_alert_delivery.py",
                "scripts/check_alert_watchdog.py",
                "scripts/check_testnet_drill.py",
                "scripts/check_testnet_drill_order_evidence.py",
                "scripts/check_testnet_drill_runner.py",
                "scripts/check_exchange_recovery.py",
                "scripts/check_exchange_emergency.py",
                "scripts/check_private_stream_mapping.py",
                "scripts/check_private_stream_health.py",
                "scripts/check_binance_testnet_validate.py",
                "scripts/check_binance_testnet_place_order.py",
                "scripts/check_binance_live_guard.py",
                "scripts/check_final_live_ready.py",
                "scripts/check_final_live_ready_api.py",
                "scripts/server_go_live_audit.py",
                "scripts/check_server_bundle.py",
                "scripts/check_server_go_live_audit.py",
                "scripts/check_server_go_live_audit_api.py",
                "scripts/check_go_live_gate.py",
                "scripts/check_live_attestation.py",
                "scripts/check_live_arming_budget.py",
                "scripts/check_binance_margin_type_sync.py",
                "scripts/check_binance_leverage_sync.py",
                "scripts/check_binance_position_mode.py",
                "scripts/check_binance_time_drift.py",
                "scripts/check_go_live_report.py",
                "scripts/check_binance_filters.py",
                "scripts/check_order_sizing.py",
                "scripts/check_audit_chain.py",
                "scripts/check_backup_state.py",
                "scripts/check_restore_state.py",
                "scripts/check_private_bind_gate.py",
                "scripts/check_preflight_live_profile.py",
                "scripts/check_server_deploy_profile.py",
                "scripts/check_auth_rate_limit.py",
                "scripts/check_auth_rate_limit_http.py",
                "scripts/export_go_live_report.py",
                "scripts/export_server_bundle.py",
                "scripts/run_testnet_drill_until_ready.py",
                "scripts/run_strategy_quality_sweep.py",
                "scripts/run_server_live_readiness.py",
                "scripts/backup_state.py",
                "scripts/restore_state.py",
                "scripts/check_ui_chinese.py",
                "scripts/preflight.py",
            ],
            timeout=30,
        )
    )
    steps.append(run_step("preflight", [PYTHON, "scripts/preflight.py"], timeout=45))
    steps.append(run_step("private_bind_gate", [PYTHON, "scripts/check_private_bind_gate.py"], timeout=30))
    steps.append(run_step("preflight_live_profile", [PYTHON, "scripts/check_preflight_live_profile.py"], timeout=60))
    steps.append(run_step("server_deploy_profile", [PYTHON, "scripts/check_server_deploy_profile.py"], timeout=30))
    steps.append(run_step("auth_rate_limit", [PYTHON, "scripts/check_auth_rate_limit.py"], timeout=30))
    steps.append(run_step("auth_rate_limit_http", [PYTHON, "scripts/check_auth_rate_limit_http.py"], timeout=60))
    steps.append(run_step("live_env_profile", [PYTHON, "scripts/check_live_env_profile.py"], timeout=30))
    steps.append(run_step("live_launch_plan", [PYTHON, "scripts/check_live_launch_plan.py"], timeout=30))
    steps.append(run_step("live_ops_handoff", [PYTHON, "scripts/check_live_ops_handoff.py"], timeout=30))
    steps.append(run_step("live_protection_guard", [PYTHON, "scripts/check_live_protection_guard.py"], timeout=60))
    steps.append(run_step("protection_unknown_submit", [PYTHON, "scripts/check_protection_unknown_submit.py"], timeout=60))
    steps.append(run_step("sibling_protection_cleanup", [PYTHON, "scripts/check_sibling_protection_cleanup.py"], timeout=60))
    steps.append(run_step("pre_submit_order_tests", [PYTHON, "scripts/check_pre_submit_order_tests.py"], timeout=30))
    steps.append(run_step("protection_geometry", [PYTHON, "scripts/check_protection_geometry.py"], timeout=30))
    steps.append(run_step("execution_market_freshness", [PYTHON, "scripts/check_execution_market_freshness.py"], timeout=30))
    steps.append(run_step("stateful_order_conflict", [PYTHON, "scripts/check_stateful_order_conflict.py"], timeout=30))
    steps.append(run_step("stateful_risk_warning_blocks", [PYTHON, "scripts/check_stateful_risk_warning_blocks.py"], timeout=30))
    steps.append(run_step("unknown_submit_reconcile", [PYTHON, "scripts/check_unknown_submit_reconcile.py"], timeout=30))
    steps.append(run_step("exchange_open_order_gate", [PYTHON, "scripts/check_exchange_open_order_gate.py"], timeout=30))
    steps.append(run_step("exchange_position_gate", [PYTHON, "scripts/check_exchange_position_gate.py"], timeout=30))
    steps.append(run_step("parent_cancel_cascade", [PYTHON, "scripts/check_parent_cancel_cascade.py"], timeout=60))
    steps.append(run_step("orphan_protection_guard", [PYTHON, "scripts/check_orphan_protection_guard.py"], timeout=60))
    steps.append(run_step("startup_disarms_live_arming", [PYTHON, "scripts/check_startup_disarms_live_arming.py"], timeout=60))
    steps.append(run_step("ui_chinese", [PYTHON, "scripts/check_ui_chinese.py"], timeout=30))
    steps.append(run_step("binance_filters", [PYTHON, "scripts/check_binance_filters.py"], timeout=60))
    steps.append(run_step("order_sizing", [PYTHON, "scripts/check_order_sizing.py"], timeout=60))
    steps.append(run_step("strategy_quality_sweep", [PYTHON, "scripts/check_strategy_quality_sweep.py"], timeout=45))
    steps.append(run_step("server_live_readiness_runner", [PYTHON, "scripts/check_server_live_readiness_runner.py"], timeout=45))
    steps.append(run_step("server_live_readiness_cancel", [PYTHON, "scripts/check_server_live_readiness_cancel.py"], timeout=45))
    steps.append(run_step("check_runner_timeout", [PYTHON, "scripts/check_check_runner_timeout.py"], timeout=20))
    steps.append(run_step("ai_operator_schema", [PYTHON, "scripts/check_ai_operator_schema.py"], timeout=30))
    steps.append(run_step("audit_chain", [PYTHON, "scripts/check_audit_chain.py"], timeout=60))
    steps.append(run_step("backup_state", [PYTHON, "scripts/check_backup_state.py"], timeout=60))
    steps.append(run_step("restore_state", [PYTHON, "scripts/check_restore_state.py"], timeout=90))
    steps.append(run_step("server_bundle", [PYTHON, "scripts/export_server_bundle.py"], timeout=60))
    steps.append(run_step("live_env_pack", [PYTHON, "scripts/check_live_env_pack.py"], timeout=120))
    steps.append(run_step("live_launch_kit", [PYTHON, "scripts/check_live_launch_kit.py"], timeout=300))

    server_available = health_ok()
    if server_available:
        quiet = quiesce_background_work()
        steps.append(
            {
                "name": "background_quiesce",
                "ok": quiet["ok"],
                "returncode": 0 if quiet["ok"] else 1,
                "duration_seconds": 0,
                "command": ["POST", "/api/scheduler", "POST", "/api/testnet-drill"],
                "stdout": json.dumps(quiet, ensure_ascii=False),
                "stderr": "",
            }
        )
        steps.append(run_server_step("paper_workflow", [PYTHON, "scripts/check_public_data.py"], timeout=120))
        steps.append(run_server_step("risk_controls", [PYTHON, "scripts/check_risk_controls.py"], timeout=150))
        steps.append(run_server_step("panic_stop", [PYTHON, "scripts/check_panic_stop.py"], timeout=120))
        steps.append(run_server_step("oms_reconcile", [PYTHON, "scripts/check_oms.py"], timeout=120))
        steps.append(run_server_step("research_artifacts", [PYTHON, "scripts/check_research_artifacts.py"], timeout=120))
        steps.append(run_server_step("architecture_blueprint", [PYTHON, "scripts/check_architecture_blueprint.py"], timeout=120))
        steps.append(run_server_step("ai_operator", [PYTHON, "scripts/check_ai_operator.py"], timeout=300))
        steps.append(run_server_step("alert_delivery", [PYTHON, "scripts/check_alert_delivery.py"], timeout=60))
        steps.append(run_server_step("alert_watchdog", [PYTHON, "scripts/check_alert_watchdog.py"], timeout=120))
        steps.append(run_server_step("testnet_drill", [PYTHON, "scripts/check_testnet_drill.py"], timeout=120))
        steps.append(run_step("testnet_drill_order_evidence", [PYTHON, "scripts/check_testnet_drill_order_evidence.py"], timeout=30))
        steps.append(run_server_step("testnet_drill_runner", [PYTHON, "scripts/check_testnet_drill_runner.py"], timeout=150))
        steps.append(run_server_step("exchange_recovery", [PYTHON, "scripts/check_exchange_recovery.py"], timeout=120))
        steps.append(run_server_step("exchange_emergency", [PYTHON, "scripts/check_exchange_emergency.py"], timeout=120))
        steps.append(run_server_step("private_stream_mapping", [PYTHON, "scripts/check_private_stream_mapping.py"], timeout=60))
        steps.append(run_step("private_stream_health", [PYTHON, "scripts/check_private_stream_health.py"], timeout=60))
        steps.append(run_server_step("binance_live_guard", [PYTHON, "scripts/check_binance_live_guard.py"], timeout=120))
        steps.append(run_server_step("scheduler", [PYTHON, "scripts/check_scheduler.py"], timeout=150))
        steps.append(run_server_step("backtest", [PYTHON, "scripts/check_backtest.py"], timeout=120))
        steps.append(run_server_step("parameter_compare", [PYTHON, "scripts/check_compare.py"], timeout=150))
        steps.append(run_server_step("walkforward", [PYTHON, "scripts/check_walkforward.py"], timeout=180))
        steps.append(
            run_server_step(
                "strategy_quality_sweep_real",
                [
                    PYTHON,
                    "scripts/run_strategy_quality_sweep.py",
                    "--symbols",
                    "BTCUSDT,ETHUSDT,SOLUSDT",
                    "--intervals",
                    "5m,15m,1h",
                    "--bars",
                    "240",
                    "--promote-best",
                ],
                timeout=240,
            )
        )
        steps.append(run_server_step("walkforward_quality_gate", [PYTHON, "scripts/check_walkforward_quality_gate.py"], timeout=120))
        steps.append(run_server_step("final_live_ready_api", [PYTHON, "scripts/check_final_live_ready_api.py"], timeout=120))
        steps.append(run_server_step("local_readiness_api", [PYTHON, "scripts/check_local_readiness_api.py"], timeout=120))
        steps.append(
            run_server_step("server_live_readiness_api", [PYTHON, "scripts/check_server_live_readiness_api.py"], timeout=150)
        )
        steps.append(run_server_step("server_bundle_api", [PYTHON, "scripts/check_server_bundle.py"], timeout=120))
        steps.append(run_server_step("server_go_live_audit_api", [PYTHON, "scripts/check_server_go_live_audit_api.py"], timeout=150))
        steps.append(run_server_step("server_go_live_audit", [PYTHON, "scripts/check_server_go_live_audit.py"], timeout=150))
        steps.append(run_server_step("live_launch_plan_api", [PYTHON, "scripts/check_live_launch_plan_api.py"], timeout=120))
        steps.append(run_server_step("live_launch_plan_export", [PYTHON, "scripts/export_live_launch_plan.py"], timeout=120))
        steps.append(run_server_step("live_ops_handoff_api", [PYTHON, "scripts/check_live_ops_handoff_api.py"], timeout=120))
        steps.append(run_server_step("live_ops_handoff_export", [PYTHON, "scripts/export_live_ops_handoff.py"], timeout=120))
        steps.append(run_server_step("live_env_pack_api", [PYTHON, "scripts/check_live_env_pack_api.py"], timeout=120))
        steps.append(run_server_step("live_env_pack_export", [PYTHON, "scripts/export_live_env_pack.py"], timeout=120))
        steps.append(run_server_step("live_blocker_resolution", [PYTHON, "scripts/check_live_blocker_resolution.py"], timeout=120))
        steps.append(run_server_step("live_launch_kit_api", [PYTHON, "scripts/check_live_launch_kit_api.py"], timeout=240))
        steps.append(run_server_step("live_launch_kit_export", [PYTHON, "scripts/export_live_launch_kit.py"], timeout=360))
        steps.append(run_server_step("live_pilot", [PYTHON, "scripts/check_live_pilot.py"], timeout=120))
        steps.append(run_server_step("live_pilot_postflight", [PYTHON, "scripts/check_live_pilot_postflight.py"], timeout=120))
        steps.append(run_server_step("guarded_live_pilot_runner", [PYTHON, "scripts/check_guarded_live_pilot_runner.py"], timeout=120))
        steps.append(run_server_step("go_live_gate", [PYTHON, "scripts/check_go_live_gate.py"], timeout=120))
        steps.append(run_server_step("live_attestation", [PYTHON, "scripts/check_live_attestation.py"], timeout=60))
        steps.append(run_server_step("live_arming_budget", [PYTHON, "scripts/check_live_arming_budget.py"], timeout=60))
        steps.append(run_server_step("binance_margin_type_sync", [PYTHON, "scripts/check_binance_margin_type_sync.py"], timeout=60))
        steps.append(run_server_step("binance_leverage_sync", [PYTHON, "scripts/check_binance_leverage_sync.py"], timeout=60))
        steps.append(run_server_step("binance_position_mode", [PYTHON, "scripts/check_binance_position_mode.py"], timeout=60))
        steps.append(run_server_step("binance_time_drift", [PYTHON, "scripts/check_binance_time_drift.py"], timeout=60))
        steps.append(run_server_step("go_live_report", [PYTHON, "scripts/check_go_live_report.py"], timeout=120))
        if os.getenv("TRADER_CHECK_TESTNET", "false").lower() == "true":
            steps.append(
                run_server_step(
                    "binance_testnet_validate",
                    [PYTHON, "scripts/check_binance_testnet_validate.py"],
                    timeout=150,
                )
            )
        if os.getenv("TRADER_CHECK_TESTNET_PLACE", "false").lower() == "true":
            steps.append(
                run_server_step(
                    "binance_testnet_place_order",
                    [PYTHON, "scripts/check_binance_testnet_place_order.py"],
                    timeout=180,
                )
            )
    else:
        steps.append(
            {
                "name": "server_available",
                "ok": False,
                "returncode": 1,
                "duration_seconds": 0,
                "command": ["GET", f"{BASE_URL}/api/health"],
                "stdout": "",
                "stderr": "Local service is not reachable. Start it with: py app\\server.py",
            }
        )

    readiness = None
    if health_ok():
        try:
            readiness = fetch_json("/api/readiness")
        except Exception as exc:  # noqa: BLE001 - report should capture any readiness fetch failure.
            readiness = {"overall": "fail", "error": f"{exc.__class__.__name__}: {exc}"}

    ok = all(step["ok"] for step in steps) and (readiness or {}).get("overall") in {"pass", "warn"}
    report = {
        "ok": ok,
        "status": "completed",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "started_at": started_at,
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "project_root": str(ROOT_DIR),
        "base_url": BASE_URL,
        "current_step": {"name": "completed", "status": "completed"},
        "completed_step_count": len(steps),
        "failed_steps": [step["name"] for step in steps if not step["ok"]],
        "final_report_path": str(report_path),
        "steps": steps,
        "readiness": readiness,
    }
    write_json_atomic(report_path, report)
    completed_active_report = build_readiness_report(
        status="completed",
        started_at=started_at,
        steps=list(steps),
        readiness=readiness,
        ok=ok,
        current_step={"name": "completed", "status": "completed", "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")},
        final_report_path=report_path,
    )
    write_json_atomic(active_report_path, completed_active_report)
    write_json_atomic(partial_report_path, completed_active_report)
    ACTIVE_REPORT_WRITER = None

    summary = {
        "ok": ok,
        "report_path": str(report_path),
        "failed_steps": [step["name"] for step in steps if not step["ok"]],
        "readiness": (readiness or {}).get("overall"),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
