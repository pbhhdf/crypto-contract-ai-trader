from __future__ import annotations

import json
import sys
import time
from typing import Any
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from app import server  # noqa: E402


def fail(message: str, payload: object | None = None) -> int:
    print(f"FAILED: {message}", file=sys.stderr)
    if payload is not None:
        print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
    return 1


def wait_until_done(timeout_seconds: float = 20.0) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    last: dict[str, Any] = {}
    while time.time() < deadline:
        last = server.server_live_readiness_status()
        if not last.get("running"):
            return last
        time.sleep(0.1)
    return last


def main() -> int:
    original_command = server.server_live_readiness_command
    try:
        server.server_live_readiness_command = lambda _options: [
            sys.executable,
            "-c",
            "import time; time.sleep(30)",
        ]
        started = server.start_server_live_readiness({"timeout_seconds": 120})
        if not started.get("running"):
            return fail("server live-readiness runner did not start", started)
        if not started.get("pid"):
            return fail("server live-readiness status did not expose child process pid", started)

        canceled = server.cancel_server_live_readiness("cancel_check")
        if not canceled.get("cancel_requested_now"):
            return fail("cancel did not mark a running readiness process", canceled)
        if not canceled.get("cancel_requested"):
            return fail("cancel status did not expose cancel_requested=true", canceled)

        final = wait_until_done()
        if final.get("running"):
            return fail("readiness process was still running after cancellation", final)
        if final.get("status") != "canceled":
            return fail("readiness process did not finish with canceled status", final)
        if "Canceled by operator request" not in str(final.get("last_error")):
            return fail("canceled readiness process did not keep cancel reason", final)
        if final.get("pid") is not None:
            return fail("canceled readiness process still exposed a live pid", final)

        idle_cancel = server.cancel_server_live_readiness("idle_cancel_check")
        if idle_cancel.get("cancel_requested_now"):
            return fail("idle cancel should not claim it canceled a running process", idle_cancel)

        print(
            json.dumps(
                {
                    "ok": True,
                    "started_pid": started.get("pid"),
                    "final_status": final.get("status"),
                    "idle_cancel_requested": idle_cancel.get("cancel_requested_now"),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    finally:
        server.server_live_readiness_command = original_command
        if server.server_live_readiness_status().get("running"):
            server.cancel_server_live_readiness("cancel_check_cleanup")
            wait_until_done()


if __name__ == "__main__":
    raise SystemExit(main())
