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


def main() -> int:
    try:
        initial = request_json("GET", "/api/exchange/recovery")
        recovered = request_json("POST", "/api/exchange/recover", {})
        state = request_json("GET", "/api/state")
    except HTTPError as exc:
        return fail(f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}")
    except (URLError, TimeoutError, OSError) as exc:
        return fail(f"could not reach {BASE_URL}: {exc}")

    recovery = recovered.get("exchange_recovery") or {}
    report = recovered.get("report") or {}
    if "user_stream" not in recovery:
        return fail("exchange recovery response does not expose user stream status")
    if "stream_summary" not in recovery:
        return fail("exchange recovery response does not expose private stream event summary")
    if "orders" not in report or "summary" not in (report.get("orders") or {}):
        return fail("exchange recovery report does not include OMS summary")
    state_recovery = state.get("exchange_recovery") or {}
    if not state_recovery.get("last_at"):
        return fail("/api/state does not expose exchange recovery last_at")
    readiness_names = {item.get("name") for item in (state.get("readiness") or {}).get("items", [])}
    if "Exchange recovery" not in readiness_names:
        return fail("readiness does not include Exchange recovery")

    print(
        json.dumps(
            {
                "ok": True,
                "initial_last_at": (initial.get("exchange_recovery") or {}).get("last_at"),
                "recovered_last_at": recovery.get("last_at"),
                "orders": (report.get("orders") or {}).get("summary"),
                "snapshots": len(recovery.get("snapshots") or []),
                "stream_events": (recovery.get("stream_summary") or {}).get("recent_count"),
                "user_stream_status": (recovery.get("user_stream") or {}).get("status"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
