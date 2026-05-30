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
REQUIRE_ARMED = os.getenv("TRADER_FINAL_LIVE_REQUIRE_ARMED", "true").lower() == "true"
REQUIRE_AI_OPERATOR = os.getenv("TRADER_FINAL_LIVE_REQUIRE_AI_OPERATOR", "true").lower() == "true"


def auth_headers() -> dict[str, str]:
    headers = {"Accept": "application/json"}
    if AUTH_USER and AUTH_PASSWORD:
        token = base64.b64encode(f"{AUTH_USER}:{AUTH_PASSWORD}".encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {token}"
    return headers


def request_json(path: str) -> Any:
    request = Request(f"{BASE_URL}{path}", headers=auth_headers(), method="GET")
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def fail(message: str, payload: dict[str, Any] | None = None) -> int:
    print(f"FAILED: {message}", file=sys.stderr)
    if payload:
        print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
    return 1


def collect_failures(report: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    verdict = report.get("verdict") or {}
    gate = report.get("go_live_gate") or {}
    attestation = report.get("live_attestation") or {}
    operator = report.get("ai_operator") or {}
    checklist = report.get("checklist") or []

    if report.get("app_env") != "server":
        failures.append("APP_ENV must be server.")
    if report.get("exchange_mode") != "live_guarded":
        failures.append("EXCHANGE_MODE must be live_guarded.")
    if not gate.get("live_mode_enabled"):
        failures.append("go-live gate does not show live_guarded as enabled.")
    if verdict.get("ready_to_enable_live") is not True:
        failures.append("go-live prerequisites are not complete enough to enable live mode.")
    if verdict.get("ready_to_arm_live") is not True:
        failures.append("go-live gate is not ready to arm live trading.")
    if REQUIRE_ARMED and verdict.get("ready_for_live_order") is not True:
        failures.append("final live readiness requires a currently armed live window.")
    if not REQUIRE_ARMED and gate.get("blocking_gates"):
        non_arming_blockers = [
            item.get("id") or item.get("label")
            for item in gate.get("blocking_gates", [])
            if item.get("id") != "live_arming"
        ]
        if non_arming_blockers:
            failures.append(f"non-arming blockers remain: {', '.join(non_arming_blockers)}.")
    if verdict.get("blocking_gate_ids") and REQUIRE_ARMED:
        failures.append(f"blocking gates remain: {', '.join(verdict.get('blocking_gate_ids') or [])}.")
    if attestation.get("status") != "pass":
        failures.append("live attestation is missing, incomplete, or expired.")

    failed_checklist = [
        item.get("id") or item.get("label")
        for item in checklist
        if item.get("status") != "pass"
        and (REQUIRE_ARMED or item.get("id") != "short_live_arming")
    ]
    if failed_checklist:
        failures.append(f"go-live checklist is not all pass: {', '.join(failed_checklist)}.")

    if REQUIRE_AI_OPERATOR:
        if not operator.get("enabled"):
            failures.append("AI/Codex operator console is not enabled.")
        if not operator.get("ready"):
            failures.append("AI/Codex operator is not ready; configure its provider and API key or use rules mode.")
        if not operator.get("allow_file_read"):
            failures.append("AI/Codex operator cannot read workspace files.")
        if not operator.get("allow_file_write"):
            failures.append("AI/Codex operator cannot write workspace files.")
        if not operator.get("allow_shell"):
            failures.append("AI/Codex operator cannot run shell commands.")
        if operator.get("allow_shell") and not operator.get("backup_before_shell"):
            failures.append("AI/Codex operator Shell backup is disabled; enable AI_OPERATOR_BACKUP_BEFORE_SHELL.")
        if not operator.get("apply_model_file_actions"):
            failures.append("AI/Codex operator is not set to auto-apply model file actions.")

    return failures


def main() -> int:
    try:
        payload = request_json("/api/go-live-report")
    except HTTPError as exc:
        return fail(f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}")
    except (URLError, TimeoutError, OSError) as exc:
        return fail(f"could not reach {BASE_URL}: {exc}")

    report = payload.get("go_live_report") or payload
    if not isinstance(report, dict):
        return fail("go-live report endpoint did not return an object")

    failures = collect_failures(report)
    verdict = report.get("verdict") or {}
    gate = report.get("go_live_gate") or {}
    summary = {
        "ok": not failures,
        "base_url": BASE_URL,
        "require_armed": REQUIRE_ARMED,
        "require_ai_operator": REQUIRE_AI_OPERATOR,
        "status": verdict.get("status"),
        "ready_to_enable_live": verdict.get("ready_to_enable_live"),
        "ready_to_arm_live": verdict.get("ready_to_arm_live"),
        "ready_for_live_order": verdict.get("ready_for_live_order"),
        "blocking_gates": verdict.get("blocking_gate_ids") or [],
        "live_arming": gate.get("live_arming") or {},
        "failures": failures,
    }
    if failures:
        return fail("final live readiness failed", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
