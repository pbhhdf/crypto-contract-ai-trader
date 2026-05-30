from __future__ import annotations

import base64
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT_DIR = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT_DIR / "reports"


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


def utc_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def auth_headers() -> dict[str, str]:
    headers = {"Accept": "application/json"}
    if AUTH_USER and AUTH_PASSWORD:
        token = base64.b64encode(f"{AUTH_USER}:{AUTH_PASSWORD}".encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {token}"
    return headers


def request_json(path: str) -> Any:
    request = Request(f"{BASE_URL}{path}", headers=auth_headers(), method="GET")
    with urlopen(request, timeout=45) as response:
        return json.loads(response.read().decode("utf-8"))


def fail(message: str) -> int:
    print(f"FAILED: {message}", file=sys.stderr)
    return 1


def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    try:
        payload = request_json("/api/live-launch-plan")
    except HTTPError as exc:
        return fail(f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}")
    except (URLError, TimeoutError, OSError) as exc:
        return fail(f"could not reach {BASE_URL}: {exc}")

    plan = payload.get("live_launch_plan") or payload
    if not isinstance(plan, dict):
        return fail("live-launch-plan endpoint did not return an object")
    slug = utc_slug()
    json_path = REPORT_DIR / f"live-launch-plan-{slug}.json"
    md_path = REPORT_DIR / f"live-launch-plan-{slug}.md"
    json_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(str(plan.get("markdown") or ""), encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": True,
                "json_path": str(json_path),
                "markdown_path": str(md_path),
                "status": plan.get("status"),
                "blocker_count": len(plan.get("blockers") or []),
                "ready_for_live_order": (plan.get("current_summary") or {}).get("ready_for_live_order"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
