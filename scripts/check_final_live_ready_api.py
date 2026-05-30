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


def auth_headers() -> dict[str, str]:
    headers = {"Accept": "application/json"}
    if AUTH_USER and AUTH_PASSWORD:
        token = base64.b64encode(f"{AUTH_USER}:{AUTH_PASSWORD}".encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {token}"
    return headers


def fail(message: str, payload: dict[str, Any] | None = None) -> int:
    print(f"FAILED: {message}", file=sys.stderr)
    if payload:
        print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
    return 1


def main() -> int:
    try:
        request = Request(f"{BASE_URL}/api/final-live-ready", headers=auth_headers(), method="GET")
        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        return fail(f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}")
    except (URLError, TimeoutError, OSError) as exc:
        return fail(f"could not reach {BASE_URL}: {exc}")

    status = payload.get("final_live_ready")
    if not isinstance(status, dict):
        return fail("endpoint did not return final_live_ready object", payload)

    required_keys = {
        "ok",
        "status",
        "ready_to_enable_live",
        "ready_to_arm_live",
        "ready_for_live_order",
        "blocking_gates",
        "failures",
        "report",
    }
    missing = sorted(required_keys - set(status))
    if missing:
        return fail(f"missing keys: {', '.join(missing)}", status)
    if status["ok"] and status.get("status") != "pass":
        return fail("ok=true must report status=pass", status)
    if not status["ok"] and not isinstance(status.get("failures"), list):
        return fail("blocked readiness must include a failures list", status)

    summary = {
        "ok": True,
        "endpoint_ok": status["ok"],
        "status": status.get("status"),
        "blocking_gates": status.get("blocking_gates"),
        "failure_count": len(status.get("failures") or []),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
