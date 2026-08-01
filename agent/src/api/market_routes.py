"""Market-data HTTP routes for the Web UI."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query

from src.market_data import DEFAULT_MAX_ROWS, fetch_market_data
from src.services.bitget_mcp import fetch_candles, normalize_category, normalize_interval, normalize_symbol

_SUPPORTED_INTERVALS = {"1m", "3m", "5m", "15m", "30m", "1h", "1H", "4h", "4H", "6h", "6H", "1d", "1D", "1w", "1W"}
_INTERVAL_SECONDS = {
    "1m": 60,
    "3m": 180,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "1H": 3600,
    "4h": 14400,
    "4H": 14400,
    "6h": 21600,
    "6H": 21600,
    "1d": 86400,
    "1D": 86400,
    "1w": 604800,
    "1W": 604800,
}


def _record_time(row: dict[str, Any]) -> str:
    value = row.get("trade_date") or row.get("timestamp") or row.get("time") or row.get("date")
    return str(value)


def register_market_routes(app: FastAPI) -> None:
    """Mount market-data routes."""
    import sys

    host = sys.modules.get("api_server") or sys.modules.get("agent.api_server")
    if host is None:
        raise RuntimeError("register_market_routes: api_server module not in sys.modules")

    require_auth = host.require_auth

    @app.get("/market/crypto/candles", dependencies=[Depends(require_auth)])
    async def get_crypto_candles(
        symbol: str = Query("BTCUSDT", min_length=3, max_length=32),
        interval: str = Query("5m"),
        category: str = Query("USDT-FUTURES"),
        lookback: int = Query(300, ge=20, le=1500),
    ):
        """Return Bitget-backed crypto candles for the chart UI."""
        if interval not in _SUPPORTED_INTERVALS:
            raise HTTPException(status_code=400, detail="Unsupported interval")

        bitget_symbol = normalize_symbol(symbol)
        bitget_category = normalize_category(category)
        bitget_interval = normalize_interval(interval)
        try:
            bars = fetch_candles(
                symbol=bitget_symbol,
                category=bitget_category,
                interval=bitget_interval,
                lookback=lookback,
            )
            return {
                "status": "ok",
                "provider": "bitget",
                "symbol": bitget_symbol,
                "product_id": bitget_symbol,
                "category": bitget_category,
                "interval": bitget_interval,
                "bars": bars,
                "provenance": {"source": "official_bitget_mcp", "fallback_used": False},
            }
        except Exception:
            # Keep Coinbase as a public market-data fallback when Bitget MCP is
            # unavailable. Execution never falls back.
            pass

        now = datetime.now(timezone.utc)
        seconds = _INTERVAL_SECONDS[interval]
        start = now - timedelta(seconds=seconds * lookback)
        coinbase_symbol = symbol.strip().upper().replace("/", "-")
        if "-" not in coinbase_symbol and coinbase_symbol.endswith("USDT"):
            coinbase_symbol = f"{coinbase_symbol.removesuffix('USDT')}-USDT"
        payload = fetch_market_data(
            codes=[coinbase_symbol],
            start_date=start.isoformat(),
            end_date=now.isoformat(),
            source="coinbase",
            interval=interval,
            max_rows=max(DEFAULT_MAX_ROWS, lookback),
            include_provenance=True,
        )
        key = coinbase_symbol
        rows = payload.get(key)
        if isinstance(rows, dict):
            rows = rows.get("data")
        if not isinstance(rows, list):
            raise HTTPException(status_code=502, detail=f"No Coinbase candle data for {symbol}")

        bars = [
            {
                "time": _record_time(row),
                "open": row.get("open"),
                "high": row.get("high"),
                "low": row.get("low"),
                "close": row.get("close"),
                "volume": row.get("volume", 0),
            }
            for row in rows[-lookback:]
            if isinstance(row, dict)
        ]
        return {
            "status": "ok",
            "provider": "coinbase",
            "symbol": key,
            "product_id": key.removesuffix("-USDT") + "-USD" if key.endswith("-USDT") else key,
            "category": "SPOT",
            "interval": interval,
            "bars": bars,
            "provenance": {**payload.get("_provenance", {}).get(key, {}), "fallback_used": True},
        }
