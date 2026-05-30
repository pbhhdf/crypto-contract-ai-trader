from __future__ import annotations

import base64
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT_DIR = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT_DIR / "reports"


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
STRICT = os.getenv("TRADER_SERVER_AUDIT_STRICT", "false").lower() == "true"


def utc_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


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


def status_badge(status: Any) -> str:
    return str(status if status is not None else "-")


def write_markdown(audit: dict[str, Any], path: Path) -> None:
    final_prearm = audit.get("final_live_ready_prearm") or {}
    final_armed = audit.get("final_live_ready_armed") or {}
    go_live_gate = audit.get("go_live_gate") or {}
    gate = go_live_gate.get("go_live_gate") or go_live_gate
    report = audit.get("go_live_report") or {}
    report_body = report.get("go_live_report") or report
    readiness = audit.get("readiness") or {}
    operator = (audit.get("ai_operator") or {}).get("status") or {}
    blockers = final_prearm.get("failures") or []
    armed_blockers = final_armed.get("failures") or []
    checklist = report_body.get("checklist") or []
    lines = [
        "# Server Go-Live Audit",
        "",
        f"- Generated: `{audit.get('generated_at')}`",
        f"- Base URL: `{audit.get('base_url')}`",
        f"- Health: `{status_badge((audit.get('health') or {}).get('ok'))}`",
        f"- Readiness: `{status_badge(readiness.get('overall'))}`",
        f"- Gate status: `{status_badge(gate.get('status'))}`",
        f"- Ready to enable live: `{status_badge(gate.get('ready_to_enable_live'))}`",
        f"- Ready to arm live: `{status_badge(gate.get('ready_to_arm_live'))}`",
        f"- Ready for live order: `{status_badge(gate.get('ready_for_live_order'))}`",
        f"- Final pre-arm check: `{status_badge(final_prearm.get('status'))}`",
        f"- Final armed check: `{status_badge(final_armed.get('status'))}`",
        "",
        "## AI/Codex Operator",
        "",
        f"- Enabled: `{status_badge(operator.get('enabled'))}`",
        f"- Ready: `{status_badge(operator.get('ready'))}`",
        f"- Provider: `{status_badge(operator.get('provider'))}`",
        f"- File write: `{status_badge(operator.get('allow_file_write'))}`",
        f"- Shell: `{status_badge(operator.get('allow_shell'))}`",
        f"- Auto-apply: `{status_badge(operator.get('apply_model_file_actions'))}`",
        f"- Snapshots: `{status_badge(operator.get('snapshot_writes'))}`",
        f"- Shell pre-backup: `{status_badge(operator.get('backup_before_shell'))}`",
        "",
        "## Pre-Arm Blockers",
        "",
    ]
    if blockers:
        lines.extend(f"- {item}" for item in blockers)
    else:
        lines.append("- none")
    lines.extend(["", "## Armed-Window Blockers", ""])
    if armed_blockers:
        lines.extend(f"- {item}" for item in armed_blockers)
    else:
        lines.append("- none")
    lines.extend(["", "## Checklist", ""])
    for item in checklist:
        lines.append(f"- `{item.get('status')}` {item.get('label')} (`{item.get('id')}`)")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def fail(message: str, payload: dict[str, Any] | None = None) -> int:
    print(f"FAILED: {message}", file=sys.stderr)
    if payload:
        print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
    return 1


def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    try:
        health = request_json("/api/health")
        readiness = request_json("/api/readiness")
        gate = request_json("/api/go-live-gate")
        final_prearm_payload = request_json("/api/final-live-ready?require_armed=false")
        final_armed_payload = request_json("/api/final-live-ready")
        ai_operator = request_json("/api/ai-operator")
        go_live_report = request_json("/api/go-live-report")
    except HTTPError as exc:
        return fail(f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}")
    except (URLError, TimeoutError, OSError) as exc:
        return fail(f"could not reach {BASE_URL}: {exc}")

    final_prearm = final_prearm_payload.get("final_live_ready") or final_prearm_payload
    final_armed = final_armed_payload.get("final_live_ready") or final_armed_payload
    audit = {
        "ok": True,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "base_url": BASE_URL,
        "strict": STRICT,
        "health": health,
        "readiness": readiness,
        "go_live_gate": gate,
        "final_live_ready_prearm": final_prearm,
        "final_live_ready_armed": final_armed,
        "ai_operator": ai_operator,
        "go_live_report": go_live_report,
    }
    slug = utc_slug()
    json_path = REPORT_DIR / f"server-go-live-audit-{slug}.json"
    md_path = REPORT_DIR / f"server-go-live-audit-{slug}.md"
    json_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(audit, md_path)
    summary = {
        "ok": True,
        "json_path": str(json_path),
        "markdown_path": str(md_path),
        "readiness": readiness.get("overall"),
        "prearm_ok": final_prearm.get("ok"),
        "armed_ok": final_armed.get("ok"),
        "prearm_failure_count": len(final_prearm.get("failures") or []),
        "armed_failure_count": len(final_armed.get("failures") or []),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if STRICT and not final_armed.get("ok"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
