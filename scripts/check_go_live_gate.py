from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT_DIR = Path(__file__).resolve().parents[1]


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
HTTP_TIMEOUT_SECONDS = float(os.getenv("TRADER_HTTP_TIMEOUT_SECONDS", "90"))


def auth_headers() -> dict[str, str]:
    headers = {"Accept": "application/json"}
    if AUTH_USER and AUTH_PASSWORD:
        token = base64.b64encode(f"{AUTH_USER}:{AUTH_PASSWORD}".encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {token}"
    return headers


def request_json(method: str, path: str, body: dict[str, Any] | None = None) -> Any:
    headers = auth_headers()
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    request = Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
    with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def fail(message: str) -> int:
    print(f"FAILED: {message}", file=sys.stderr)
    return 1


def validate_gate(gate: dict[str, Any], enabled_modes: list[str]) -> str | None:
    required_ids = {
        "deployment_profile",
        "live_flags",
        "live_attestation",
        "live_pilot_capital",
        "risk_controls",
        "exchange_margin_type_sync",
        "exchange_leverage_sync",
        "exchange_position_mode",
        "binance_time_drift",
        "panic_stop_drill",
        "exchange_emergency_controls",
        "backup_restore_drill",
        "oms_reconciled",
        "audit_chain",
        "alert_watchdog",
        "exchange_recovery",
        "private_user_stream",
        "testnet_drill_cycles",
        "backtest_walkforward",
        "live_arming",
    }
    gate_ids = {item.get("id") for item in gate.get("gates", [])}
    missing = sorted(required_ids - gate_ids)
    if missing:
        return f"go-live gate is missing checks: {missing}"
    live_mode_enabled = "live_guarded" in enabled_modes
    if gate.get("live_mode_enabled") is not live_mode_enabled:
        return "go-live gate live_mode_enabled does not match enabled modes"
    if gate.get("ready_for_live_order"):
        if not live_mode_enabled:
            return "ready_for_live_order is true without live_guarded mode"
        if gate.get("blocking_gates"):
            return "ready_for_live_order is true while blocking gates remain"
    else:
        if live_mode_enabled and not gate.get("blocking_gates"):
            return "live_guarded is enabled but gate is not ready and has no blockers"
    return None


def main() -> int:
    try:
        state = request_json("GET", "/api/state?include_checks=true")
        gate_response = request_json("GET", "/api/go-live-gate")
        check_response = request_json("POST", "/api/go-live-gate/check", {})
        arming_response = request_json("GET", "/api/live-arming")
        bad_arm_response = None
        try:
            request_json("POST", "/api/live-arming/arm", {"confirmation": "WRONG"})
            return fail("live arming accepted an invalid confirmation phrase")
        except HTTPError as exc:
            if exc.code != 400:
                return fail(f"live arming invalid confirmation returned HTTP {exc.code}")
            bad_arm_response = json.loads(exc.read().decode("utf-8"))
    except HTTPError as exc:
        return fail(f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}")
    except (URLError, TimeoutError, OSError) as exc:
        return fail(f"could not reach {BASE_URL}: {exc}")

    enabled_modes = state.get("config", {}).get("enabled_modes") or []
    state_gate = state.get("go_live_gate") or {}
    endpoint_gate = gate_response.get("go_live_gate") or {}
    checked_gate = check_response.get("go_live_gate") or {}
    arming = arming_response.get("live_arming") or {}
    if not arming:
        return fail("/api/live-arming does not expose live_arming")
    if "confirmation_phrase" not in arming:
        return fail("live arming status does not expose the confirmation phrase")
    for key in ("max_orders", "order_count", "remaining_orders"):
        if key not in arming:
            return fail(f"live arming status does not expose {key}")
    if not (bad_arm_response or {}).get("error"):
        return fail("invalid live arming response did not include an error")
    if not state_gate:
        return fail("/api/state does not include go_live_gate")
    for source, gate in {
        "state": state_gate,
        "endpoint": endpoint_gate,
        "check": checked_gate,
    }.items():
        error = validate_gate(gate, enabled_modes)
        if error:
            return fail(f"{source}: {error}")

    readiness_names = {item.get("name") for item in (state.get("readiness") or {}).get("items", [])}
    if "Go-live gate" not in readiness_names:
        return fail("readiness does not expose Go-live gate")

    print(
        json.dumps(
            {
                "ok": True,
                "status": endpoint_gate.get("status"),
                "ready_to_enable_live": endpoint_gate.get("ready_to_enable_live"),
                "ready_to_arm_live": endpoint_gate.get("ready_to_arm_live"),
                "ready_for_live_order": endpoint_gate.get("ready_for_live_order"),
                "live_armed": arming.get("armed"),
                "blocking_gates": [item.get("id") for item in endpoint_gate.get("blocking_gates", [])],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
