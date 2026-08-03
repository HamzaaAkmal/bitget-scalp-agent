"""Centralized MarketDataCache for zero-latency market snapshot reuse and staleness checking."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MarketDataCache:
    def __init__(self, default_stale_ms: int = 3000) -> None:
        self.default_stale_ms = default_stale_ms
        self._snapshots: Dict[str, Dict[str, Any]] = {}

    def update_snapshot(self, symbol: str, data: Dict[str, Any]) -> Dict[str, Any]:
        now_ms = int(time.time() * 1000)
        
        best_bid = float(data.get("best_bid") or data.get("bid_price") or data.get("last_price") or 0.0)
        best_ask = float(data.get("best_ask") or data.get("ask_price") or data.get("last_price") or 0.0)
        mid_price = (best_bid + best_ask) / 2.0 if (best_bid + best_ask) > 0 else float(data.get("last_price") or 1.0)
        
        spread_bps = float(data.get("spread_bps", 0.0))
        if spread_bps <= 0 and mid_price > 0 and (best_ask - best_bid) > 0:
            spread_bps = round(((best_ask - best_bid) / mid_price) * 10000.0, 2)

        snapshot = {
            "symbol": symbol,
            "exchange_timestamp_ms": data.get("timestamp_ms", now_ms),
            "received_timestamp_ms": now_ms,
            "last_price": float(data.get("last_price") or mid_price),
            "mark_price": float(data.get("mark_price") or data.get("last_price") or mid_price),
            "index_price": float(data.get("index_price") or data.get("mark_price") or mid_price),
            "best_bid": best_bid,
            "best_ask": best_ask,
            "spread_bps": spread_bps,
            "bid_depth_usdt": float(data.get("bid_depth_usdt", 0.0)),
            "ask_depth_usdt": float(data.get("ask_depth_usdt", 0.0)),
            "order_book_imbalance": float(data.get("order_book_imbalance", 0.0)),
            "trade_flow_delta": float(data.get("trade_flow_delta", 0.0)),
            "volume_24h_usdt": float(data.get("volume_24h_usdt", 0.0)),
            "funding_rate": float(data.get("funding_rate", 0.0)),
            "open_interest": float(data.get("open_interest", 0.0)),
            "open_interest_delta_pct": float(data.get("open_interest_delta_pct", 0.0)),
            "realized_volatility": float(data.get("realized_volatility", 0.0)),
            "candles": data.get("candles", []),
            "data_age_ms": 0,
            "connection_state": data.get("connection_state", "HEALTHY"),
        }

        self._snapshots[symbol] = snapshot
        return snapshot

    def get_snapshot(self, symbol: str) -> Optional[Dict[str, Any]]:
        snapshot = self._snapshots.get(symbol)
        if not snapshot:
            return None

        now_ms = int(time.time() * 1000)
        age_ms = now_ms - snapshot["received_timestamp_ms"]
        snapshot["data_age_ms"] = age_ms
        return snapshot

    def is_stale(self, symbol: str, max_stale_ms: int | None = None) -> bool:
        limit = max_stale_ms if max_stale_ms is not None else self.default_stale_ms
        snapshot = self.get_snapshot(symbol)
        if not snapshot:
            return True
        return snapshot["data_age_ms"] > limit


_market_data_cache_instance: MarketDataCache | None = None


def get_market_data_cache() -> MarketDataCache:
    global _market_data_cache_instance
    if _market_data_cache_instance is None:
        _market_data_cache_instance = MarketDataCache()
    return _market_data_cache_instance
