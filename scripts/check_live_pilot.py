from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
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
    request = Request(f"{BASE_URL}{path}", data=payload, headers=request_headers, method=method)
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def fail(message: str, payload: Any | None = None) -> int:
    print(f"FAILED: {message}", file=sys.stderr)
    if payload is not None:
        print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
    return 1


def main() -> int:
    symbol = os.getenv("TRADER_TEST_SYMBOL", "BTCUSDT")
    try:
        query = urlencode({"symbol": symbol})
        payload = request_json("GET", f"/api/live-pilot?{query}")
        pilot = payload.get("live_pilot") or {}
        if not pilot:
            return fail("live pilot endpoint did not return live_pilot", payload)
        for key in ("status", "symbol", "can_launch", "confirmation_phrase", "prearm_ready", "armed_ready", "safety_contract"):
            if key not in pilot:
                return fail(f"live pilot status missing {key}", pilot)
        if pilot.get("confirmation_phrase") != "LAUNCH_LIVE_PILOT":
            return fail("live pilot confirmation phrase changed", pilot)
        if pilot.get("can_launch") and pilot.get("status") != "ready":
            return fail("live pilot can_launch requires ready status", pilot)
        before = request_json("GET", "/api/runs?limit=1").get("runs") or []
        try:
            request_json("POST", "/api/live-pilot/run", {"symbol": symbol, "confirmation": "WRONG"})
            return fail("live pilot accepted a wrong confirmation phrase")
        except HTTPError as exc:
            raw_error = exc.read().decode("utf-8", errors="replace")
            if exc.code != 400:
                return fail(f"wrong confirmation returned HTTP {exc.code}", raw_error)
            error_payload = json.loads(raw_error)
            if "confirmation=LAUNCH_LIVE_PILOT" not in (error_payload.get("error") or ""):
                return fail("wrong confirmation response did not explain the required phrase", error_payload)
        after = request_json("GET", "/api/runs?limit=1").get("runs") or []
        if (before[:1] or [{}])[0].get("id") != (after[:1] or [{}])[0].get("id"):
            return fail("wrong confirmation unexpectedly created a run", {"before": before[:1], "after": after[:1]})
    except HTTPError as exc:
        return fail(f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}")
    except (URLError, TimeoutError, OSError) as exc:
        return fail(f"could not reach {BASE_URL}: {exc}")

    print(
        json.dumps(
            {
                "ok": True,
                "status": pilot.get("status"),
                "can_launch": pilot.get("can_launch"),
                "symbol": pilot.get("symbol"),
                "failure_count": len(pilot.get("failures") or []),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
