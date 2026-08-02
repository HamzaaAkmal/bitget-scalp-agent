"""Bitget monitoring and trade-management helpers."""

from __future__ import annotations

import time
from typing import Any

from src.services.bitget_account import get_account_overview
from src.services.bitget_mcp import call_bitget_tool, call_market, normalize_category, normalize_symbol
from src.services.bitget_positions import get_open_orders, get_positions
from src.services.trade_confirmation import explicit_confirmation


def get_order_fills(
    *,
    category: str = "USDT-FUTURES",
    symbol: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    args: dict[str, Any] = {
        "action": "fills",
        "category": normalize_category(category),
        "limit": str(max(1, min(int(limit), 100))),
        "view": "summary",
    }
    if symbol:
        args["symbol"] = normalize_symbol(symbol)
    return call_bitget_tool("order", args, read_only=True)


def get_order_history(
    *,
    category: str = "USDT-FUTURES",
    symbol: str | None = None,
    limit: int = 50,
    lookback_hours: int = 24,
) -> dict[str, Any]:
    now = int(time.time() * 1000)
    args: dict[str, Any] = {
        "action": "history",
        "category": normalize_category(category),
        "startTime": str(now - max(1, int(lookback_hours)) * 60 * 60 * 1000),
        "endTime": str(now),
        "limit": str(max(1, min(int(limit), 100))),
        "view": "summary",
    }
    if symbol:
        args["symbol"] = normalize_symbol(symbol)
    return call_bitget_tool("order", args, read_only=True)


def get_strategy_orders(
    *,
    category: str = "USDT-FUTURES",
    symbol: str | None = None,
    status: str = "open",
    limit: int = 50,
) -> dict[str, Any]:
    action = "history" if status == "history" else "open"
    args: dict[str, Any] = {
        "action": action,
        "category": normalize_category(category),
        "limit": str(max(1, min(int(limit), 100))),
        "view": "summary",
    }
    if symbol:
        args["symbol"] = normalize_symbol(symbol)
    return call_bitget_tool("strategy_order", args, read_only=True)


def modify_tpsl(
    *,
    category: str,
    symbol: str,
    pos_side: str,
    take_profit: float | None = None,
    stop_loss: float | None = None,
    qty: float | None = None,
    strategy_order_id: str | None = None,
    confirmation_text: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    if not explicit_confirmation(confirmation_text):
        return {"status": "error", "error": "explicit confirmation is required before modifying TP/SL"}
    args: dict[str, Any] = {
        "action": "modify" if strategy_order_id else "place",
        "category": normalize_category(category),
        "symbol": normalize_symbol(symbol),
        "posSide": str(pos_side or "long").lower(),
        "tpslMode": "partial" if qty else "full",
        "dryRun": bool(dry_run),
        "confirm": True,
    }
    
    from src.services.bitget_symbols import format_bitget_price

    if take_profit is not None:
        args["tpTriggerBy"] = "market"
        args["tpOrderType"] = "market"
        args["takeProfit"] = format_bitget_price(symbol, take_profit)
    if stop_loss is not None:
        args["slTriggerBy"] = "market"
        args["slOrderType"] = "market"
        args["stopLoss"] = format_bitget_price(symbol, stop_loss)

    if not strategy_order_id:
        args["planType"] = "position_tpsl"
        args["marginCoin"] = "USDT"
        args["marginMode"] = "isolated"
        if take_profit is None:
             args["takeProfit"] = ""
        if stop_loss is None:
             args["stopLoss"] = ""
    else:
        args["orderId"] = str(strategy_order_id)
            
    if qty:
        args["qty"] = str(qty)
    if take_profit is None and stop_loss is None:
        return {"status": "error", "error": "take_profit or stop_loss is required"}
    return call_bitget_tool("strategy_order", args)


def partial_close_position(
    *,
    category: str,
    symbol: str,
    pos_side: str,
    qty: float,
    confirmation_text: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    if not explicit_confirmation(confirmation_text):
        return {"status": "error", "error": "explicit confirmation is required before partial close"}
    side = "sell" if str(pos_side or "").lower() == "long" else "buy"
    return call_bitget_tool(
        "order",
        {
            "action": "place",
            "category": normalize_category(category),
            "symbol": normalize_symbol(symbol),
            "side": side,
            "posSide": str(pos_side or "long").lower(),
            "qty": str(qty),
            "orderType": "market",
            "marginCoin": "USDT",
            "marginMode": "isolated",
            "dryRun": bool(dry_run),
            "confirm": True,
        },
    )


def scale_position(
    *,
    category: str,
    symbol: str,
    side: str,
    qty: float,
    pos_side: str | None,
    confirmation_text: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    if not explicit_confirmation(confirmation_text):
        return {"status": "error", "error": "explicit confirmation is required before scaling a position"}
    normalized_side = "sell" if str(side).lower() in {"sell", "short"} else "buy"
    args: dict[str, Any] = {
        "action": "place",
        "category": normalize_category(category),
        "symbol": normalize_symbol(symbol),
        "side": normalized_side,
        "qty": str(qty),
        "orderType": "market",
        "marginCoin": "USDT",
        "marginMode": "isolated",
        "dryRun": bool(dry_run),
        "confirm": True,
    }
    if normalize_category(category) != "SPOT":
        args["posSide"] = str(pos_side or ("short" if normalized_side == "sell" else "long")).lower()
    return call_bitget_tool("order", args)


def build_trailing_stop_proposal(
    *,
    category: str,
    symbol: str,
    pos_side: str,
    callback_percent: float = 1.0,
) -> dict[str, Any]:
    ticker_result = call_market(
        {
            "action": "tickers",
            "category": normalize_category(category),
            "symbol": normalize_symbol(symbol),
            "view": "summary",
        }
    )
    rows = _rows_from_result(ticker_result)
    last = _number(_first_value(rows, "lastPrice", "last", "markPrice", "indexPrice"))
    pct = max(0.1, min(float(callback_percent or 1.0), 25.0)) / 100
    side = str(pos_side or "long").lower()
    trigger = None
    if last is not None:
        trigger = last * (1 - pct) if side == "long" else last * (1 + pct)
    return {
        "status": "ok",
        "symbol": normalize_symbol(symbol),
        "category": normalize_category(category),
        "pos_side": side,
        "last_price": last,
        "callback_percent": round(pct * 100, 4),
        "suggested_stop": trigger,
        "message": "Review this trailing stop proposal and convert it to a TP/SL update when ready.",
        "ticker": ticker_result,
    }


def get_risk_dashboard(*, category: str = "USDT-FUTURES", symbol: str | None = None) -> dict[str, Any]:
    normalized_category = normalize_category(category)
    normalized_symbol = normalize_symbol(symbol or "BTCUSDT")
    account = get_account_overview(category=normalized_category, symbol=normalized_symbol)
    positions = get_positions(category=normalized_category, symbol=symbol)
    orders = get_open_orders(category=normalized_category, symbol=symbol)
    strategy_orders = get_strategy_orders(category=normalized_category, symbol=symbol)
    funding = call_market(
        {
            "action": "fundingRate",
            "category": normalized_category,
            "symbol": normalized_symbol,
            "view": "summary",
        }
    )
    open_interest = call_market(
        {
            "action": "openInterest",
            "category": normalized_category,
            "symbol": normalized_symbol,
            "view": "summary",
        }
    )
    position_rows = _rows_from_result(positions)
    total_notional = sum(abs(_number(_first_value([row], "notional", "marginSize", "total", "usdtEquity")) or 0) for row in position_rows)
    total_unrealized = sum(_number(_first_value([row], "unrealizedPL", "upl", "pnl", "unrealizedPnl")) or 0 for row in position_rows)
    return {
        "status": "ok",
        "category": normalized_category,
        "symbol": normalized_symbol,
        "summary": {
            "positions": len(position_rows),
            "estimated_notional_usdt": round(total_notional, 4),
            "estimated_unrealized_pnl_usdt": round(total_unrealized, 4),
        },
        "account": account,
        "positions": positions,
        "orders": orders,
        "strategy_orders": strategy_orders,
        "funding": funding,
        "open_interest": open_interest,
    }


def get_alerts(*, category: str = "USDT-FUTURES", symbol: str | None = None) -> dict[str, Any]:
    normalized_category = normalize_category(category)
    normalized_symbol = normalize_symbol(symbol or "BTCUSDT")
    positions = get_positions(category=normalized_category, symbol=symbol)
    history = get_order_history(category=normalized_category, symbol=symbol, limit=50, lookback_hours=24)
    ticker = call_market(
        {
            "action": "tickers",
            "category": normalized_category,
            "symbol": normalized_symbol,
            "view": "summary",
        }
    )
    price = _number(_first_value(_rows_from_result(ticker), "lastPrice", "last", "markPrice"))
    alerts: list[dict[str, Any]] = []
    for row in _rows_from_result(positions):
        liq = _number(_first_value([row], "liquidationPrice", "liqPrice", "liqPx"))
        tp = _number(_first_value([row], "takeProfit", "tp", "tpTriggerPrice"))
        sl = _number(_first_value([row], "stopLoss", "sl", "slTriggerPrice"))
        symbol_value = str(_first_value([row], "symbol", "instId") or normalized_symbol)
        if price and liq:
            distance = abs(price - liq) / price
            if distance <= 0.05:
                alerts.append({"type": "liquidation_proximity", "severity": "high", "symbol": symbol_value, "distance_percent": round(distance * 100, 3)})
        for label, target in (("take_profit_proximity", tp), ("stop_loss_proximity", sl)):
            if price and target:
                distance = abs(price - target) / price
                if distance <= 0.01:
                    alerts.append({"type": label, "severity": "medium", "symbol": symbol_value, "distance_percent": round(distance * 100, 3)})
    for row in _rows_from_result(history):
        status = str(_first_value([row], "status", "state", "orderStatus") or "").lower()
        if any(token in status for token in ("reject", "fail", "error")):
            alerts.append({"type": "order_rejection", "severity": "high", "symbol": _first_value([row], "symbol", "instId"), "status": status})
    return {
        "status": "ok",
        "category": normalized_category,
        "symbol": normalized_symbol,
        "alerts": alerts,
        "positions": positions,
        "order_history": history,
        "ticker": ticker,
    }


def _rows_from_result(result: dict[str, Any]) -> list[dict[str, Any]]:
    payload = result.get("structured_content") or result.get("data")
    if isinstance(payload, dict):
        data = payload.get("data") or payload.get("items")
        if isinstance(data, list):
            return [row for row in data if isinstance(row, dict)]
    data = result.get("data")
    if isinstance(data, dict):
        rows = data.get("data") or data.get("items")
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    return []


def _first_value(rows: list[dict[str, Any]], *keys: str) -> Any:
    for row in rows:
        for key in keys:
            if key in row and row[key] not in (None, ""):
                return row[key]
    return None


def _number(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
