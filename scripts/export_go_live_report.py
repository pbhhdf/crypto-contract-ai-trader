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


def utc_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def request_json(path: str) -> Any:
    headers = {"Accept": "application/json"}
    if AUTH_USER and AUTH_PASSWORD:
        token = base64.b64encode(f"{AUTH_USER}:{AUTH_PASSWORD}".encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {token}"
    request = Request(f"{BASE_URL}{path}", headers=headers, method="GET")
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def write_markdown(report: dict[str, Any], path: Path) -> None:
    verdict = report.get("verdict") or {}
    blockers = verdict.get("blocking_gate_labels") or []
    checklist = report.get("checklist") or []
    gate = report.get("go_live_gate") or {}
    drill = report.get("testnet_drill") or {}
    audit = report.get("audit_chain") or {}
    lines = [
        "# Go-Live Evidence Report",
        "",
        f"- Generated: `{report.get('generated_at')}`",
        f"- App environment: `{report.get('app_env')}`",
        f"- Exchange mode: `{report.get('exchange_mode')}`",
        f"- Gate status: `{verdict.get('status')}`",
        f"- Ready for live order: `{verdict.get('ready_for_live_order')}`",
        f"- Blocking gates: `{', '.join(blockers) if blockers else 'none'}`",
        "",
        "## Checklist",
        "",
    ]
    for item in checklist:
        lines.append(f"- `{item.get('status')}` {item.get('label')} (`{item.get('id')}`)")
    lines.extend(
        [
            "",
            "## Evidence",
            "",
            f"- Testnet drill: real `{drill.get('real_completed_cycles')}/{gate.get('min_testnet_drill_cycles')}`, dry-run `{drill.get('dry_run_completed_cycles')}`, total `{drill.get('completed_cycles')}/{drill.get('target_cycles')}`",
            f"- Audit chain: `{audit.get('status')}`, records `{audit.get('total_records')}`, broken `{audit.get('broken_count')}`",
            f"- OMS: `{(report.get('oms') or {}).get('reconciled_orders')}/{(report.get('oms') or {}).get('total_orders')}` reconciled",
            f"- Alert active count: `{((report.get('alerts') or {}).get('summary') or {}).get('active')}`",
            "",
            "## Manual Evidence Still Required",
            "",
        ]
    )
    for item in report.get("required_manual_evidence") or []:
        lines.append(f"- {item}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def fail(message: str) -> int:
    print(f"FAILED: {message}", file=sys.stderr)
    return 1


def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    try:
        payload = request_json("/api/go-live-report")
    except HTTPError as exc:
        return fail(f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}")
    except (URLError, TimeoutError, OSError) as exc:
        return fail(f"could not reach {BASE_URL}: {exc}")

    report = payload.get("go_live_report") or payload
    if not isinstance(report, dict):
        return fail("go-live report endpoint did not return an object")
    slug = utc_slug()
    json_path = REPORT_DIR / f"go-live-report-{slug}.json"
    md_path = REPORT_DIR / f"go-live-report-{slug}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(report, md_path)
    print(
        json.dumps(
            {
                "ok": True,
                "json_path": str(json_path),
                "markdown_path": str(md_path),
                "status": (report.get("verdict") or {}).get("status"),
                "ready_for_live_order": (report.get("verdict") or {}).get("ready_for_live_order"),
                "blocking_gates": (report.get("verdict") or {}).get("blocking_gate_ids"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
