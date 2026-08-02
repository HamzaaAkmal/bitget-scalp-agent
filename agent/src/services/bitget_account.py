"""Bitget account reads via official MCP."""

from __future__ import annotations

from typing import Any

from src.services.bitget_mcp import bitget_connection_status, call_bitget_tool, normalize_category, normalize_symbol


def get_connection_status() -> dict[str, Any]:
    return bitget_connection_status()


def get_account_overview(*, category: str | None = None, symbol: str | None = None, coin: str | None = None) -> dict[str, Any]:
    args: dict[str, Any] = {"view": "summary"}
    if category:
        args["category"] = normalize_category(category)
    if symbol:
        args["symbol"] = normalize_symbol(symbol)
    if coin:
        args["coin"] = str(coin).strip().upper()
    return call_bitget_tool("account_overview", args, read_only=True)
