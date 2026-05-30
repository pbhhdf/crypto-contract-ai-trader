from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path
from typing import Any, Callable


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from app import server  # noqa: E402


def fail(message: str, payload: Any | None = None) -> int:
    print(f"FAILED: {message}", file=sys.stderr)
    if payload is not None:
        print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
    return 1


def cleanup(order_ids: list[str], run_ids: list[str]) -> None:
    ids = set(order_ids)
    if run_ids:
        for order in server.get_orders(limit=2000):
            if order.get("run_id") in run_ids:
                ids.add(str(order.get("id")))
    if not ids:
        return
    placeholders = ", ".join("?" for _ in ids)
    values = sorted(ids)
    with server.DB_LOCK, server.connect() as conn:
        conn.execute(f"DELETE FROM order_transitions WHERE order_id IN ({placeholders})", values)
        conn.execute(f"DELETE FROM orders WHERE id IN ({placeholders})", values)
        conn.commit()


def intent(symbol: str) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "side": "BUY",
        "confidence": 0.82,
        "entry_price": 50000.0,
        "stop_loss": 49000.0,
        "take_profit": 52000.0,
        "leverage": 2.0,
        "position_pct": 0.01,
        "time_horizon": "30-90 minutes",
        "provider": "rules",
        "model": "deterministic_rules_v1",
        "ai_enabled": False,
        "fallback_reason": None,
        "rationale": "unknown submit reconcile smoke",
    }


def fresh_market(symbol: str) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "data_source": "binance_public",
        "fallback": False,
        "source_error": None,
        "timestamp": server.utc_now(),
        "mark_price": 50000.0,
        "liquidation_pressure": "low",
    }


def fresh_account(mode: str) -> dict[str, Any]:
    return {
        "source": mode,
        "snapshot_id": f"EXSNAP-{mode}",
        "synced_at": server.utc_now(),
        "equity_usdt": 2500.0,
        "free_margin_usdt": 2400.0,
        "open_position_count": 0,
    }


def fake_order_params(order: dict[str, Any], mode: str = "binance_testnet_validate") -> dict[str, Any]:
    return {
        "symbol": order["symbol"],
        "side": order["side"],
        "type": "LIMIT",
        "timeInForce": "GTC",
        "quantity": "0.001",
        "price": "50000",
        "newClientOrderId": order["client_order_id"],
        "newOrderRespType": "RESULT",
    }


def fake_sync(name: str) -> Callable[[dict[str, Any], str], dict[str, Any]]:
    def _sync(order: dict[str, Any], mode: str) -> dict[str, Any]:
        return {
            "status": "smoke_skipped",
            "name": name,
            "mode": mode,
            "symbol": order.get("symbol"),
            "checked_at": server.utc_now(),
        }

    return _sync


