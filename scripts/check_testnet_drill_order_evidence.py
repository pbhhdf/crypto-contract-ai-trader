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


def expect_error(label: str, *args: Any) -> str:
    try:
        server.validate_testnet_drill_order_evidence(*args)
    except RuntimeError as exc:
        return str(exc)
    raise AssertionError(f"{label} unexpectedly passed")


def main() -> int:
    completed_run = {"id": "RUN-TND-EVIDENCE", "status": "completed"}
    failed_run = {"id": "RUN-TND-FAILED", "status": "failed"}
    validate_order = {
        "id": "TEST-VALIDATED",
        "status": "testnet_validated",
        "venue_status": "ORDER_TEST_ACCEPTED",
    }
    placed_order = {
        "id": "TESTLIVE-CANCELED",
        "status": "testnet_canceled",
        "venue_status": "CANCELED",
        "reconcile_status": "reconciled",
    }
    unresolved_cancel = {
        "id": "TESTLIVE-UNKNOWN",
        "status": "pending_reconcile",
        "venue_status": "UNKNOWN",
        "reconcile_status": "needs_reconcile",
    }

    try:
        validate_ok = server.validate_testnet_drill_order_evidence(
            "binance_testnet_validate",
            completed_run,
            validate_order,
            [],
        )
        place_ok = server.validate_testnet_drill_order_evidence(
            "binance_testnet_place_order",
            completed_run,
            placed_order,
            [placed_order],
        )
        missing_order_error = expect_error(
            "missing_order",
            "binance_testnet_place_order",
            completed_run,
            None,
            [],
        )
        no_cleanup_error = expect_error(
            "no_cleanup",
            "binance_testnet_place_order",
            completed_run,
            placed_order,
            [],
        )
        unexpected_status_error = expect_error(
            "unexpected_status",
            "binance_testnet_place_order",
            completed_run,
            unresolved_cancel,
            [unresolved_cancel],
        )
        failed_run_error = expect_error(
            "failed_run",
            "binance_testnet_validate",
            failed_run,
            validate_order,
            [],
        )
    except AssertionError as exc:
        return fail(str(exc))

    for label, evidence in {"validate_ok": validate_ok, "place_ok": place_ok}.items():
        if evidence.get("status") != "pass":
            return fail(f"{label} did not pass", evidence)
    expected_fragments = {
        "missing_order_error": "produced no order evidence",
        "no_cleanup_error": "did not cancel or terminally clean up",
        "unexpected_status_error": "unexpected status=pending_reconcile",
        "failed_run_error": "must complete",
    }
    actual_errors = {
        "missing_order_error": missing_order_error,
        "no_cleanup_error": no_cleanup_error,
        "unexpected_status_error": unexpected_status_error,
        "failed_run_error": failed_run_error,
    }
    for key, fragment in expected_fragments.items():
        if fragment not in actual_errors[key]:
            return fail(f"{key} did not include expected fragment {fragment!r}", actual_errors)

    print(
        json.dumps(
            {
                "ok": True,
                "validate_evidence": validate_ok,
                "place_evidence": place_ok,
                "blocked_errors": actual_errors,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
