from __future__ import annotations

import base64
import json
import os
import sys
import time
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


def request_json(path: str, method: str = "GET", body: dict[str, Any] | None = None, timeout: int = 30) -> dict[str, Any]:
    payload = None
    headers = auth_headers()
    if body is not None:
        payload = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(f"{BASE_URL}{path}", data=payload, headers=headers, method=method)
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def fail(message: str, payload: object | None = None) -> int:
    print(f"FAILED: {message}", file=sys.stderr)
    if payload is not None:
        print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
    return 1


def poll_status(max_seconds: int = 45) -> dict[str, Any]:
    deadline = time.time() + max_seconds
    last: dict[str, Any] = {}
    while time.time() < deadline:
        payload = request_json("/api/server-live-readiness")
        status = payload.get("server_live_readiness")
        if not isinstance(status, dict):
            raise RuntimeError("endpoint did not return server_live_readiness object")
        last = status
        if not status.get("running") and status.get("status") in {"completed", "failed"}:
            return status
        time.sleep(0.75)
    return last


def main() -> int:
    try:
        initial = request_json("/api/server-live-readiness")
        if not isinstance(initial.get("server_live_readiness"), dict):
            return fail("status endpoint did not return server_live_readiness object", initial)
        started = request_json(
            "/api/server-live-readiness/run",
            method="POST",
            body={
                "dry_run": True,
                "run_testnet_drill": True,
                "target_cycles": 2,
                "interval_seconds": 1,
                "timeout_seconds": 120,
            },
            timeout=30,
        )
        if not isinstance(started.get("server_live_readiness"), dict):
            return fail("run endpoint did not return server_live_readiness object", started)
        status = poll_status()
    except HTTPError as exc:
        return fail(f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}")
    except (URLError, TimeoutError, OSError, RuntimeError) as exc:
        return fail(f"could not verify server live readiness API at {BASE_URL}: {exc}")

    if status.get("status") != "completed":
        return fail("dry-run server live readiness did not complete", status)
    summary = status.get("last_summary")
    if not isinstance(summary, dict):
        return fail("completed run did not keep a summary", status)
    report_path = Path(str(status.get("last_report_path") or summary.get("report_path") or ""))
    if not report_path.exists():
        return fail("completed run did not write a report", status)
    if not summary.get("ok"):
        return fail("dry-run runner reported failure", summary)
    if not isinstance(summary.get("evidence_paths"), dict):
        return fail("dry-run runner summary did not include evidence_paths", summary)

    print(
        json.dumps(
            {
                "ok": True,
                "status": status.get("status"),
                "run_id": status.get("run_id"),
                "report_path": str(report_path),
                "final_live_ready": summary.get("final_live_ready"),
                "blocking_gates": summary.get("blocking_gates"),
                "evidence_path_keys": sorted(summary.get("evidence_paths") or {}),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
