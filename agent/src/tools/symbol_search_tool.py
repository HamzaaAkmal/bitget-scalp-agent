"""Read-only crypto symbol search backed by Bitget MCP metadata."""

from __future__ import annotations

import json
from typing import Any

from src.agent.tools import BaseTool
from src.services.bitget_symbols import search_symbols

_MAX_LIMIT = 25
_DEFAULT_LIMIT = 10

_CRYPTO_ALIASES: dict[str, dict[str, str]] = {
    "bitcoin": {"symbol": "BTCUSDT", "name": "Bitcoin", "base": "BTC"},
    "btc": {"symbol": "BTCUSDT", "name": "Bitcoin", "base": "BTC"},
    "btc-usd": {"symbol": "BTCUSDT", "name": "Bitcoin", "base": "BTC"},
    "btcusd": {"symbol": "BTCUSDT", "name": "Bitcoin", "base": "BTC"},
    "btc-usdt": {"symbol": "BTCUSDT", "name": "Bitcoin", "base": "BTC"},
    "btcusdt": {"symbol": "BTCUSDT", "name": "Bitcoin", "base": "BTC"},
    "ethereum": {"symbol": "ETHUSDT", "name": "Ethereum", "base": "ETH"},
    "ether": {"symbol": "ETHUSDT", "name": "Ethereum", "base": "ETH"},
    "eth": {"symbol": "ETHUSDT", "name": "Ethereum", "base": "ETH"},
    "solana": {"symbol": "SOLUSDT", "name": "Solana", "base": "SOL"},
    "sol": {"symbol": "SOLUSDT", "name": "Solana", "base": "SOL"},
    "xrp": {"symbol": "XRPUSDT", "name": "XRP", "base": "XRP"},
    "dogecoin": {"symbol": "DOGEUSDT", "name": "Dogecoin", "base": "DOGE"},
    "doge": {"symbol": "DOGEUSDT", "name": "Dogecoin", "base": "DOGE"},
    "pepe": {"symbol": "PEPEUSDT", "name": "Pepe", "base": "PEPE"},
}


class SymbolSearchTool(BaseTool):
    """Resolve a crypto name or ticker fragment to Bitget symbols."""

    name = "search_symbol"
    description = (
        "Resolve a crypto name or ticker fragment to Bitget-backed trading "
        "symbols, e.g. BTCUSDT. Use this before calling get_market_data, "
        "technical_indicators, or Bitget execution tools."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Free-text crypto name or ticker fragment, e.g. bitcoin, btc, ethereum, sol.",
            },
            "limit": {
                "type": "integer",
                "description": f"Maximum candidates to return (1-{_MAX_LIMIT}). Defaults to {_DEFAULT_LIMIT}.",
                "default": _DEFAULT_LIMIT,
            },
        },
        "required": ["query"],
    }
    repeatable = True
    is_readonly = True

    def execute(self, **kwargs: Any) -> str:
        query = str(kwargs.get("query") or "").strip()
        if not query:
            return _error("'query' is required and must be a non-empty string")

        limit = _clamp_limit(kwargs.get("limit", _DEFAULT_LIMIT))
        alias = _search_crypto_alias(query)
        if alias is not None:
            return json.dumps(
                {
                    "ok": True,
                    "market": "crypto",
                    "source": "symbol_search",
                    "data": {
                        "query": query,
                        "count": 1,
                        "candidates": [alias],
                        "sources": {"bitget_mcp": "alias"},
                    },
                },
                ensure_ascii=False,
            )

        bitget = search_symbols(query, limit=limit)
        candidates = list(bitget.get("candidates") or [])
        sources = bitget.get("sources") if isinstance(bitget.get("sources"), dict) else {"bitget_mcp": "ok"}
        return json.dumps(
            {
                "ok": True,
                "market": "crypto",
                "source": "symbol_search",
                "data": {
                    "query": query,
                    "count": len(candidates),
                    "candidates": candidates,
                    "sources": sources,
                },
            },
            ensure_ascii=False,
        )


def _clamp_limit(value: Any) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError, OverflowError):
        return _DEFAULT_LIMIT
    return max(1, min(n, _MAX_LIMIT))


def _search_crypto_alias(query: str) -> dict[str, Any] | None:
    normalized = "".join(ch for ch in query.strip().casefold() if ch.isalnum())
    if not normalized:
        return None
    for key, item in _CRYPTO_ALIASES.items():
        key_norm = "".join(ch for ch in key.casefold() if ch.isalnum())
        if normalized == key_norm:
            return {
                "symbol": item["symbol"],
                "name": item["name"],
                "market": "crypto",
                "type": "cryptocurrency",
                "exchange": "bitget",
                "source": "bitget_mcp",
                "quote_currency": "USDT",
                "category": "USDT-FUTURES",
            }
    return None


def _error(message: str) -> str:
    return json.dumps({"ok": False, "error": message}, ensure_ascii=False)

