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


def headers() -> dict[str, str]:
    result = {"Accept": "application/json"}
    if AUTH_USER and AUTH_PASSWORD:
        token = base64.b64encode(f"{AUTH_USER}:{AUTH_PASSWORD}".encode("utf-8")).decode("ascii")
        result["Authorization"] = f"Basic {token}"
    return result


def request_json(method: str, path: str, body: dict[str, Any] | None = None) -> Any:
    payload = json.dumps(body or {}).encode("utf-8") if body is not None else None
    request_headers = headers()
    if payload is not None:
        request_headers["Content-Type"] = "application/json"
    request = Request(
        f"{BASE_URL}{path}",
        data=payload,
        headers=request_headers,
        method=method,
    )
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def fail(message: str) -> int:
    print(f"FAILED: {message}", file=sys.stderr)
    return 1


def find_alert(payload: dict[str, Any], key: str) -> dict[str, Any] | None:
    for alert in payload.get("alerts", []):
        if alert.get("key") == key:
            return alert
    return None


def main() -> int:
    try:
        request_json("POST", "/api/reset-emergency-stop", {})
        state = request_json("GET", "/api/state")
        readiness_names = {item.get("name") for item in (state.get("readiness") or {}).get("items", [])}
        if "Alert watchdog" not in readiness_names:
            return fail("readiness does not include Alert watchdog")

        request_json("POST", "/api/emergency-stop", {})
        active = request_json("POST", "/api/alerts/check", {})
        emergency = find_alert(active, "risk.emergency_stop")
        if not emergency:
            return fail("emergency stop did not raise a watchdog alert")
        if emergency.get("severity") != "critical" or emergency.get("status") != "open":
            return fail(f"unexpected emergency alert state: {emergency}")

        acknowledged = request_json("POST", f"/api/alerts/{emergency['id']}/ack", {})
        ack_alert = acknowledged.get("alert") or {}
        if ack_alert.get("status") != "acknowledged":
            return fail(f"alert acknowledge failed: {ack_alert}")

        request_json("POST", "/api/reset-emergency-stop", {})
        cleared = request_json("POST", "/api/alerts/check", {})
        if find_alert(cleared, "risk.emergency_stop"):
            return fail("emergency stop alert is still active after reset")
        resolved_history = request_json("GET", "/api/alerts?include_resolved=true&limit=100")
    except HTTPError as exc:
        return fail(f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}")
    except (URLError, TimeoutError, OSError) as exc:
        return fail(f"could not reach {BASE_URL}: {exc}")

    resolved = find_alert(resolved_history, "risk.emergency_stop")
    if not resolved or resolved.get("status") != "resolved":
        return fail(f"resolved emergency alert not found in history: {resolved}")

    print(
        json.dumps(
            {
                "ok": True,
                "raised_alert_id": emergency["id"],
                "resolved_status": resolved.get("status"),
                "active_after_clear": (cleared.get("summary") or {}).get("active"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
