"""Bitget execution helpers that require a confirmed proposal."""

from __future__ import annotations

from typing import Any

from src.services.bitget_mcp import call_bitget_tool, normalize_category, normalize_symbol
from src.services.trade_confirmation import (
    explicit_confirmation,
    get_trade_proposal,
    mark_trade_executed,
    proposal_is_expired,
)


def execute_confirmed_trade(
    proposal_id: str,
    *,
    confirmation_text: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Execute a stored trade proposal through the official Bitget MCP server."""
    if not proposal_id or not str(proposal_id).startswith("btg_"):
        return {
            "status": "error",
            "error": f"Invalid proposal_id '{proposal_id}'. You MUST call bitget_prepare_trade first to generate a valid proposal_id (e.g. btg_...). Never guess or pass the user prompt as the proposal_id."
        }

    proposal = get_trade_proposal(proposal_id)
    if proposal is None:
        return {"status": "error", "error": f"Unknown trade proposal: {proposal_id}. You MUST call bitget_prepare_trade first."}
    if proposal_is_expired(proposal):
        return {"status": "error", "error": "trade proposal expired; create a fresh proposal"}
    if not explicit_confirmation(confirmation_text):
        return {"status": "error", "error": "explicit confirmation is required before Bitget execution"}
    if str(proposal.get("direction") or "").upper() == "WAIT":
        return {"status": "error", "error": "WAIT proposals cannot be executed"}

    symbol = normalize_symbol(str((proposal.get("symbol") or {}).get("symbol") or ""))
    category = normalize_category(proposal.get("category"))
    side = "buy" if str(proposal.get("direction")).upper() == "BUY" else "sell"
    qty = proposal.get("suggested_qty")
    if not symbol or not qty:
        return {"status": "error", "error": "proposal is missing executable symbol or quantity"}

    actions: list[dict[str, Any]] = []
    leverage = int(proposal.get("suggested_leverage") or 1)
    if category != "SPOT" and leverage > 1:
        leverage_args: dict[str, Any] = {
            "action": "setLeverage",
            "category": category,
            "symbol": symbol,
            "leverage": str(leverage),
            "confirm": True,
        }
        if category == "USDT-FUTURES":
            leverage_args["marginCoin"] = "USDT"
            
        pos_side = "long" if side == "buy" else "short"
        if str(proposal.get("margin_mode") or "").lower().startswith("isolated"):
            leverage_args["posSide"] = pos_side
            
        lev_res = call_bitget_tool("account_config", leverage_args)
        actions.append({"step": "set_leverage", "result": lev_res})
        
        if str(lev_res.get("status", "")).lower() != "ok":
            err_msg = lev_res.get("error") or lev_res.get("message") or "Unknown leverage error"
            return {
                "status": "error",
                "error": f"CRITICAL: Failed to apply {leverage}x leverage on Bitget. Aborting trade execution. ({err_msg})",
                "actions": actions,
            }

    from src.services.bitget_symbols import format_bitget_price, format_bitget_qty

    formatted_qty = format_bitget_qty(symbol, qty)

    order_args: dict[str, Any] = {
        "action": "place",
        "category": category,
        "symbol": symbol,
        "qty": str(formatted_qty or qty),
        "side": side,
        "orderType": "market",
        "clientOid": f"vt-{proposal_id}",
        "dryRun": bool(dry_run),
        "confirm": True,
    }
    if category != "SPOT":
        order_args.update(
            {
                "posSide": "long" if side == "buy" else "short",
                "reduceOnly": "no",
                "marginMode": proposal.get("margin_mode") or "isolated",
                "takeProfit": format_bitget_price(symbol, proposal.get("take_profit")),
                "stopLoss": format_bitget_price(symbol, proposal.get("stop_loss")),
                "tpTriggerBy": "market",
                "slTriggerBy": "market",
                "tpOrderType": "market",
                "slOrderType": "market",
            }
        )
    order_result = call_bitget_tool("order", order_args)
    actions.append({"step": "place_order", "result": order_result})

    status = "ok" if str(order_result.get("status", "")).lower() == "ok" else "error"
    execution = {
        "status": status,
        "proposal_id": proposal_id,
        "dry_run": bool(dry_run),
        "symbol": symbol,
        "category": category,
        "side": side,
        "qty": qty,
        "actions": actions,
        "order": order_result,
    }
    mark_trade_executed(proposal_id, execution)
    return execution


def cancel_order(*, order_id: str, category: str, symbol: str | None = None) -> dict[str, Any]:
    args: dict[str, Any] = {
        "action": "cancel",
        "category": normalize_category(category),
        "orderId": str(order_id),
    }
    if symbol:
        args["symbol"] = normalize_symbol(symbol)
    return call_bitget_tool("order", args)


def close_position(
    *,
    category: str,
    symbol: str,
    pos_side: str | None = None,
    confirmation_text: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    if not explicit_confirmation(confirmation_text):
        return {"status": "error", "error": "explicit confirmation is required before closing a position"}
    args: dict[str, Any] = {
        "action": "close",
        "category": normalize_category(category),
        "symbol": normalize_symbol(symbol),
        "confirm": True,
        "dryRun": bool(dry_run),
    }
    if pos_side:
        args["posSide"] = str(pos_side).lower()
    return call_bitget_tool("position", args)