def run_unknown_submit_case(
    mode: str,
    symbol: str,
    run_id: str,
    submit_calls: list[dict[str, Any]],
    reconcile_calls: list[dict[str, Any]],
    consumed_orders: list[str] | None = None,
) -> dict[str, Any]:
    consumed_orders = consumed_orders if consumed_orders is not None else []
    risk = {
        "status": "approved",
        "checks": [],
        "account": fresh_account(mode),
        "market": fresh_market(symbol),
    }
    first = server.execute_order(run_id, intent(symbol), risk, mode)
    if not first:
        raise AssertionError("execute_order returned no order for unknown submit smoke")
    order_id = str(first.get("id"))
    stored = server.get_order(order_id) or {}
    if stored.get("status") != "pending_reconcile":
        raise AssertionError(f"unknown submit should remain pending_reconcile, got {stored}")
    if stored.get("venue_status") != "UNKNOWN" or stored.get("reconcile_status") != "needs_reconcile":
        raise AssertionError(f"unknown submit should require reconcile, got {stored}")
    if len(submit_calls) != 1:
        raise AssertionError(f"unknown submit should attempt exactly one POST before blocking retry: {submit_calls}")
    if not reconcile_calls:
        raise AssertionError("unknown submit should immediately query venue by clientOrderId before any retry")
    query = reconcile_calls[-1]
    if query.get("method") != "GET" or query.get("path") != "/fapi/v1/order":
        raise AssertionError(f"unknown submit reconcile used unexpected endpoint: {query}")
    if query.get("params", {}).get("origClientOrderId") != stored.get("client_order_id"):
        raise AssertionError(
            "unknown submit reconcile did not query by the stored clientOrderId",
        )
    conflicts = server.stateful_order_conflicts(mode, symbol)
    if not any(item.get("id") == order_id for item in conflicts):
        raise AssertionError(f"pending unknown order did not block new stateful execution: {conflicts}")

    submit_count_before_retry = len(submit_calls)
    try:
        server.execute_order(f"{run_id}-RETRY", intent(symbol), risk, mode)
        raise AssertionError("retry should be blocked by pending_reconcile before another POST")
    except ValueError as exc:
        if "Stateful order conflict blocks" not in str(exc):
            raise
    if len(submit_calls) != submit_count_before_retry:
        raise AssertionError("retry attempted another POST instead of stopping at OMS conflict")

    if mode == "live_guarded" and consumed_orders != [order_id]:
        raise AssertionError(f"live unknown submit should consume one short arming slot once: {consumed_orders}")

    return {
        "mode": mode,
        "order_id": order_id,
        "client_order_id": stored.get("client_order_id"),
        "status": stored.get("status"),
        "venue_status": stored.get("venue_status"),
        "reconcile_status": stored.get("reconcile_status"),
        "submit_calls": len(submit_calls),
        "reconcile_query": query,
        "retry_blocked_before_post": True,
        "consumed_orders": consumed_orders,
    }


