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
        payload = request_json("GET", f"/api/live-pilot-postflight?{query}")
        postflight = payload.get("live_pilot_postflight") if isinstance(payload, dict) else None
        if not isinstance(postflight, dict):
            return fail("endpoint did not return live_pilot_postflight object", payload)
        required = {
            "status",
            "ok",
            "symbol",
            "run_id",
            "checks",
            "oms",
            "alerts",
            "audit_chain",
            "exchange_recovery",
            "final_live_ready_prearm",
            "next_actions",
        }
        missing = sorted(required - set(postflight))
        if missing:
            return fail("postflight response is missing required keys", {"missing": missing, "postflight": postflight})
        check_ids = {item.get("id") for item in postflight.get("checks") or []}
        expected_check_ids = {
            "selected_live_run",
            "run_terminal",
            "live_order_evidence",
            "oms_postflight_reconciled",
            "alerts_postflight",
            "audit_chain_postflight",
            "live_arming_disarmed",
            "exchange_snapshot_postflight",
            "final_prearm_after_pilot",
        }
        missing_checks = sorted(expected_check_ids - check_ids)
        if missing_checks:
            return fail("postflight response is missing required checks", {"missing_checks": missing_checks, "check_ids": sorted(check_ids)})
        if postflight.get("symbol") != symbol:
            return fail("postflight response did not preserve symbol", postflight)

        ai_result = request_json("POST", "/api/ai-operator/chat", {"message": f"/live-postflight {symbol}"})
        serialized = json.dumps(ai_result, ensure_ascii=False)
        if '"action": "live_pilot_postflight"' not in serialized:
            return fail("AI operator live-postflight command did not return live_pilot_postflight action", ai_result)
        if "sk-proj-" in serialized or "live-secret-value" in serialized or "testnet-secret-value" in serialized:
            return fail("AI operator live-postflight leaked a secret-looking marker")
    except HTTPError as exc:
        return fail(f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}")
    except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        return fail(f"could not validate live pilot postflight: {exc}")

    print(
        json.dumps(
            {
                "ok": True,
                "status": postflight.get("status"),
                "symbol": postflight.get("symbol"),
                "run_id": postflight.get("run_id"),
                "check_count": len(postflight.get("checks") or []),
                "warning_count": len(postflight.get("warnings") or []),
                "failure_count": len(postflight.get("failed_checks") or []),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
