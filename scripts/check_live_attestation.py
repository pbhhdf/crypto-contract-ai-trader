from __future__ import annotations

import base64
import json
import os
import sys
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


def request_json(method: str, path: str, body: dict[str, Any] | None = None) -> Any:
    headers = auth_headers()
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
    with urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def fail(message: str) -> int:
    print(f"FAILED: {message}", file=sys.stderr)
    return 1


def main() -> int:
    try:
        initial = request_json("GET", "/api/live-attestation")
        try:
            request_json("POST", "/api/live-attestation", {"confirmation": "WRONG", "accepted": {}})
            return fail("live attestation accepted an invalid confirmation phrase")
        except HTTPError as exc:
            if exc.code != 400:
                return fail(f"invalid attestation returned HTTP {exc.code}")
            error_payload = json.loads(exc.read().decode("utf-8"))
            if not error_payload.get("error"):
                return fail("invalid attestation did not include an error")

        attestation = initial.get("live_attestation") or {}
        mutated = False
        if attestation.get("status") != "pass":
            accepted = {
                item["id"]: True
                for item in attestation.get("requirements", [])
                if item.get("id")
            }
            if not accepted:
                return fail("live attestation endpoint did not expose requirements")
            saved = request_json(
                "POST",
                "/api/live-attestation",
                {
                    "confirmation": "LIVE_ATTESTATION_CONFIRMED",
                    "actor": "check_live_attestation",
                    "note": "temporary smoke-test evidence; cleared after validation",
                    "accepted": accepted,
                },
            )
            attestation = saved.get("live_attestation") or {}
            if attestation.get("status") != "pass":
                return fail("live attestation did not pass after all evidence was accepted")
            mutated = True

        gate_response = request_json("GET", "/api/go-live-gate")
        gate = gate_response.get("go_live_gate") or {}
        attestation_gate = next(
            (item for item in gate.get("gates", []) if item.get("id") == "live_attestation"),
            None,
        )
        if not attestation_gate:
            return fail("go-live gate does not include live_attestation")
        if attestation.get("status") == "pass" and attestation_gate.get("status") != "pass":
            return fail("go-live gate did not reflect passing live attestation")

        cleanup_status = "skipped"
        if mutated:
            cleared = request_json(
                "POST",
                "/api/live-attestation/clear",
                {"reason": "check_live_attestation cleanup"},
            )
            cleared_attestation = cleared.get("live_attestation") or {}
            if cleared_attestation.get("status") == "pass":
                return fail("live attestation cleanup did not clear the evidence")
            cleanup_status = cleared_attestation.get("status") or "cleared"

    except HTTPError as exc:
        return fail(f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}")
    except (URLError, TimeoutError, OSError) as exc:
        return fail(f"could not reach {BASE_URL}: {exc}")

    print(
        json.dumps(
            {
                "ok": True,
                "status": attestation.get("status"),
                "mutated": mutated,
                "cleanup_status": cleanup_status,
                "gate_status": attestation_gate.get("status"),
                "missing_ids": attestation.get("missing_ids"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
