from __future__ import annotations

import base64
import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


BASE_URL = os.getenv("TRADER_BASE_URL", "http://127.0.0.1:8787").rstrip("/")
HTTP_TIMEOUT_SECONDS = float(os.getenv("TRADER_HTTP_TIMEOUT_SECONDS", "120"))
AUTH_USER = os.getenv("TRADER_AUTH_USER", os.getenv("APP_BASIC_AUTH_USER", ""))
AUTH_PASSWORD = os.getenv("TRADER_AUTH_PASSWORD", os.getenv("APP_BASIC_AUTH_PASSWORD", ""))


def headers() -> dict[str, str]:
    result = {"Accept": "application/json", "Content-Type": "application/json"}
    if AUTH_USER and AUTH_PASSWORD:
        token = base64.b64encode(f"{AUTH_USER}:{AUTH_PASSWORD}".encode("utf-8")).decode("ascii")
        result["Authorization"] = f"Basic {token}"
    return result


def request_json(method: str, path: str, payload: dict[str, object] | None = None) -> dict[str, object]:
    body = json.dumps(payload or {}, ensure_ascii=False).encode("utf-8") if method == "POST" else None
    request = Request(f"{BASE_URL}{path}", data=body, headers=headers(), method=method)
    with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def fail(message: str, payload: object | None = None) -> int:
    print(f"FAILED: {message}", file=sys.stderr)
    if payload is not None:
        print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
    return 1


def main() -> int:
    symbol = os.getenv("TRADER_TEST_SYMBOL", "BTCUSDT")
    try:
        query = urlencode({"symbol": symbol})
        payload = request_json("GET", f"/api/live-blocker-resolution?{query}")
        resolution = payload.get("live_blocker_resolution") if isinstance(payload, dict) else None
        if not isinstance(resolution, dict):
            return fail("endpoint did not return live_blocker_resolution object", payload)
        required = {
            "ok",
            "status",
            "symbol",
            "blocking_gates",
            "next_action",
            "steps",
            "readiness",
            "testnet_drill",
            "final_live_ready_prearm",
            "final_live_ready_armed",
            "live_env_profile",
            "server_live_readiness",
            "ai_commands",
            "safety_note",
        }
        missing = sorted(required - set(resolution))
        if missing:
            return fail("resolution response is missing required keys", {"missing": missing, "resolution": resolution})
        if resolution.get("symbol") != symbol:
            return fail("resolution response did not preserve symbol", resolution)
        steps = resolution.get("steps") or []
        if not isinstance(steps, list):
            return fail("resolution steps is not a list", resolution)
        for step in steps:
            if not isinstance(step, dict):
                return fail("resolution step is not an object", step)
            missing_step = sorted({"id", "label", "status", "detail", "commands", "proof", "safety"} - set(step))
            if missing_step:
                return fail("resolution step missing required keys", {"missing": missing_step, "step": step})
        serialized = json.dumps(resolution, ensure_ascii=False)
        if "live_flags" in serialized and "LIVE_TRADING_CONFIRMATION=I_UNDERSTAND_LIVE_RISK" not in serialized:
            return fail("live_flags blocker did not include live confirmation guidance", resolution)
        if "testnet_drill_cycles" in serialized and "run_testnet_drill_until_ready.py" not in serialized:
            return fail("testnet drill blocker did not include runner guidance", resolution)
        if "sk-proj-" in serialized or "live-secret-value" in serialized or "testnet-secret-value" in serialized:
            return fail("resolution leaked a secret-looking marker")

        ai_result = request_json("POST", "/api/ai-operator/chat", {"message": f"/resolve-live-blockers {symbol}"})
        ai_serialized = json.dumps(ai_result, ensure_ascii=False)
        if '"action": "live_blocker_resolution"' not in ai_serialized:
            return fail("AI operator resolve-live-blockers command did not return live_blocker_resolution action", ai_result)
        if "sk-proj-" in ai_serialized or "live-secret-value" in ai_serialized or "testnet-secret-value" in ai_serialized:
            return fail("AI operator resolve-live-blockers leaked a secret-looking marker")
    except HTTPError as exc:
        return fail(f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}")
    except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        return fail(f"could not validate live blocker resolution: {exc}")

    print(
        json.dumps(
            {
                "ok": True,
                "status": resolution.get("status"),
                "symbol": resolution.get("symbol"),
                "blocking_gates": resolution.get("blocking_gates"),
                "step_count": len(steps),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
