from __future__ import annotations

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


def main() -> int:
    server.init_db()
    schema = server.ai_operator_response_schema()
    action_schema = schema["properties"]["actions"]["items"]
    properties = action_schema.get("properties") or {}
    required = set(action_schema.get("required") or [])
    property_names = set(properties)
    if required != property_names:
        return fail("AI operator action schema required keys must match properties for strict mode", {
            "missing_required": sorted(property_names - required),
            "unknown_required": sorted(required - property_names),
        })
    enum_values = set((properties.get("type") or {}).get("enum") or [])
    expected_actions = set(server.AI_OPERATOR_ACTION_TYPES)
    if enum_values != expected_actions:
        return fail("AI operator action enum does not match runtime action types", {
            "missing_enum": sorted(expected_actions - enum_values),
            "extra_enum": sorted(enum_values - expected_actions),
        })
    panic_fields = {
        "panic_stop",
        "confirmation",
        "reason",
        "cancel_orders",
        "cancel_exchange_open_orders",
        "flatten_positions",
        "flatten_confirmation",
        "reconcile",
    }
    missing_panic_fields = sorted(field for field in panic_fields if field != "panic_stop" and field not in property_names)
    if "panic_stop" not in enum_values or missing_panic_fields:
        return fail("AI operator schema does not fully cover panic-stop actions", {
            "panic_in_enum": "panic_stop" in enum_values,
            "missing_fields": missing_panic_fields,
        })
    live_control_actions = {
        "live_arm",
        "live_disarm",
        "live_attestation_save",
        "live_attestation_clear",
    }
    live_control_fields = {
        "confirmation",
        "actor",
        "reason",
        "note",
        "ttl_seconds",
        "ttl_minutes",
        "accepted_all",
    }
    missing_live_actions = sorted(live_control_actions - enum_values)
    missing_live_fields = sorted(live_control_fields - property_names)
    if missing_live_actions or missing_live_fields:
        return fail("AI operator schema does not fully cover live control actions", {
            "missing_actions": missing_live_actions,
            "missing_fields": missing_live_fields,
        })
    server_runner_fields = {
        "server_live_readiness_run",
        "target",
        "testnet_mode",
        "dry_run",
        "run_testnet_drill",
        "allow_testnet_placement",
        "skip_full_checks",
        "skip_strategy_sweep",
        "strict",
        "target_cycles",
        "interval_seconds",
        "timeout_seconds",
    }
    missing_runner_fields = sorted(
        field for field in server_runner_fields
        if field != "server_live_readiness_run" and field not in property_names
    )
    if "server_live_readiness_run" not in enum_values or missing_runner_fields:
        return fail("AI operator schema does not fully cover server live-readiness runner actions", {
            "runner_in_enum": "server_live_readiness_run" in enum_values,
            "missing_fields": missing_runner_fields,
        })

    original_key = server.OPENAI_API_KEY
    original_post = server.http_post_json
    captured: dict[str, Any] = {}

    def fake_post(url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        captured["url"] = url
        captured["payload"] = payload
        captured["headers"] = headers
        return {"output_text": json.dumps({"reply": "ok", "actions": []})}

    try:
        server.OPENAI_API_KEY = "sk-test-ai-operator-schema"
        server.http_post_json = fake_post
        result = server.call_openai_operator("检查是否可以 panic stop", [])
        if result.get("reply") != "ok":
            return fail("fake OpenAI operator call did not return expected parsed result", result)
    finally:
        server.OPENAI_API_KEY = original_key
        server.http_post_json = original_post

    payload = captured.get("payload") or {}
    response_format = ((payload.get("text") or {}).get("format") or {})
    if response_format.get("strict") is not True:
        return fail("OpenAI operator payload did not request strict structured output", response_format)
    if response_format.get("schema") != schema:
        return fail("OpenAI operator payload schema differs from ai_operator_response_schema()", response_format.get("schema"))
    user_context = json.loads(payload["input"][1]["content"])
    if "panic_stop" not in (user_context.get("available_actions") or []):
        return fail("OpenAI operator prompt did not advertise panic_stop action", user_context)
    defaults = user_context.get("action_defaults") or {}
    if defaults.get("panic_stop_requires_confirmation") != "PANIC_STOP":
        return fail("OpenAI operator prompt did not advertise panic-stop confirmation phrase", defaults)
    if "live_guarded" not in (defaults.get("live_env_profile_targets") or []):
        return fail("OpenAI operator prompt did not advertise live-env profile targets", defaults)
    if "binance_testnet_place_order" not in (defaults.get("testnet_modes") or []):
        return fail("OpenAI operator prompt did not advertise testnet runner modes", defaults)
    if defaults.get("live_arm_requires_confirmation") != "ARM_LIVE_TRADING":
        return fail("OpenAI operator prompt did not advertise live arming confirmation phrase", defaults)
    if defaults.get("live_attestation_requires_confirmation") != "LIVE_ATTESTATION_CONFIRMED":
        return fail("OpenAI operator prompt did not advertise live attestation confirmation phrase", defaults)

    print(
        json.dumps(
            {
                "ok": True,
                "action_count": len(enum_values),
                "property_count": len(property_names),
                "panic_stop_schema_ready": True,
                "live_control_schema_ready": True,
                "server_runner_schema_ready": True,
                "strict": response_format.get("strict"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
