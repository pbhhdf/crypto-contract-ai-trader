from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from app import server  # noqa: E402


STREAM_KEYS = [
    "binance_user_stream_mode",
    "binance_user_stream_listen_key",
    "binance_user_stream_status",
    "binance_user_stream_started_at",
    "binance_user_stream_keepalive_at",
    "binance_user_stream_expires_at",
    "binance_user_stream_last_error",
    "binance_user_stream_connected",
    "binance_user_stream_consumer_started_at",
    "binance_user_stream_last_event_at",
    "binance_user_stream_last_event_type",
    "binance_user_stream_event_count",
]


def fail(message: str, payload: Any | None = None) -> int:
    print(f"FAILED: {message}", file=sys.stderr)
    if payload is not None:
        print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
    return 1


def set_stream(**values: str) -> None:
    defaults = {
        "binance_user_stream_mode": "",
        "binance_user_stream_listen_key": "",
        "binance_user_stream_status": "stopped",
        "binance_user_stream_started_at": "",
        "binance_user_stream_keepalive_at": "",
        "binance_user_stream_expires_at": "",
        "binance_user_stream_last_error": "",
        "binance_user_stream_connected": "false",
        "binance_user_stream_consumer_started_at": "",
        "binance_user_stream_last_event_at": "",
        "binance_user_stream_last_event_type": "",
        "binance_user_stream_event_count": "0",
    }
    defaults.update(values)
    for key, value in defaults.items():
        server.set_setting(key, value)


def main() -> int:
    server.init_db()
    original_values = {key: server.get_setting(key, "") for key in STREAM_KEYS}
    original_alive = server.current_user_stream_thread_alive
    original_dependency = server.user_stream_dependency_ready
    try:
        server.current_user_stream_thread_alive = lambda: False
        server.user_stream_dependency_ready = lambda: True
        set_stream()
        empty_status = server.binance_user_stream_status()
        if empty_status.get("health", {}).get("status") != "warn":
            return fail("missing listenKey should be a warning outside required live mode", empty_status)
        required_empty = server.evaluate_binance_user_stream_health(empty_status, require_live=True)
        if required_empty.get("status") != "fail":
            return fail("missing listenKey should fail required live stream health", required_empty)

        server.current_user_stream_thread_alive = lambda: True
        set_stream(
            binance_user_stream_mode="live_guarded",
            binance_user_stream_listen_key="listen-key-live-12345",
            binance_user_stream_status="active",
            binance_user_stream_started_at=server.utc_now(),
            binance_user_stream_keepalive_at=server.utc_now(),
            binance_user_stream_expires_at=server.seconds_from_now(55 * 60),
            binance_user_stream_connected="true",
            binance_user_stream_consumer_started_at=server.utc_now(),
        )
        healthy = server.binance_user_stream_status()
        required_healthy = server.evaluate_binance_user_stream_health(healthy, require_live=True)
        if healthy.get("health", {}).get("status") != "pass" or required_healthy.get("status") != "pass":
            return fail("healthy live user stream did not pass", {"status": healthy, "required": required_healthy})

        set_stream(
            binance_user_stream_mode="live_guarded",
            binance_user_stream_listen_key="listen-key-live-12345",
            binance_user_stream_status="active",
            binance_user_stream_expires_at=server.seconds_from_now(55 * 60),
            binance_user_stream_connected="false",
            binance_user_stream_consumer_started_at=server.utc_now(),
        )
        disconnected = server.evaluate_binance_user_stream_health(server.binance_user_stream_status(), require_live=True)
        if disconnected.get("status") != "fail":
            return fail("active stream without WebSocket connection should fail", disconnected)

        set_stream(
            binance_user_stream_mode="binance_testnet_place_order",
            binance_user_stream_listen_key="listen-key-testnet-12345",
            binance_user_stream_status="active",
            binance_user_stream_expires_at=server.seconds_from_now(55 * 60),
            binance_user_stream_connected="true",
            binance_user_stream_consumer_started_at=server.utc_now(),
        )
        wrong_mode = server.evaluate_binance_user_stream_health(server.binance_user_stream_status(), require_live=True)
        if wrong_mode.get("status") != "fail":
            return fail("required live stream should reject testnet listenKey mode", wrong_mode)

        set_stream(
            binance_user_stream_mode="live_guarded",
            binance_user_stream_listen_key="listen-key-live-12345",
            binance_user_stream_status="active",
            binance_user_stream_expires_at=server.seconds_from_now(-1),
            binance_user_stream_connected="true",
            binance_user_stream_consumer_started_at=server.utc_now(),
        )
        expired = server.evaluate_binance_user_stream_health(server.binance_user_stream_status(), require_live=True)
        if expired.get("status") != "fail":
            return fail("expired listenKey should fail", expired)

        set_stream(
            binance_user_stream_mode="live_guarded",
            binance_user_stream_listen_key="listen-key-live-12345",
            binance_user_stream_status="active",
            binance_user_stream_expires_at=server.seconds_from_now(55 * 60),
            binance_user_stream_connected="true",
            binance_user_stream_consumer_started_at=server.utc_now(),
            binance_user_stream_last_event_at=server.seconds_from_now(-(server.PRIVATE_STREAM_STALE_SECONDS + 5)),
            binance_user_stream_last_event_type="ORDER_TRADE_UPDATE",
            binance_user_stream_event_count="1",
        )
        stale = server.evaluate_binance_user_stream_health(server.binance_user_stream_status(), require_live=True)
        if stale.get("status") != "fail" or "stale" not in stale.get("detail", ""):
            return fail("stale private stream events should fail required live health", stale)

        print(
            json.dumps(
                {
                    "ok": True,
                    "empty": empty_status.get("health"),
                    "healthy": required_healthy,
                    "disconnected": disconnected,
                    "wrong_mode": wrong_mode,
                    "expired": expired,
                    "stale": stale,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    finally:
        server.current_user_stream_thread_alive = original_alive
        server.user_stream_dependency_ready = original_dependency
        for key, value in original_values.items():
            server.set_setting(key, value)


if __name__ == "__main__":
    raise SystemExit(main())
