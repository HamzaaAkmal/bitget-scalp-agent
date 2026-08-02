"""Bitget futures symbol resolver and instrument metadata cache."""

from __future__ import annotations

import logging
from typing import Any, Dict
from src.services.bitget_symbols import resolve_symbol

logger = logging.getLogger(__name__)


class BitgetSymbolResolver:
    @staticmethod
    def resolve(symbol_query: str, category: str = "USDT-FUTURES") -> Dict[str, Any]:
        res = resolve_symbol(symbol_query, category=category)
        if res.get("status") == "ok":
            return res.get("symbol", {})
        clean = symbol_query.upper().replace("/", "").replace("-", "")
        if not clean.endswith("USDT"):
            clean = f"{clean}USDT"
        return {
            "symbol": clean,
            "base_coin": clean.replace("USDT", ""),
            "quote_coin": "USDT",
            "price_precision": 2 if "BTC" in clean else 4,
            "quantity_precision": 3 if "BTC" in clean else 1,
            "min_trade_num": 0.001 if "BTC" in clean else 0.1,
            "max_leverage": 125 if "BTC" in clean else 50,
        }
