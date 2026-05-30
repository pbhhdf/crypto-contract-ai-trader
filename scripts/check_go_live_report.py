from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT_DIR = Path(__file__).resolve().parents[1]
BASE_URL = os.getenv("TRADER_BASE_URL", "http://127.0.0.1:8787").rstrip("/")
AUTH_USER = os.getenv("TRADER_AUTH_USER", os.getenv("APP_BASIC_AUTH_USER", ""))
AUTH_PASSWORD = os.getenv("TRADER_AUTH_PASSWORD", os.getenv("APP_BASIC_AUTH_PASSWORD", ""))


def auth_headers() -> dict[str, str]:
    headers = {"Accept": "application/json"}
    if AUTH_USER and AUTH_PASSWORD:
        token = base64.b64encode(f"{AUTH_USER}:{AUTH_PASSWORD}".encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {token}"
    return headers


def request_json(path: str) -> Any:
    request = Request(f"{BASE_URL}{path}", headers=auth_headers(), method="GET")
    with urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def fail(message: str) -> int:
    print(f"FAILED: {message}", file=sys.stderr)
    return 1


def main() -> int:
    try:
        payload = request_json("/api/go-live-report")
    except HTTPError as exc:
        return fail(f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}")
    except (URLError, TimeoutError, OSError) as exc:
        return fail(f"could not reach {BASE_URL}: {exc}")

    report = payload.get("go_live_report") or {}
    for key in ("verdict", "checklist", "go_live_gate", "readiness", "audit_chain", "oms", "ai_operator"):
        if key not in report:
            return fail(f"go-live report missing {key}")
    checklist_ids = {item.get("id") for item in report.get("checklist") or []}
    required = {
        "deployment_profile",
        "server_private_access",
        "basic_auth",
        "live_flags",
        "live_attestation",
        "live_pilot_capital",
        "exchange_leverage_sync",
        "exchange_margin_type_sync",
        "exchange_position_mode",
        "binance_time_drift",
        "risk_oms_audit",
        "panic_stop_drill",
        "exchange_emergency_controls",
        "alerts_recovery_stream",
        "testnet_drill",
        "backtest_walkforward",
        "short_live_arming",
    }
    missing = sorted(required - checklist_ids)
    if missing:
        return fail(f"go-live report checklist missing {missing}")
    if (report.get("audit_chain") or {}).get("status") != "pass":
        return fail("go-live report audit chain is not passing")
    drill = report.get("testnet_drill") or {}
    drill_cycles = drill.get("cycles") or []
    if drill_cycles:
        latest_cycle = drill_cycles[0]
        if "order_evidence" not in latest_cycle or "real_cycle_counted" not in latest_cycle:
            return fail(f"go-live report does not expose Testnet order evidence: {latest_cycle}")

    export = subprocess.run(
        [sys.executable, "scripts/export_go_live_report.py"],
        cwd=ROOT_DIR,
        text=True,
        capture_output=True,
        timeout=60,
    )
    if export.returncode != 0:
        return fail(export.stderr.strip() or export.stdout.strip() or "export_go_live_report.py failed")
    exported = json.loads(export.stdout)
    for path_key in ("json_path", "markdown_path"):
        path = Path(exported[path_key])
        if not path.exists() or path.stat().st_size == 0:
            return fail(f"exported {path_key} is missing or empty: {path}")

    print(
        json.dumps(
            {
                "ok": True,
                "status": (report.get("verdict") or {}).get("status"),
                "ready_for_live_order": (report.get("verdict") or {}).get("ready_for_live_order"),
                "blocking_gates": (report.get("verdict") or {}).get("blocking_gate_ids"),
                "exported": exported,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
