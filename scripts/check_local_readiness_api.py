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


def request_json(path: str, timeout: int = 30) -> dict[str, Any]:
    request = Request(f"{BASE_URL}{path}", headers=auth_headers(), method="GET")
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def fail(message: str, payload: object | None = None) -> int:
    print(f"FAILED: {message}", file=sys.stderr)
    if payload is not None:
        print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
    return 1


def validate_local_readiness(payload: dict[str, Any], *, max_last_steps: int) -> int:
    report = payload.get("local_readiness")
    if not isinstance(report, dict):
        return fail("endpoint did not return local_readiness object", payload)
    for key in (
        "exists",
        "status",
        "current_step",
        "completed_step_count",
        "failed_step_count",
        "failed_steps",
        "timed_out_steps",
        "last_steps",
        "report_path",
    ):
        if key not in report:
            return fail(f"local readiness payload missing {key}", report)
    last_steps = report.get("last_steps")
    if not isinstance(last_steps, list):
        return fail("last_steps is not a list", report)
    if len(last_steps) > max_last_steps:
        return fail("endpoint ignored local readiness limit", report)
    for step in last_steps:
        if not isinstance(step, dict):
            return fail("last_steps contains non-object step", report)
        for key in ("name", "ok", "returncode", "duration_seconds", "timed_out", "note"):
            if key not in step:
                return fail(f"local readiness step missing {key}", step)
        if step.get("ok") and len(str(step.get("note") or "")) > 0:
            return fail("successful local readiness steps should not stream noisy stdout into UI", step)
    return 0


def main() -> int:
    try:
        endpoint = request_json("/api/local-readiness?limit=3")
        status = validate_local_readiness(endpoint, max_last_steps=3)
        if status:
            return status
        state = request_json("/api/state")
    except HTTPError as exc:
        return fail(f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}")
    except (URLError, TimeoutError, OSError) as exc:
        return fail(f"could not verify local readiness API at {BASE_URL}: {exc}")

    if "local_readiness" not in state:
        return fail("state payload does not include local_readiness", list(state.keys()))
    status = validate_local_readiness({"local_readiness": state.get("local_readiness")}, max_last_steps=8)
    if status:
        return status

    report = endpoint["local_readiness"]
    print(
        json.dumps(
            {
                "ok": True,
                "status": report.get("status"),
                "exists": report.get("exists"),
                "completed_step_count": report.get("completed_step_count"),
                "failed_step_count": report.get("failed_step_count"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
