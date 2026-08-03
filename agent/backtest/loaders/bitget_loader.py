"""Bitget MCP candle loader for crypto spot and USDT futures markets."""

from __future__ import annotations

import logging
import math
import os
from typing import Dict, List, Optional

import pandas as pd

from backtest.loaders.base import cached_loader_fetch, validate_date_range, validate_ohlc
from backtest.loaders.registry import register
from src.services.bitget_mcp import (
    fetch_candles,
    fetch_candles_history,
    normalize_category,
    normalize_interval,
    normalize_symbol,
)

logger = logging.getLogger(__name__)

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
    "1d": 86400,
    "1D": 86400,
    "1w": 604800,
    "1W": 604800,
}
_MAX_LOOKBACK = 1500


def _timestamp_utc(value: str) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        return ts.tz_localize("UTC")
    return ts.tz_convert("UTC")


def _is_date_only(value: str) -> bool:
    text = value.strip()
    return "T" not in text and " " not in text


def _display_code(code: str) -> str:
    value = code.strip().upper().replace("/", "-")
    
    known_quotes = ("-USDT", "-USDC", "-BTC", "-ETH", "-BGB", "-EUR")
    if value and not any(value.endswith(q) for q in known_quotes):
        if value.endswith("USDT") and "-" not in value:
            value = f"{value.removesuffix('USDT')}-USDT"
        elif value.endswith("-USD"):
            value = value.removesuffix("-USD") + "-USDT"
        elif "-" not in value:
            value = f"{value}-USDT"
    return value


def _lookback_for_range(start: pd.Timestamp, end: pd.Timestamp, seconds: int) -> int:
    bars = math.ceil(max((end - start).total_seconds(), seconds) / seconds) + 5
    return max(20, min(_MAX_LOOKBACK, bars))


def _backtest_category() -> str:
    return normalize_category(os.getenv("BITGET_BACKTEST_CATEGORY", "USDT-FUTURES"))


@register
class DataLoader:
    """Bitget OHLCV loader backed by the official MCP market tool."""

    name = "bitget"
    markets = {"crypto"}
    requires_auth = False

    def is_available(self) -> bool:
        try:
            return bool(fetch_candles(symbol="BTCUSDT", category=_backtest_category(), interval="1D", lookback=20))
        except Exception as exc:  # noqa: BLE001 - availability probe
            logger.warning("Bitget MCP probe failed: %s", exc)
            return False

    def fetch(
        self,
        codes: List[str],
        start_date: str,
        end_date: str,
        *,
        interval: str = "1D",
        fields: Optional[List[str]] = None,
    ) -> Dict[str, pd.DataFrame]:
        validate_date_range(start_date, end_date)
        if fields:
            logger.warning("Bitget ignores extra fields: %s", fields)

        normalized_interval = normalize_interval(interval)
        seconds = _INTERVAL_SECONDS.get(normalized_interval) or _INTERVAL_SECONDS.get(interval.strip())
        if seconds is None:
            logger.warning("unsupported Bitget interval %r; supported: %s", interval, sorted(_INTERVAL_SECONDS))
            return {}

        start = _timestamp_utc(start_date)
        end = _timestamp_utc(end_date)
        if _is_date_only(end_date):
            end += pd.Timedelta(days=1)
        now = pd.Timestamp.now(tz="UTC").floor("s")
        if end > now:
            end = now
        if start >= end:
            logger.warning("Bitget date range is empty after capping future end: %s -> %s", start, end)
            return {}

        category = _backtest_category()
        lookback = _lookback_for_range(start, end, seconds)
        result: Dict[str, pd.DataFrame] = {}
        for code in codes:
            key = _display_code(code)
            symbol = normalize_symbol(key)
            try:
                frame = cached_loader_fetch(
                    source=self.name,
                    symbol=f"{key}:{symbol}:{category}",
                    timeframe=normalized_interval,
                    start_date=start_date,
                    end_date=end_date,
                    fields=None,
                    fetch=lambda symbol=symbol: self._fetch_symbol(
                        symbol=symbol,
                        category=category,
                        interval=normalized_interval,
                        lookback=lookback,
                        start=start,
                        end=end,
                    ),
                )
                if frame is not None and not frame.empty:
                    result[key] = frame
            except Exception as exc:  # noqa: BLE001 - loader boundary
                logger.warning("Bitget failed for %s (%s): %s", code, symbol, exc)
        return result

    @staticmethod
    def _fetch_symbol(
        *,
        symbol: str,
        category: str,
        interval: str,
        lookback: int,
        start: pd.Timestamp,
        end: pd.Timestamp,
    ) -> pd.DataFrame | None:
        rows: list[dict] = []
        page_limit = min(200, lookback)
        step_ms = _INTERVAL_SECONDS[interval] * page_limit * 1000
        cursor_ms = int(start.timestamp() * 1000)
        end_ms = int(end.timestamp() * 1000)
        while cursor_ms < end_ms and len(rows) < _MAX_LOOKBACK:
            window_end = min(cursor_ms + step_ms, end_ms)
            rows.extend(
                fetch_candles_history(
                    symbol=symbol,
                    category=category,
                    interval=interval,
                    start_ms=cursor_ms,
                    end_ms=window_end,
                    limit=page_limit,
                )
            )
            cursor_ms = window_end
        if not rows:
            return None
        frame = pd.DataFrame(rows)
        if frame.empty or "time" not in frame.columns:
            return None
        numeric_time = pd.to_numeric(frame["time"], errors="coerce")
        median = float(numeric_time.dropna().median()) if numeric_time.notna().any() else 0
        unit = "ms" if median > 1_000_000_000_000 else "s"
        frame["trade_date"] = pd.to_datetime(numeric_time, unit=unit, utc=True, errors="coerce").dt.tz_convert(None)
        for column in ("open", "high", "low", "close", "volume"):
            frame[column] = pd.to_numeric(frame.get(column), errors="coerce")
        frame = frame.set_index("trade_date").sort_index()
        frame = frame[~frame.index.duplicated(keep="last")]
        frame = frame[(frame.index >= start.tz_convert(None)) & (frame.index < end.tz_convert(None))]
        frame = frame[["open", "high", "low", "close", "volume"]].dropna(
            subset=["open", "high", "low", "close"]
        )
        frame = validate_ohlc(frame)
        return frame if not frame.empty else None
