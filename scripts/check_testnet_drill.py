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
    with urlopen(request, timeout=45) as response:
        return json.loads(response.read().decode("utf-8"))


def fail(message: str) -> int:
    print(f"FAILED: {message}", file=sys.stderr)
    return 1


def main() -> int:
    try:
        state = request_json("GET", "/api/state")
        readiness_names = {item.get("name") for item in (state.get("readiness") or {}).get("items", [])}
        if "Testnet drill" not in readiness_names:
            return fail("readiness does not include Testnet drill")

        configured = request_json(
            "POST",
            "/api/testnet-drill",
            {
                "enabled": False,
                "symbol": "BTCUSDT",
                "mode": "binance_testnet_validate",
                "interval_minutes": 30,
                "target_cycles": 2,
            },
        )
        drill = configured.get("testnet_drill") or {}
        if drill.get("enabled"):
            return fail(f"drill should be disabled during local smoke test: {drill}")

        payload = request_json("POST", "/api/testnet-drill/run-now", {"dry_run": True})
        cycle = payload.get("cycle") or {}
        if cycle.get("status") not in {"completed", "failed"}:
            return fail(f"unexpected cycle status: {cycle}")
        if "dry_run" not in (cycle.get("note") or ""):
            return fail(f"cycle note does not document dry_run: {cycle.get('note')}")
        if not isinstance(cycle.get("recovery_report"), dict):
            return fail("cycle recovery_report is missing")
        if not isinstance(cycle.get("alert_summary"), dict):
            return fail("cycle alert_summary is missing")
        if not isinstance(cycle.get("stream_summary"), dict):
            return fail("cycle stream_summary is missing")

        refreshed = request_json("GET", "/api/testnet-drill")
        refreshed_drill = refreshed.get("testnet_drill") or {}
        for required_key in ("real_completed_cycles", "dry_run_completed_cycles", "remaining_real_cycles"):
            if refreshed_drill.get(required_key) is None:
                return fail(f"testnet drill status is missing {required_key}: {refreshed_drill}")
        if refreshed_drill.get("last_cycle_id") != cycle.get("id"):
            return fail(f"last cycle id was not persisted: {refreshed_drill}")
        if not refreshed_drill.get("cycles"):
            return fail("testnet drill cycle history is empty")
        if refreshed_drill.get("real_completed_cycles", 0) > refreshed_drill.get("completed_cycles", 0):
            return fail(f"real cycle count cannot exceed total cycles: {refreshed_drill}")
        if refreshed_drill.get("last_real_cycle_id") == cycle.get("id"):
            return fail("dry_run cycle was incorrectly recorded as a real Binance Testnet cycle")
    except HTTPError as exc:
        return fail(f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}")
    except (URLError, TimeoutError, OSError) as exc:
        return fail(f"could not reach {BASE_URL}: {exc}")

    print(
        json.dumps(
            {
                "ok": True,
                "cycle_id": cycle["id"],
                "cycle_status": cycle["status"],
                "last_cycle_id": refreshed_drill.get("last_cycle_id"),
                "completed_cycles": refreshed_drill.get("completed_cycles"),
                "real_completed_cycles": refreshed_drill.get("real_completed_cycles"),
                "dry_run_completed_cycles": refreshed_drill.get("dry_run_completed_cycles"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
