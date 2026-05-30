from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path
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


def request_json(path: str) -> dict[str, object]:
    request = Request(f"{BASE_URL}{path}", headers=headers(), method="GET")
    with urlopen(request, timeout=45) as response:
        return json.loads(response.read().decode("utf-8"))


def fail(message: str, payload: object | None = None) -> int:
    print(f"FAILED: {message}", file=sys.stderr)
    if payload is not None:
        print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
    return 1


def main() -> int:
    payload = request_json("/api/live-launch-plan")
    plan = payload.get("live_launch_plan") if isinstance(payload, dict) else None
    if not isinstance(plan, dict):
        return fail("live-launch-plan endpoint did not return live_launch_plan", payload)
    for key in ("status", "current_summary", "blockers", "stages", "evidence_paths", "markdown", "safety_note"):
        if key not in plan:
            return fail(f"live launch plan missing {key}", plan)
    if len(plan.get("stages") or []) < 5:
        return fail("live launch plan endpoint returned too few stages", plan)
    markdown = str(plan.get("markdown") or "")
    for phrase in (
        "ARM_LIVE_TRADING",
        "live_guarded",
        "run_guarded_live_pilot_once.py",
        "LAUNCH_LIVE_PILOT",
        "guarded-live-pilot",
    ):
        if phrase not in markdown:
            return fail(f"live launch markdown is missing {phrase!r}", plan)
    serialized = json.dumps(plan, ensure_ascii=False)
    for forbidden in ("live-secret-value", "testnet-secret-value", "sk-proj-", "sk-test-"):
        if forbidden in serialized:
            return fail(f"live launch plan leaked forbidden token {forbidden}", plan)
    print(
        json.dumps(
            {
                "ok": True,
                "status": plan.get("status"),
                "stage_count": len(plan.get("stages") or []),
                "blocker_count": len(plan.get("blockers") or []),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
