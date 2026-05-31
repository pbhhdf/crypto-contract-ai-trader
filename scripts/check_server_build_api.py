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


def auth_headers() -> dict[str, str]:
    headers = {"Accept": "application/json"}
    if AUTH_USER and AUTH_PASSWORD:
        token = base64.b64encode(f"{AUTH_USER}:{AUTH_PASSWORD}".encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {token}"
    return headers


def request_json(path: str, timeout: int = 10) -> dict[str, Any]:
    request = Request(f"{BASE_URL}{path}", headers=auth_headers(), method="GET")
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def fail(message: str, payload: object | None = None) -> int:
    print(f"FAILED: {message}", file=sys.stderr)
    if payload is not None:
        print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
    return 1


def validate_build(build: object, *, expected_fingerprint: str, source: str) -> tuple[bool, str, dict[str, Any]]:
    if not isinstance(build, dict):
        return False, f"{source} payload is missing build metadata; restart the server with the current code", {}
    actual_fingerprint = str(build.get("server_fingerprint") or "")
    if actual_fingerprint != expected_fingerprint:
        return (
            False,
            f"{source} build fingerprint does not match current app/server.py",
            {
                "expected_fingerprint": expected_fingerprint,
                "actual_fingerprint": actual_fingerprint,
                "server_pid": build.get("server_pid"),
                "server_started_at": build.get("server_started_at"),
            },
        )
    if not build.get("server_started_at") or not build.get("server_pid"):
        return False, f"{source} build metadata is incomplete", build
    return True, "", build


def main() -> int:
    try:
        health = request_json("/api/health")
    except HTTPError as exc:
        return fail(f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}")
    except (URLError, TimeoutError, OSError) as exc:
        return fail(f"could not verify server build at {BASE_URL}: {exc}")

    expected_fingerprint = hashlib.sha256((ROOT_DIR / "app" / "server.py").read_bytes()).hexdigest()
    ok, message, build = validate_build(health.get("build"), expected_fingerprint=expected_fingerprint, source="health")
    if not ok:
        return fail(message, {"base_url": BASE_URL, **build})

    try:
        state = request_json("/api/state")
    except HTTPError as exc:
        return fail(f"state HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}")
    except (URLError, TimeoutError, OSError) as exc:
        return fail(f"could not verify state build metadata at {BASE_URL}: {exc}")
    state_build = (state.get("system") or {}).get("build")
    ok, message, state_build_payload = validate_build(
        state_build,
        expected_fingerprint=expected_fingerprint,
        source="state",
    )
    if not ok:
        return fail(message, {"base_url": BASE_URL, **state_build_payload})

    print(
        json.dumps(
            {
                "ok": True,
                "base_url": BASE_URL,
                "server_pid": build.get("server_pid"),
                "server_started_at": build.get("server_started_at"),
                "server_fingerprint": expected_fingerprint[:16],
                "state_build_visible": True,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
