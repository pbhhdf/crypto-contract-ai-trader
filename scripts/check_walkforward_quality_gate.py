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


def request_json(path: str) -> Any:
    request = Request(f"{BASE_URL}{path}", headers=auth_headers(), method="GET")
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def fail(message: str, payload: object | None = None) -> int:
    print(f"FAILED: {message}", file=sys.stderr)
    if payload is not None:
        print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
    return 1


def main() -> int:
    try:
        payload = request_json("/api/go-live-gate")
        readiness = request_json("/api/readiness")
    except HTTPError as exc:
        return fail(f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}")
    except (URLError, TimeoutError, OSError) as exc:
        return fail(f"could not reach {BASE_URL}: {exc}")

    gate = payload.get("go_live_gate") or {}
    walkforward_gate = next(
        (item for item in gate.get("gates", []) if item.get("id") == "backtest_walkforward"),
        None,
    )
    if not walkforward_gate:
        return fail("go-live gate is missing backtest_walkforward")
    evidence = walkforward_gate.get("evidence") or {}
    thresholds = evidence.get("thresholds") or {}
    for key in (
        "min_folds",
        "min_total_return_pct",
        "min_positive_fold_rate_pct",
        "max_fold_drawdown_pct",
    ):
        if key not in thresholds:
            return fail(f"walk-forward gate missing threshold {key}", evidence)
    if "failures" not in evidence:
        return fail("walk-forward gate does not expose quality failures", evidence)

    readiness_names = {item.get("name") for item in readiness.get("items", [])}
    if "Walk-forward quality" not in readiness_names:
        return fail("readiness does not expose Walk-forward quality")
    print(
        json.dumps(
            {
                "ok": True,
                "gate_status": walkforward_gate.get("status"),
                "thresholds": thresholds,
                "failures": evidence.get("failures"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
