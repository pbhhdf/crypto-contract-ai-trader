from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import server  # noqa: E402


def fail(message: str, details: object | None = None) -> int:
    print(f"FAILED: {message}", file=sys.stderr)
    if details is not None:
        print(json.dumps(details, ensure_ascii=False, indent=2), file=sys.stderr)
    return 1


def gate_by_id(gate: dict[str, Any], gate_id: str) -> dict[str, Any]:
    for item in gate.get("gates", []):
        if item.get("id") == gate_id:
            return item
    return {}


def readiness_item_by_name(readiness: dict[str, Any], name: str) -> dict[str, Any]:
    for item in readiness.get("items", []):
        if item.get("name") == name:
            return item
    return {}


def main() -> int:
    expected_categories = {
        "127.0.0.1": "loopback",
        "10.0.8.5": "private",
        "100.64.0.10": "tailscale_cgnat",
        "169.254.10.20": "link_local",
        "8.8.8.8": "public",
        "0.0.0.0": "wildcard",
        "trader.internal": "invalid_ip",
    }
    profiles = {value: server.private_bind_profile(value) for value in expected_categories}
    for value, category in expected_categories.items():
        if profiles[value].get("category") != category:
            return fail(f"unexpected private bind profile for {value}", profiles[value])
    for value in ("127.0.0.1", "10.0.8.5", "100.64.0.10", "169.254.10.20"):
        if profiles[value].get("ok") is not True:
            return fail(f"private bind profile should pass for {value}", profiles[value])
    for value in ("8.8.8.8", "0.0.0.0", "trader.internal"):
        if profiles[value].get("ok") is not False:
            return fail(f"private bind profile should fail for {value}", profiles[value])

    original = {
        "APP_ENV": server.APP_ENV,
        "AUTH_ENABLED": server.AUTH_ENABLED,
        "TRADER_BIND_IP": server.TRADER_BIND_IP,
    }
    try:
        server.APP_ENV = "server"
        server.AUTH_ENABLED = True

        server.TRADER_BIND_IP = "8.8.8.8"
        public_gate = gate_by_id(server.go_live_gate_status(), "private_network")
        if public_gate.get("status") != "fail":
            return fail("go-live gate did not fail a public TRADER_BIND_IP", public_gate)
        if (public_gate.get("evidence") or {}).get("bind_profile", {}).get("category") != "public":
            return fail("go-live gate did not expose public bind evidence", public_gate)
        readiness_item = readiness_item_by_name(server.deployment_readiness(), "Private network access")
        if readiness_item.get("status") != "fail":
            return fail("deployment readiness did not fail a public TRADER_BIND_IP", readiness_item)

        server.TRADER_BIND_IP = "100.64.0.10"
        tailscale_gate = gate_by_id(server.go_live_gate_status(), "private_network")
        if tailscale_gate.get("status") != "pass":
            return fail("go-live gate did not pass a Tailscale TRADER_BIND_IP", tailscale_gate)
        if (tailscale_gate.get("evidence") or {}).get("bind_profile", {}).get("category") != "tailscale_cgnat":
            return fail("go-live gate did not expose Tailscale bind evidence", tailscale_gate)
    finally:
        server.APP_ENV = original["APP_ENV"]
        server.AUTH_ENABLED = original["AUTH_ENABLED"]
        server.TRADER_BIND_IP = original["TRADER_BIND_IP"]

    print(json.dumps({"ok": True, "profiles": profiles}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