def main() -> int:
    server.init_db()
    suffix = uuid.uuid4().hex[:8].upper()
    run_ids = [
        f"RUN-UNKNOWN-TESTNET-{suffix}",
        f"RUN-UNKNOWN-LIVE-{suffix}",
        f"RUN-UNKNOWN-TESTNET-{suffix}-RETRY",
        f"RUN-UNKNOWN-LIVE-{suffix}-RETRY",
    ]
    order_ids: list[str] = []
    originals = {
        "BINANCE_PLACE_TESTNET_ORDERS": server.BINANCE_PLACE_TESTNET_ORDERS,
        "ENABLE_BINANCE_TESTNET": server.ENABLE_BINANCE_TESTNET,
        "BINANCE_API_KEY": server.BINANCE_API_KEY,
        "BINANCE_API_SECRET": server.BINANCE_API_SECRET,
        "ENABLE_BINANCE_LIVE": server.ENABLE_BINANCE_LIVE,
        "BINANCE_LIVE_API_KEY": server.BINANCE_LIVE_API_KEY,
        "BINANCE_LIVE_API_SECRET": server.BINANCE_LIVE_API_SECRET,
        "BINANCE_PLACE_LIVE_ORDERS": server.BINANCE_PLACE_LIVE_ORDERS,
        "LIVE_TRADING_CONFIRMATION": server.LIVE_TRADING_CONFIRMATION,
        "account_state_for_mode": server.account_state_for_mode,
        "assert_no_exchange_open_orders": server.assert_no_exchange_open_orders,
        "assert_no_exchange_positions": server.assert_no_exchange_positions,
        "binance_order_params": server.binance_order_params,
        "ensure_binance_margin_type": server.ensure_binance_margin_type,
        "ensure_binance_leverage": server.ensure_binance_leverage,
        "validate_binance_order_bundle": server.validate_binance_order_bundle,
        "signed_binance_request": server.signed_binance_request,
        "signed_binance_request_for_mode": server.signed_binance_request_for_mode,
        "assert_go_live_gate_allows_live_order": server.assert_go_live_gate_allows_live_order,
        "consume_live_arming_order": server.consume_live_arming_order,
    }
    try:
        cleanup([], run_ids)
        server.BINANCE_PLACE_TESTNET_ORDERS = True
        server.ENABLE_BINANCE_TESTNET = True
        server.BINANCE_API_KEY = "testnet-key"
        server.BINANCE_API_SECRET = "testnet-secret"
        server.ENABLE_BINANCE_LIVE = True
        server.BINANCE_LIVE_API_KEY = "live-key"
        server.BINANCE_LIVE_API_SECRET = "live-secret"
        server.BINANCE_PLACE_LIVE_ORDERS = True
        server.LIVE_TRADING_CONFIRMATION = "I_UNDERSTAND_LIVE_RISK"
        server.account_state_for_mode = lambda mode: fresh_account(str(mode or "").lower().strip())
        server.assert_no_exchange_open_orders = lambda mode: {"status": "pass", "mode": mode, "orders": []}
        server.assert_no_exchange_positions = lambda mode: {"status": "pass", "mode": mode, "positions": []}
        server.binance_order_params = fake_order_params
        server.ensure_binance_margin_type = fake_sync("margin_type")
        server.ensure_binance_leverage = fake_sync("leverage")
        server.validate_binance_order_bundle = lambda order, params, mode: {
            "status": "validated",
            "mode": mode,
            "client_order_id": params.get("newClientOrderId"),
        }
        server.assert_go_live_gate_allows_live_order = lambda: {
            "status": "armed",
            "ready_for_live_order": True,
            "blocking_gates": [],
        }

        testnet_submit_calls: list[dict[str, Any]] = []
        testnet_reconcile_calls: list[dict[str, Any]] = []

        def testnet_submit(method: str, path: str, params: dict[str, Any]) -> Any:
            testnet_submit_calls.append({"method": method, "path": path, "params": dict(params)})
            raise RuntimeError("simulated Binance 503 unknown submit state")

        def testnet_reconcile(method: str, path: str, params: dict[str, Any], request_mode: str) -> Any:
            testnet_reconcile_calls.append(
                {"method": method, "path": path, "mode": request_mode, "params": dict(params)}
            )
            raise RuntimeError("simulated venue query unavailable")

        server.signed_binance_request = testnet_submit
        server.signed_binance_request_for_mode = testnet_reconcile
        testnet = run_unknown_submit_case(
            "binance_testnet_place_order",
            f"UNKT{suffix[:4]}USDT",
            run_ids[0],
            testnet_submit_calls,
            testnet_reconcile_calls,
        )
        testnet["submit_calls_detail"] = testnet_submit_calls
        testnet["reconcile_calls_detail"] = testnet_reconcile_calls
        order_ids.append(testnet["order_id"])

        live_calls: list[dict[str, Any]] = []
        consumed_orders: list[str] = []

        def live_signed_for_mode(method: str, path: str, params: dict[str, Any], request_mode: str) -> Any:
            call = {"method": method, "path": path, "mode": request_mode, "params": dict(params)}
            if method == "POST" and path == "/fapi/v1/order":
                live_calls.append(call)
            else:
                live_reconcile_calls.append(call)
            raise RuntimeError("simulated Binance 503 unknown submit or query state")

        def live_consume(order_id: str) -> dict[str, Any]:
            consumed_orders.append(order_id)
            return {"armed": True, "remaining_orders": 0, "order_ids": [order_id]}

        server.signed_binance_request_for_mode = live_signed_for_mode
        server.consume_live_arming_order = live_consume
        live_reconcile_calls: list[dict[str, Any]] = []
        live = run_unknown_submit_case(
            "live_guarded",
            f"UNKL{suffix[:4]}USDT",
            run_ids[1],
            live_calls,
            live_reconcile_calls,
            consumed_orders,
        )
        live["signed_calls_detail"] = live_calls
        live["reconcile_calls_detail"] = live_reconcile_calls
        live["consumed_orders"] = consumed_orders
        order_ids.append(live["order_id"])

        print(
            json.dumps(
                {
                    "ok": True,
                    "testnet": testnet,
                    "live_guarded": live,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    except AssertionError as exc:
        return fail(str(exc))
    finally:
        for name, value in originals.items():
            setattr(server, name, value)
        cleanup(order_ids, run_ids)


if __name__ == "__main__":
    raise SystemExit(main())
