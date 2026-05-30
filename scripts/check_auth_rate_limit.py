from __future__ import annotations

import base64
import json
import sys
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from app import server  # noqa: E402


def fail(message: str, payload: Any | None = None) -> int:
    print(f"FAILED: {message}", file=sys.stderr)
    if payload is not None:
        print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
    return 1


def auth_header(username: str, password: str) -> str:
    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


def main() -> int:
    original = {
        "auth_enabled": server.AUTH_ENABLED,
        "user": server.APP_BASIC_AUTH_USER,
        "password": server.APP_BASIC_AUTH_PASSWORD,
        "limit": server.AUTH_FAILURE_LIMIT,
        "window": server.AUTH_FAILURE_WINDOW_SECONDS,
        "lockout": server.AUTH_LOCKOUT_SECONDS,
    }
    try:
        server.AUTH_ENABLED = True
        server.APP_BASIC_AUTH_USER = "admin"
        server.APP_BASIC_AUTH_PASSWORD = "correct-long-password"
        server.AUTH_FAILURE_LIMIT = 2
        server.AUTH_FAILURE_WINDOW_SECONDS = 300
        server.AUTH_LOCKOUT_SECONDS = 60
        server.AUTH_FAILURES.clear()

        bad = auth_header("admin", "wrong")
        bad_other_user = auth_header("other", "wrong")
        first = server.evaluate_basic_auth(bad, "100.64.0.10", now=1000.0)
        if first.get("ok") or first.get("locked") or first.get("failure_count") != 1:
            return fail("first failed auth attempt should be rejected but not locked", first)

        second = server.evaluate_basic_auth(bad_other_user, "100.64.0.10", now=1001.0)
        if second.get("ok") or not second.get("locked") or int(second.get("retry_after_seconds") or 0) <= 0:
            return fail("second failed auth attempt from the same client should trigger lockout", second)

        correct_while_locked = server.evaluate_basic_auth(
            auth_header("admin", "correct-long-password"),
            "100.64.0.10",
            now=1002.0,
        )
        if correct_while_locked.get("ok") or not correct_while_locked.get("locked"):
            return fail("correct credentials must remain blocked during active lockout", correct_while_locked)

        correct_after_lockout = server.evaluate_basic_auth(
            auth_header("admin", "correct-long-password"),
            "100.64.0.10",
            now=1062.0,
        )
        if not correct_after_lockout.get("ok") or correct_after_lockout.get("locked"):
            return fail("correct credentials should clear failures after lockout expires", correct_after_lockout)

        other_client = server.evaluate_basic_auth(
            auth_header("admin", "correct-long-password"),
            "100.64.0.11",
            now=1002.0,
        )
        if not other_client.get("ok"):
            return fail("lockout should be scoped to the failing client and username", other_client)
    finally:
        server.AUTH_ENABLED = original["auth_enabled"]
        server.APP_BASIC_AUTH_USER = original["user"]
        server.APP_BASIC_AUTH_PASSWORD = original["password"]
        server.AUTH_FAILURE_LIMIT = original["limit"]
        server.AUTH_FAILURE_WINDOW_SECONDS = original["window"]
        server.AUTH_LOCKOUT_SECONDS = original["lockout"]
        server.AUTH_FAILURES.clear()

    print(
        json.dumps(
            {
                "ok": True,
                "failure_limit": 2,
                "lockout_seconds": 60,
                "lockout_scoped_by_client": True,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
