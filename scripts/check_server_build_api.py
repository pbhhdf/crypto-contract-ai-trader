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


def main() -> int:
    try:
        health = request_json("/api/health")
    except HTTPError as exc:
        return fail(f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}")
    except (URLError, TimeoutError, OSError) as exc:
        return fail(f"could not verify server build at {BASE_URL}: {exc}")

    build = health.get("build")
    if not isinstance(build, dict):
        return fail("health payload is missing build metadata; restart the server with the current code", health)

    expected_fingerprint = hashlib.sha256((ROOT_DIR / "app" / "server.py").read_bytes()).hexdigest()
    actual_fingerprint = str(build.get("server_fingerprint") or "")
    if actual_fingerprint != expected_fingerprint:
        return fail(
            "running server does not match current app/server.py; restart the service before validation",
            {
                "base_url": BASE_URL,
                "expected_fingerprint": expected_fingerprint,
                "actual_fingerprint": actual_fingerprint,
                "server_pid": build.get("server_pid"),
                "server_started_at": build.get("server_started_at"),
            },
        )
    if not build.get("server_started_at") or not build.get("server_pid"):
        return fail("build metadata is incomplete", build)

    print(
        json.dumps(
            {
                "ok": True,
                "base_url": BASE_URL,
                "server_pid": build.get("server_pid"),
                "server_started_at": build.get("server_started_at"),
                "server_fingerprint": actual_fingerprint[:16],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
