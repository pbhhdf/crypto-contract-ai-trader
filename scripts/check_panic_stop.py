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


def assert_bad_confirmation_rejected() -> str:
    try:
        request_json("POST", "/api/panic-stop", {"confirmation": "WRONG"})
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        if exc.code == 400 and "PANIC_STOP" in body:
            return body
        raise
    raise AssertionError("panic stop accepted an invalid confirmation")


def cleanup() -> None:
    try:
        request_json("POST", "/api/reset-emergency-stop", {"reason": "check_panic_stop_cleanup"})
    except Exception:
        pass
    try:
        alerts = request_json("GET", "/api/alerts?include_resolved=false").get("alerts") or []
        for alert in alerts:
            if alert.get("key") in {"panic_stop.active", "risk.emergency_stop"}:
                request_json("POST", f"/api/alerts/{alert['id']}/resolve")
    except Exception:
        pass
    try:
        request_json("POST", "/api/scheduler", {"enabled": False, "symbol": "BTCUSDT", "mode": "paper", "interval_seconds": 3600})
    except Exception:
        pass
    try:
        request_json(
            "POST",
            "/api/testnet-drill",
            {
                "enabled": False,
                "symbol": "BTCUSDT",
                "mode": "binance_testnet_validate",
                "interval_minutes": 30,
                "target_cycles": 24,
            },
        )
    except Exception:
        pass


def main() -> int:
    try:
        request_json("POST", "/api/scheduler", {"enabled": True, "symbol": "BTCUSDT", "mode": "paper", "interval_seconds": 3600})
        rejected_body = assert_bad_confirmation_rejected()
        response = request_json(
            "POST",
            "/api/panic-stop",
            {
                "confirmation": "PANIC_STOP",
                "reason": "smoke test panic stop",
                "cancel_orders": True,
                "reconcile": True,
            },
        )
        panic = response.get("panic_stop") or {}
        if panic.get("status") != "panic_stop_active":
            return fail(f"unexpected panic status: {panic}")
        if not panic.get("emergency_stop"):
            return fail("panic stop did not enable emergency_stop")
        if panic.get("scheduler_enabled"):
            return fail("panic stop did not disable scheduler")
        if panic.get("testnet_drill_enabled"):
            return fail("panic stop did not disable testnet drill")
        if not isinstance(panic.get("cancel_attempts"), list):
            return fail("panic stop response does not include cancel_attempts")
        if (response.get("live_arming") or {}).get("armed"):
            return fail("panic stop did not disarm live trading")

        state = request_json("GET", "/api/state")
        if not (state.get("system") or {}).get("emergency_stop"):
            return fail("state does not show emergency stop after panic")
        if (state.get("scheduler") or {}).get("enabled"):
            return fail("state scheduler is still enabled after panic")
        if (state.get("testnet_drill") or {}).get("enabled"):
            return fail("state testnet drill is still enabled after panic")
        cleanup()
        final_state = request_json("GET", "/api/state")
        if (final_state.get("system") or {}).get("emergency_stop"):
            return fail("emergency stop cleanup failed")

        print(
            json.dumps(
                {
                    "ok": True,
                    "invalid_confirmation_rejected": "PANIC_STOP" in rejected_body,
                    "cancel_attempts": len(panic.get("cancel_attempts") or []),
                    "cancel_failed": len(panic.get("cancel_failed") or []),
                    "oms": panic.get("oms"),
                    "scheduler_enabled_after_cleanup": (final_state.get("scheduler") or {}).get("enabled"),
                    "emergency_stop_after_cleanup": (final_state.get("system") or {}).get("emergency_stop"),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    except AssertionError as exc:
        cleanup()
        return fail(str(exc))
    except HTTPError as exc:
        cleanup()
        return fail(f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}")
    except (URLError, TimeoutError, OSError) as exc:
        cleanup()
        return fail(f"could not validate panic stop: {exc}")


if __name__ == "__main__":
    raise SystemExit(main())
