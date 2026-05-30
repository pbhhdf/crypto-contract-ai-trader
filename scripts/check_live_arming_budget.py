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
    ]
    original = {key: server.get_setting(key, "") for key in keys}
    original_max_orders = server.LIVE_ARMING_MAX_ORDERS
    try:
        server.LIVE_ARMING_MAX_ORDERS = 1
        server.set_setting("live_armed_at", server.utc_now())
        server.set_setting("live_armed_until", server.seconds_from_now(300))
        server.set_setting("live_armed_by", "smoke")
        server.set_setting("live_armed_reason", "budget smoke")
        server.set_setting("live_armed_order_count", "0")
        server.set_setting("live_armed_order_ids", "[]")
        server.set_setting("live_disarmed_at", "")
        server.set_setting("live_disarm_reason", "")

        before = server.live_arming_status()
        if not before.get("armed") or before.get("remaining_orders") != 1:
            return fail(f"arming should start active with one remaining order: {before}")

        consumed = server.consume_live_arming_order("LIVE-BUDGET-SMOKE")
        if consumed.get("armed"):
            return fail(f"arming should be exhausted after one consumed order: {consumed}")
        if consumed.get("remaining_orders") != 0 or consumed.get("order_count") != 1:
            return fail(f"arming budget counters are wrong after consume: {consumed}")
        if "LIVE-BUDGET-SMOKE" not in (consumed.get("order_ids") or []):
            return fail("consumed order id was not recorded")

        try:
            server.consume_live_arming_order("LIVE-BUDGET-SMOKE-2")
            return fail("second live order budget consume was accepted")
        except ValueError:
            pass

        print(
            json.dumps(
                {
                    "ok": True,
                    "before": {
                        "armed": before.get("armed"),
                        "remaining_orders": before.get("remaining_orders"),
                        "max_orders": before.get("max_orders"),
                    },
                    "after": {
                        "armed": consumed.get("armed"),
                        "order_count": consumed.get("order_count"),
                        "remaining_orders": consumed.get("remaining_orders"),
                        "order_ids": consumed.get("order_ids"),
                    },
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    finally:
        server.LIVE_ARMING_MAX_ORDERS = original_max_orders
        for key, value in original.items():
            server.set_setting(key, value)


if __name__ == "__main__":
    raise SystemExit(main())
