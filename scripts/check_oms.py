from __future__ import annotations

import base64
import json
import os
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BASE_URL = os.getenv("TRADER_BASE_URL", "http://127.0.0.1:8787").rstrip("/")
HTTP_TIMEOUT_SECONDS = float(os.getenv("TRADER_HTTP_TIMEOUT_SECONDS", "45"))
AUTH_USER = os.getenv("TRADER_AUTH_USER", "")
AUTH_PASSWORD = os.getenv("TRADER_AUTH_PASSWORD", "")


def request_json(method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
    body = None
    headers = {"Accept": "application/json"}
    if AUTH_USER and AUTH_PASSWORD:
        token = base64.b64encode(f"{AUTH_USER}:{AUTH_PASSWORD}".encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {token}"
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(f"{BASE_URL}{path}", data=body, headers=headers, method=method)
    with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def fail(message: str) -> int:
    print(f"FAILED: {message}", file=sys.stderr)
    return 1


def main() -> int:
    try:
        reconciled = request_json("POST", "/api/oms/reconcile")
        summary = reconciled.get("summary") or {}
        orders = reconciled.get("orders") or []
        required_summary_keys = {
            "total_orders",
            "reconciled_orders",
            "needs_reconcile",
            "unknown_venue_status",
            "updated_at",
        }
        missing_keys = sorted(required_summary_keys - set(summary))
        if missing_keys:
            return fail(f"OMS summary missing keys: {missing_keys}")
        if summary.get("unknown_venue_status") != 0:
            return fail(f"OMS still has unknown venue statuses: {summary}")
        if summary.get("needs_reconcile") != 0:
            return fail(f"OMS still has orders needing reconcile: {summary}")

        for order in orders:
            if not order.get("client_order_id"):
                return fail(f"order {order.get('id')} is missing client_order_id")
            if not order.get("venue_status"):
                return fail(f"order {order.get('id')} is missing venue_status")
            if order.get("reconcile_status") not in {
                "reconciled",
                "validated_no_live_order",
                "reviewed",
            }:
                return fail(
                    f"order {order.get('id')} has unexpected reconcile_status "
                    f"{order.get('reconcile_status')!r}"
                )

        state = request_json("GET", "/api/state")
        state_oms = state.get("oms") or {}
        if state_oms.get("needs_reconcile") != 0:
            return fail(f"state endpoint OMS summary is stale: {state_oms}")

        output = {
            "total_orders": summary.get("total_orders"),
            "reconciled_orders": summary.get("reconciled_orders"),
            "needs_reconcile": summary.get("needs_reconcile"),
            "unknown_venue_status": summary.get("unknown_venue_status"),
            "latest_order_id": summary.get("latest_order_id"),
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0
    except HTTPError as exc:
        return fail(f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}")
    except (URLError, TimeoutError, OSError) as exc:
        return fail(f"could not reach {BASE_URL}: {exc}")


if __name__ == "__main__":
    raise SystemExit(main())
