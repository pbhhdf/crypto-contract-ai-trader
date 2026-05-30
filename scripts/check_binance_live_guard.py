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


def request_json(method: str, path: str) -> Any:
    headers = {"Accept": "application/json"}
    if AUTH_USER and AUTH_PASSWORD:
        token = base64.b64encode(f"{AUTH_USER}:{AUTH_PASSWORD}".encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {token}"
    request = Request(f"{BASE_URL}{path}", headers=headers, method=method)
    with urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def fail(message: str) -> int:
    print(f"FAILED: {message}", file=sys.stderr)
    return 1


def main() -> int:
    try:
        state = request_json("GET", "/api/state")
    except HTTPError as exc:
        return fail(f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}")
    except (URLError, TimeoutError, OSError) as exc:
        return fail(f"could not reach {BASE_URL}: {exc}")

    config = state.get("config") or {}
    exchange = config.get("exchange") or {}
    enabled_modes = config.get("enabled_modes") or []
    readiness = state.get("readiness") or {}
    readiness_names = {item.get("name") for item in readiness.get("items", [])}
    if "Binance live guard" not in readiness_names:
        return fail("readiness does not expose Binance live guard")

    live_mode_enabled = "live_guarded" in enabled_modes
    if live_mode_enabled:
        required = {
            "live_enabled": True,
            "live_key_ready": True,
            "live_places_real_orders": True,
            "live_confirmation_ready": True,
        }
        missing = [key for key, expected in required.items() if exchange.get(key) is not expected]
        if missing:
            return fail(f"live_guarded is enabled but exchange status is missing gates: {missing}")
    else:
        if exchange.get("live_places_real_orders"):
            return fail("live order placement flag is true but live_guarded mode is not enabled")

    print(
        json.dumps(
            {
                "ok": True,
                "live_guarded_enabled": live_mode_enabled,
                "live_enabled": exchange.get("live_enabled"),
                "live_key_ready": exchange.get("live_key_ready"),
                "live_places_real_orders": exchange.get("live_places_real_orders"),
                "live_confirmation_ready": exchange.get("live_confirmation_ready"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
