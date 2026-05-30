from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT_DIR = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT_DIR / "reports"


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
AUTH_USER = os.getenv("TRADER_AUTH_USER", os.getenv("APP_BASIC_AUTH_USER", ""))
AUTH_PASSWORD = os.getenv("TRADER_AUTH_PASSWORD", os.getenv("APP_BASIC_AUTH_PASSWORD", ""))
HTTP_TIMEOUT_SECONDS = float(os.getenv("TRADER_HTTP_TIMEOUT_SECONDS", "60"))


def utc_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def auth_headers() -> dict[str, str]:
    headers = {"Accept": "application/json"}
    if AUTH_USER and AUTH_PASSWORD:
        token = base64.b64encode(f"{AUTH_USER}:{AUTH_PASSWORD}".encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {token}"
    return headers


def request_json(method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
    body = None
    headers = auth_headers()
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(f"{BASE_URL}{path}", data=body, headers=headers, method=method)
    with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def write_report(report: dict[str, Any]) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"guarded-live-pilot-{utc_slug()}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def fail(message: str, report: dict[str, Any]) -> int:
    report["ok"] = False
    report["error"] = message
    report["completed_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    report["report_path"] = str(write_report(report))
    print(json.dumps(report, ensure_ascii=False, indent=2), file=sys.stderr)
    return 1


def latest_run_by_id(run_id: str) -> dict[str, Any] | None:
    runs = request_json("GET", "/api/runs?limit=25").get("runs") or []
    for run in runs:
        if run.get("id") == run_id:
            return run
    return None


def wait_for_run(run_id: str, wait_seconds: float, poll_interval: float) -> dict[str, Any]:
    deadline = time.time() + max(0.0, wait_seconds)
    terminal = {"completed", "failed"}
    last = latest_run_by_id(run_id) or {"id": run_id, "status": "unknown"}
    while time.time() < deadline:
        current = latest_run_by_id(run_id)
        if current:
            last = current
            if str(current.get("status") or "").lower() in terminal:
                break
        time.sleep(max(0.5, poll_interval))
    return last


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the final guarded live pilot sequence through the HTTP control plane. "
            "It never changes env flags; all real trading remains behind final-live-ready, "
            "ARM_LIVE_TRADING, LAUNCH_LIVE_PILOT, OMS, and RMS."
        )
    )
    parser.add_argument("--symbol", default=os.getenv("TRADER_SYMBOL", "BTCUSDT"))
    parser.add_argument("--plan-only", action="store_true", help="Collect status and write a report without mutating state.")
    parser.add_argument("--attest", action="store_true", help="Save live attestation before arming.")
    parser.add_argument("--attestation-confirmation", default=os.getenv("LIVE_ATTESTATION_CONFIRMATION", ""))
    parser.add_argument("--actor", default=os.getenv("TRADER_OPERATOR_ACTOR", "codex_operator"))
    parser.add_argument("--note", default=os.getenv("TRADER_LIVE_PILOT_NOTE", "guarded live pilot"))
    parser.add_argument("--arm", action="store_true", help="Arm the short live window before launching.")
    parser.add_argument("--arm-confirmation", default=os.getenv("LIVE_ARM_CONFIRMATION", ""))
    parser.add_argument("--ttl-seconds", type=int, default=int(os.getenv("TRADER_LIVE_ARM_TTL_SECONDS", "300")))
    parser.add_argument("--launch", action="store_true", help="Launch exactly one live_guarded pilot workflow.")
    parser.add_argument("--launch-confirmation", default=os.getenv("LIVE_PILOT_CONFIRMATION", ""))
    parser.add_argument("--wait-seconds", type=float, default=float(os.getenv("TRADER_LIVE_PILOT_WAIT_SECONDS", "180")))
    parser.add_argument("--poll-interval", type=float, default=float(os.getenv("TRADER_LIVE_PILOT_POLL_INTERVAL", "2")))
    parser.add_argument("--keep-armed", action="store_true", help="Do not disarm after this script finishes.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    symbol = args.symbol.upper().strip()
    report: dict[str, Any] = {
        "ok": False,
        "base_url": BASE_URL,
        "symbol": symbol,
        "plan_only": args.plan_only,
        "attest": args.attest,
        "arm": args.arm,
        "launch": args.launch,
        "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "steps": [],
    }
    armed_by_script = False
    try:
        query = urlencode({"symbol": symbol})
        report["initial_final_live_ready_prearm"] = request_json("GET", "/api/final-live-ready?require_armed=false").get("final_live_ready")
        report["initial_final_live_ready_armed"] = request_json("GET", "/api/final-live-ready").get("final_live_ready")
        report["initial_live_pilot"] = request_json("GET", f"/api/live-pilot?{query}").get("live_pilot")

        if args.plan_only:
            report["ok"] = True
            report["completed_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            report["report_path"] = str(write_report(report))
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0

        if args.attest:
            if args.attestation_confirmation != "LIVE_ATTESTATION_CONFIRMED":
                return fail("attestation requires --attestation-confirmation LIVE_ATTESTATION_CONFIRMED", report)
            attest_payload = {
                "confirmation": args.attestation_confirmation,
                "actor": args.actor,
                "note": args.note,
                "accepted": {
                    "withdrawal_disabled": True,
                    "ip_whitelisted": True,
                    "jurisdiction_ok": True,
                    "offserver_backup_copied": True,
                    "pilot_capital_limit_ok": True,
                },
            }
            report["steps"].append({"name": "live_attestation", "result": request_json("POST", "/api/live-attestation", attest_payload)})

        if args.arm:
            if args.arm_confirmation != "ARM_LIVE_TRADING":
                return fail("live arming requires --arm-confirmation ARM_LIVE_TRADING", report)
            arm_payload = {
                "confirmation": args.arm_confirmation,
                "ttl_seconds": args.ttl_seconds,
                "actor": args.actor,
                "reason": args.note,
            }
            report["steps"].append({"name": "live_arm", "result": request_json("POST", "/api/live-arming/arm", arm_payload)})
            armed_by_script = True

        report["pre_launch_final_live_ready"] = request_json("GET", "/api/final-live-ready").get("final_live_ready")
        report["pre_launch_live_pilot"] = request_json("GET", f"/api/live-pilot?{query}").get("live_pilot")

        if args.launch:
            if args.launch_confirmation != "LAUNCH_LIVE_PILOT":
                return fail("live pilot launch requires --launch-confirmation LAUNCH_LIVE_PILOT", report)
            launch = request_json("POST", "/api/live-pilot/run", {"symbol": symbol, "confirmation": args.launch_confirmation})
            report["steps"].append({"name": "live_pilot_run", "result": launch})
            run_id = ((launch.get("run") or {}).get("id") or "")
            if run_id:
                report["run_id"] = run_id
                report["final_run"] = wait_for_run(run_id, args.wait_seconds, args.poll_interval)
            report["steps"].append({"name": "oms_reconcile", "result": request_json("POST", "/api/oms/reconcile", {})})
            report["post_launch_oms"] = request_json("GET", "/api/oms")
            postflight_query = urlencode({"symbol": symbol, "run_id": run_id}) if run_id else urlencode({"symbol": symbol})
            report["post_launch_postflight"] = request_json("GET", f"/api/live-pilot-postflight?{postflight_query}").get("live_pilot_postflight")

        report["final_live_pilot"] = request_json("GET", f"/api/live-pilot?{query}").get("live_pilot")
        report["final_postflight"] = request_json("GET", f"/api/live-pilot-postflight?{query}").get("live_pilot_postflight")
        report["final_go_live_gate"] = request_json("GET", "/api/go-live-gate").get("go_live_gate")
        report["ok"] = (not args.launch) or str((report.get("final_run") or {}).get("status") or "").lower() == "completed"
        report["completed_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        return_code = 0 if report["ok"] else 1
        return return_code
    except HTTPError as exc:
        raw_body = exc.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(raw_body)
        except json.JSONDecodeError:
            body = {"raw": raw_body}
        report["http_error"] = {"status": exc.code, "body": body}
        return fail(f"HTTP {exc.code}", report)
    except (URLError, TimeoutError, OSError, RuntimeError, ValueError) as exc:
        return fail(f"{exc.__class__.__name__}: {exc}", report)
    finally:
        if not args.keep_armed and armed_by_script:
            try:
                report["steps"].append({
                    "name": "live_disarm",
                    "result": request_json("POST", "/api/live-arming/disarm", {"reason": "guarded_live_pilot_script_finished"}),
                })
            except Exception as exc:  # noqa: BLE001
                report["disarm_error"] = f"{exc.__class__.__name__}: {exc}"
        if "report_path" not in report:
            report["report_path"] = str(write_report(report))
            print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
