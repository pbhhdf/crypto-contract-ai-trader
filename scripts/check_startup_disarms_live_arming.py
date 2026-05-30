from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from app import server  # noqa: E402


def fail(message: str) -> int:
    print(f"FAILED: {message}", file=sys.stderr)
    return 1


def main() -> int:
    server.init_db()
    keys = [
        "live_armed_at",
        "live_armed_until",
        "live_armed_by",
        "live_armed_reason",
        "live_armed_order_count",
        "live_armed_order_ids",
        "live_disarmed_at",
        "live_disarm_reason",
        "live_startup_disarm_last_at",
        "live_startup_disarm_last_report",
    ]
    original = {key: server.get_setting(key, "") for key in keys}
    try:
        server.set_setting("live_armed_at", server.utc_now())
        server.set_setting("live_armed_until", server.seconds_from_now(600))
        server.set_setting("live_armed_by", "startup-smoke")
        server.set_setting("live_armed_reason", "should not survive restart")
        server.set_setting("live_armed_order_count", "0")
        server.set_setting("live_armed_order_ids", "[]")
        server.set_setting("live_disarmed_at", "")
        server.set_setting("live_disarm_reason", "")

        before = server.live_arming_status()
        if not before.get("time_active") or not before.get("armed"):
            return fail(f"test setup did not create an active live arming window: {before}")

        report = server.disarm_live_arming_on_startup()
        after = server.live_arming_status()
        if report.get("action") != "disarmed":
            return fail(f"startup disarm should report action=disarmed: {report}")
        if after.get("armed") or after.get("time_active"):
            return fail(f"live arming remained active after startup disarm: {after}")
        if after.get("disarm_reason") != "startup_disarm":
            return fail(f"unexpected disarm reason after startup disarm: {after}")
        saved_report = server.get_setting("live_startup_disarm_last_report", "{}")
        if "startup_disarm" not in saved_report:
            return fail("startup disarm did not persist evidence report")

        second = server.disarm_live_arming_on_startup()
        if second.get("action") != "noop":
            return fail(f"second startup disarm should be a noop: {second}")

        print(
            json.dumps(
                {
                    "ok": True,
                    "before": {
                        "armed": before.get("armed"),
                        "time_active": before.get("time_active"),
                        "remaining_orders": before.get("remaining_orders"),
                    },
                    "after": {
                        "armed": after.get("armed"),
                        "time_active": after.get("time_active"),
                        "disarm_reason": after.get("disarm_reason"),
                    },
                    "first_action": report.get("action"),
                    "second_action": second.get("action"),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    finally:
        for key, value in original.items():
            server.set_setting(key, value)


if __name__ == "__main__":
    raise SystemExit(main())
