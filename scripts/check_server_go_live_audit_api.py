from __future__ import annotations

import base64
import hashlib
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


def fail(message: str, payload: object | None = None) -> int:
    print(f"FAILED: {message}", file=sys.stderr)
    if payload is not None:
        print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
    return 1


def request_json(path: str) -> Any:
    request = Request(f"{BASE_URL}{path}", headers=auth_headers(), method="GET")
    with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    try:
        payload = request_json("/api/server-go-live-audit")
    except HTTPError as exc:
        return fail(f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}")
    except (URLError, TimeoutError, OSError) as exc:
        return fail(f"could not reach {BASE_URL}: {exc}")
    audit = payload.get("server_go_live_audit") or payload
    if not isinstance(audit, dict):
        return fail("server-go-live-audit endpoint did not return an object", payload)
    required = {
        "health",
        "readiness",
        "go_live_gate",
        "final_live_ready_prearm",
        "final_live_ready_armed",
        "ai_operator",
        "go_live_report",
    }
    missing = sorted(required - set(audit))
    if missing:
        return fail(f"audit missing keys: {', '.join(missing)}", audit)
    build = (audit.get("health") or {}).get("build")
    expected_fingerprint = hashlib.sha256((ROOT_DIR / "app" / "server.py").read_bytes()).hexdigest()
    if not isinstance(build, dict):
        return fail("server-go-live-audit health is missing build metadata", audit.get("health"))
    if build.get("server_fingerprint") != expected_fingerprint:
        return fail(
            "server-go-live-audit build fingerprint does not match current app/server.py",
            {
                "expected_fingerprint": expected_fingerprint,
                "actual_fingerprint": build.get("server_fingerprint"),
                "server_pid": build.get("server_pid"),
                "server_started_at": build.get("server_started_at"),
            },
        )
    operator = (audit.get("ai_operator") or {}).get("status") or {}
    if not operator.get("enabled"):
        return fail("AI operator should be visible in server audit", operator)
    print(
        json.dumps(
            {
                "ok": True,
                "readiness": (audit.get("readiness") or {}).get("overall"),
                "prearm_ok": (audit.get("final_live_ready_prearm") or {}).get("ok"),
                "armed_ok": (audit.get("final_live_ready_armed") or {}).get("ok"),
                "server_fingerprint": expected_fingerprint[:16],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
