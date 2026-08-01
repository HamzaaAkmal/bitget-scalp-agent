"""Bitget position and order reads via official MCP."""

from __future__ import annotations

from typing import Any

from src.services.bitget_mcp import call_bitget_tool, normalize_category, normalize_symbol


def get_positions(*, category: str = "USDT-FUTURES", symbol: str | None = None) -> dict[str, Any]:
    args: dict[str, Any] = {"action": "info", "category": normalize_category(category), "view": "summary"}
    if symbol:
        args["symbol"] = normalize_symbol(symbol)
    return call_bitget_tool("position", args)


def get_open_orders(*, category: str = "USDT-FUTURES", symbol: str | None = None) -> dict[str, Any]:
    args: dict[str, Any] = {"action": "open", "category": normalize_category(category), "view": "summary"}
    if symbol:
        args["symbol"] = normalize_symbol(symbol)
    return call_bitget_tool("order", args)

