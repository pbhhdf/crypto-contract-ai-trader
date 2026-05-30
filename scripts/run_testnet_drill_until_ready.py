from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
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
HTTP_TIMEOUT_SECONDS = float(os.getenv("TRADER_HTTP_TIMEOUT_SECONDS", "90"))


def utc_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def auth_headers() -> dict[str, str]:
    headers = {"Accept": "application/json"}
    if AUTH_USER and AUTH_PASSWORD:
        token = base64.b64encode(f"{AUTH_USER}:{AUTH_PASSWORD}".encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {token}"
    return headers


def request_json(method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
    body = None
    headers = auth_headers()
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(f"{BASE_URL}{path}", data=body, headers=headers, method=method)
    with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def find_testnet_gate(gate: dict[str, Any]) -> dict[str, Any]:
    return next(
        (item for item in gate.get("gates", []) if item.get("id") == "testnet_drill_cycles"),
        {},
    )


def counter_value(status: dict[str, Any], target_kind: str) -> int:
    if target_kind == "real":
        return int(status.get("real_completed_cycles") or 0)
    if target_kind == "dry_run":
        return int(status.get("dry_run_completed_cycles") or 0)
    return int(status.get("completed_cycles") or 0)


def fail(message: str, report: dict[str, Any] | None = None) -> int:
    print(f"FAILED: {message}", file=sys.stderr)
    if report is not None:
        print(json.dumps(report, ensure_ascii=False, indent=2), file=sys.stderr)
    return 1


def write_report(report: dict[str, Any]) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"testnet-drill-runner-{utc_slug()}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run Binance Testnet drill cycles until the configured go-live counter is ready. "
            "Dry-run mode exercises the control chain without sending Binance requests."
        )
    )
    parser.add_argument("--symbol", default=os.getenv("TRADER_SYMBOL", "BTCUSDT"), help="Symbol to configure for drills.")
    parser.add_argument(
        "--mode",
        default=os.getenv("TRADER_TESTNET_DRILL_MODE", "binance_testnet_validate"),
        choices=["binance_testnet_validate", "binance_testnet_place_order"],
        help="Drill mode to configure before running cycles.",
    )
    parser.add_argument(
        "--target-cycles",
        type=int,
        default=None,
        help="Target counter value. Defaults to go-live required cycles for real runs, or one extra dry-run cycle.",
    )
    parser.add_argument(
        "--target-kind",
        choices=["real", "dry_run", "total"],
        default=None,
        help="Which cycle counter must reach the target. Defaults to real unless --dry-run is set.",
    )
    parser.add_argument("--interval-seconds", type=float, default=60.0, help="Delay between successful cycles.")
    parser.add_argument("--max-cycles", type=int, default=None, help="Maximum cycles to attempt in this invocation.")
    parser.add_argument("--dry-run", action="store_true", help="Do not send Binance requests; run local drill checks only.")
    parser.add_argument(
        "--allow-testnet-placement",
        action="store_true",
        help="Allow non-dry-run binance_testnet_place_order cycles. Validation mode does not need this.",
    )
    parser.add_argument(
        "--continue-on-failed-cycle",
        action="store_true",
        help="Keep running after a failed cycle. Default stops immediately.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.mode == "binance_testnet_place_order" and not args.dry_run and not args.allow_testnet_placement:
        return fail("binance_testnet_place_order requires --allow-testnet-placement for non-dry-run cycles.")

    target_kind = args.target_kind or ("dry_run" if args.dry_run else "real")
    report: dict[str, Any] = {
        "ok": False,
        "base_url": BASE_URL,
        "symbol": args.symbol.upper(),
        "mode": args.mode,
        "dry_run": args.dry_run,
        "target_kind": target_kind,
        "cycles": [],
        "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    try:
        gate_payload = request_json("GET", "/api/go-live-gate").get("go_live_gate") or {}
        gate = find_testnet_gate(gate_payload)
        gate_evidence = gate.get("evidence") or {}
        required_cycles = int(gate_evidence.get("required_cycles") or 24)

        configured = request_json(
            "POST",
            "/api/testnet-drill",
            {
                "enabled": False,
                "symbol": args.symbol.upper(),
                "mode": args.mode,
                "interval_minutes": max(1, int(args.interval_seconds // 60) or 1),
                "target_cycles": max(1, args.target_cycles or required_cycles),
            },
        ).get("testnet_drill") or {}

        if args.target_cycles is None:
            target_cycles = (
                counter_value(configured, target_kind) + 1
                if args.dry_run
                else required_cycles
            )
        else:
            target_cycles = max(1, args.target_cycles)
        max_cycles = args.max_cycles
        if max_cycles is None:
            max_cycles = max(1, target_cycles - counter_value(configured, target_kind))

        report.update(
            {
                "required_cycles": required_cycles,
                "target_cycles": target_cycles,
                "max_cycles": max_cycles,
                "initial_status": configured,
            }
        )

        attempts = 0
        status = configured
        while counter_value(status, target_kind) < target_cycles and attempts < max_cycles:
            attempts += 1
            try:
                payload = request_json("POST", "/api/testnet-drill/run-now", {"dry_run": args.dry_run})
                cycle = payload.get("cycle") or {}
                status = payload.get("testnet_drill") or request_json("GET", "/api/testnet-drill").get("testnet_drill") or {}
                item = {
                    "attempt": attempts,
                    "cycle_id": cycle.get("id"),
                    "status": cycle.get("status"),
                    "note": cycle.get("note"),
                    "real_completed_cycles": status.get("real_completed_cycles"),
                    "dry_run_completed_cycles": status.get("dry_run_completed_cycles"),
                    "completed_cycles": status.get("completed_cycles"),
                    "last_error": status.get("last_error"),
                }
                report["cycles"].append(item)
                print(json.dumps(item, ensure_ascii=False))
                if cycle.get("status") != "completed" and not args.continue_on_failed_cycle:
                    report["final_status"] = status
                    report["completed_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
                    report["report_path"] = str(write_report(report))
                    return fail("Testnet drill cycle failed; stopping.", report)
                if counter_value(status, target_kind) >= target_cycles:
                    break
                time.sleep(max(0.0, args.interval_seconds))
            except HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                if exc.code == 409:
                    print(json.dumps({"attempt": attempts, "status": "waiting_for_active_run", "error": body}, ensure_ascii=False))
                    time.sleep(max(1.0, min(args.interval_seconds, 30.0)))
                    attempts -= 1
                    continue
                raise RuntimeError(f"HTTP {exc.code}: {body}") from exc

        status = request_json("GET", "/api/testnet-drill").get("testnet_drill") or {}
        gate_payload = request_json("GET", "/api/go-live-gate").get("go_live_gate") or {}
        reached = counter_value(status, target_kind) >= target_cycles
        report.update(
            {
                "ok": reached,
                "attempted_cycles": attempts,
                "final_status": status,
                "final_counter": counter_value(status, target_kind),
                "go_live_gate": {
                    "status": gate_payload.get("status"),
                    "ready_to_enable_live": gate_payload.get("ready_to_enable_live"),
                    "blocking_gates": gate_payload.get("blocking_gates") or [],
                    "testnet_gate": find_testnet_gate(gate_payload),
                },
                "completed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
        )
        path = write_report(report)
        report["report_path"] = str(path)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if reached else 1
    except (URLError, TimeoutError, OSError, RuntimeError, ValueError) as exc:
        report["error"] = f"{exc.__class__.__name__}: {exc}"
        report["completed_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        report["report_path"] = str(write_report(report))
        return fail("could not complete Testnet drill runner", report)


if __name__ == "__main__":
    raise SystemExit(main())
