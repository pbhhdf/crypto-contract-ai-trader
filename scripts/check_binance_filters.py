from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from app import server  # noqa: E402


def fail(message: str) -> int:
    print(f"FAILED: {message}", file=sys.stderr)
    return 1


def main() -> int:
    order = {
        "id": "TEST-FILTERS",
        "run_id": "filters",
        "symbol": "BTCUSDT",
        "side": "BUY",
        "quantity": 0.137271234,
        "leverage": 2,
        "entry_price": 72999.68951449,
        "stop_loss": 72123.456789,
        "take_profit": 74123.456789,
        "client_order_id": "TEST-FILTERS",
    }
    try:
        params = server.binance_order_params(order, "binance_testnet_validate")
        stop_params, stop_evidence = server.binance_protection_order_params(
            order,
            "stop_loss",
            "binance_testnet_validate",
        )
        take_params, take_evidence = server.binance_protection_order_params(
            order,
            "take_profit",
            "binance_testnet_validate",
        )
    except Exception as exc:  # noqa: BLE001 - smoke test should capture the exact failure.
        return fail(f"Binance filter normalization failed: {exc.__class__.__name__}: {exc}")

    if params["quantity"] == str(order["quantity"]):
        return fail("quantity was not normalized by exchange stepSize")
    if params["price"] == str(order["entry_price"]):
        return fail("price was not normalized by exchange tickSize")
    if stop_params["type"] != "STOP_MARKET" or take_params["type"] != "TAKE_PROFIT_MARKET":
        return fail("protection order types are incorrect")
    if stop_params["side"] != "SELL" or take_params["side"] != "SELL":
        return fail("protection orders must be opposite-side close orders for a BUY entry")
    if stop_params.get("closePosition") != "true" or take_params.get("closePosition") != "true":
        return fail("protection orders must use closePosition=true")
    if "quantity" in stop_params or "quantity" in take_params:
        return fail("closePosition protection orders should not include quantity")

    output = {
        "ok": True,
        "symbol": order["symbol"],
        "entry_params": params,
        "entry_filter": order.get("binance_filter_evidence"),
        "stop_loss": {
            "params": stop_params,
            "evidence": stop_evidence,
        },
        "take_profit": {
            "params": take_params,
            "evidence": take_evidence,
        },
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
