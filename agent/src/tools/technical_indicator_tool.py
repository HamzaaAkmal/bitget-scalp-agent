"""Read-only technical indicator tool.

Computes RSI, MACD, Bollinger Bands, SMA, and EMA for a given symbol using the
existing market-data pipeline. All computation is pure Python (numpy/pandas);
no new dependencies.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd

from src.agent.tools import BaseTool
from src.services.bitget_mcp import fetch_candles

logger = logging.getLogger(__name__)

# ── Indicator defaults ────────────────────────────────────────────────────────
_RSI_PERIOD = 14
_MACD_FAST = 12
_MACD_SLOW = 26
_MACD_SIGNAL = 9
_BB_PERIOD = 20
_BB_STD = 2.0
_SMA_PERIODS = (20, 50, 200)
_EMA_PERIOD = 20
_DEFAULT_LOOKBACK = 200
_MAX_LOOKBACK = 500
_CRYPTO_SYMBOL_RE = re.compile(r"^[A-Z0-9]{2,15}[-/](?:USD|USDT|USDC)$", re.I)


def _is_crypto_symbol(symbol: str) -> bool:
    return bool(_CRYPTO_SYMBOL_RE.match(symbol.strip()))


def _normalize_crypto_symbol(symbol: str) -> str:
    value = symbol.strip().upper().replace("/", "-")
    if value.endswith("-USD"):
        return value.removesuffix("-USD") + "-USDT"
    return value


def _normalize_interval(interval: str) -> str:
    value = interval.strip()
    aliases = {
        "1d": "1D",
        "day": "1D",
        "daily": "1D",
        "1h": "1H",
        "60m": "1H",
        "1w": "1W",
        "week": "1W",
        "weekly": "1W",
        "15min": "15m",
        "5min": "5m",
        "1min": "1m",
    }
    return aliases.get(value.casefold(), value)


def _date_window(interval: str, lookback: int) -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    normalized = interval.strip().lower()
    if normalized.endswith("m"):
        start = now - timedelta(minutes=lookback * int(normalized[:-1] or "1") * 3)
    elif normalized.endswith("h"):
        start = now - timedelta(hours=lookback * int(normalized[:-1] or "1") * 3)
    else:
        start = now - timedelta(days=lookback * 2)
    return start.isoformat(), now.isoformat()


def _records_to_frame(raw: Any) -> pd.DataFrame:
    if isinstance(raw, dict):
        records = raw.get("data")
    else:
        records = raw
    if not isinstance(records, list) or not records:
        return pd.DataFrame()
    frame = pd.DataFrame([row for row in records if isinstance(row, dict)])
    if frame.empty:
        return frame
    date_col = next((col for col in ("trade_date", "date", "time", "timestamp") if col in frame.columns), None)
    if date_col:
        numeric_dates = pd.to_numeric(frame[date_col], errors="coerce")
        if numeric_dates.notna().any():
            median = float(numeric_dates.dropna().median())
            unit = "ms" if median > 1_000_000_000_000 else "s"
            frame[date_col] = pd.to_datetime(numeric_dates, unit=unit, errors="coerce", utc=True)
        else:
            frame[date_col] = pd.to_datetime(frame[date_col], errors="coerce", utc=True)
        frame = frame.dropna(subset=[date_col]).set_index(date_col).sort_index()
    for column in ("open", "high", "low", "close", "volume"):
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.dropna(subset=["close"]) if "close" in frame.columns else frame


def _compute_sma(close: pd.Series, period: int) -> float | None:
    """Simple moving average over the last *period* bars."""
    if len(close) < period:
        return None
    return float(close.iloc[-period:].mean())


def _compute_ema(close: pd.Series, period: int) -> float | None:
    """Exponential moving average over the full series."""
    if len(close) < period:
        return None
    return float(close.ewm(span=period, adjust=False).mean().iloc[-1])


def _compute_rsi(close: pd.Series, period: int = _RSI_PERIOD) -> float | None:
    """Relative Strength Index (Wilder smoothing) over *period* bars."""
    if len(close) < period + 1:
        return None
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.rolling(window=period).mean().iloc[-1]
    avg_loss = loss.rolling(window=period).mean().iloc[-1]
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return float(100.0 - (100.0 / (1.0 + rs)))


def _compute_macd(
    close: pd.Series,
    fast: int = _MACD_FAST,
    slow: int = _MACD_SLOW,
    signal: int = _MACD_SIGNAL,
) -> dict[str, float | None] | None:
    """MACD line, signal line, and histogram."""
    if len(close) < slow + signal:
        return None
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return {
        "macd_line": round(float(macd_line.iloc[-1]), 4),
        "signal_line": round(float(signal_line.iloc[-1]), 4),
        "histogram": round(float(histogram.iloc[-1]), 4),
    }


def _compute_bollinger(
    close: pd.Series,
    period: int = _BB_PERIOD,
    num_std: float = _BB_STD,
) -> dict[str, float | None] | None:
    """Bollinger Bands: upper, middle (SMA), lower."""
    if len(close) < period:
        return None
    sma = close.rolling(window=period).mean()
    std = close.rolling(window=period).std()
    return {
        "upper": round(float(sma.iloc[-1] + num_std * std.iloc[-1]), 2),
        "middle": round(float(sma.iloc[-1]), 2),
        "lower": round(float(sma.iloc[-1] - num_std * std.iloc[-1]), 2),
    }


class TechnicalIndicatorTool(BaseTool):
    """Compute common technical indicators for a symbol.

    Fetches OHLCV data through the existing loader pipeline, then computes
    RSI, MACD, Bollinger Bands, SMA, and EMA. All math is pure Python; no
    new dependencies, no network calls beyond what the loaders already do.
    """

    name = "technical_indicators"
    description = (
        "Compute common technical indicators (RSI, MACD, Bollinger Bands, "
        "SMA, EMA) for a crypto trading symbol. Uses Bitget market data "
        "for crypto price history, then computes indicators locally."
    )
    parameters = {
        "type": "object",
        "properties": {
            "symbol": {
                "type": "string",
                "description": (
                    "Crypto trading symbol, e.g. BTC-USDT, ETH-USDT, SOL-USDT."
                ),
            },
            "interval": {
                "type": "string",
                "description": "Bar interval: 1m, 5m, 15m, 1h, or 1d.",
                "default": "1d",
            },
            "lookback": {
                "type": "integer",
                "description": (
                    "Number of bars to fetch. Default 200, max 500. "
                    "More bars = more accurate long-term indicators (SMA 200)."
                ),
                "default": _DEFAULT_LOOKBACK,
            },
        },
        "required": ["symbol"],
    }
    repeatable = True
    is_readonly = True

    def execute(self, **kwargs: Any) -> str:
        symbol = str(kwargs.get("symbol", "")).strip()
        interval = _normalize_interval(str(kwargs.get("interval", "1d")).strip())
        lookback_raw = kwargs.get("lookback", _DEFAULT_LOOKBACK)

        if not symbol:
            return json.dumps({"ok": False, "error": "symbol is required"})
        if not _is_crypto_symbol(symbol):
            return json.dumps(
                {
                    "ok": False,
                    "error": "technical_indicators is configured for crypto only. Use symbols like BTC-USDT.",
                }
            )
        symbol = _normalize_crypto_symbol(symbol)

        try:
            lookback = int(lookback_raw)
        except (TypeError, ValueError):
            lookback = _DEFAULT_LOOKBACK
        lookback = max(10, min(lookback, _MAX_LOOKBACK))

        try:
            bars = fetch_candles(symbol=symbol, category="USDT-FUTURES", interval=interval, lookback=lookback)
        except Exception as exc:
            logger.debug("fetch_bitget_candles failed for %s: %s", symbol, exc)
            return json.dumps({"ok": False, "error": f"Failed to fetch data: {exc}"})

        df = _records_to_frame(bars).tail(lookback)
        if df.empty:
            return json.dumps({"ok": False, "error": f"No data returned for {symbol}"})

        close = df.get("close") if isinstance(df, pd.DataFrame) else None
        if close is None:
            # Some loaders return a dict-like structure; try common key names.
            if hasattr(df, "to_dict"):
                d = df.to_dict() if callable(df.to_dict) else dict(df)
                for key in ("close", "Close", "CLOSE", "adj_close"):
                    if key in d:
                        close = pd.Series(d[key])
                        break
        if close is None:
            return json.dumps({"ok": False, "error": "No close price column in data"})

        if not isinstance(close, pd.Series):
            close = pd.Series(close)

        # ── Compute indicators ────────────────────────────────────────────
        indicators: dict[str, Any] = {
            "rsi_14": _compute_rsi(close),
            "macd": _compute_macd(close),
            "bollinger": _compute_bollinger(close),
        }
        for period in _SMA_PERIODS:
            indicators[f"sma_{period}"] = _compute_sma(close, period)
        indicators[f"ema_{_EMA_PERIOD}"] = _compute_ema(close, _EMA_PERIOD)

        latest_close = float(close.iloc[-1]) if len(close) > 0 else None
        latest_date = str(close.index[-1])[:10] if hasattr(close, "index") and len(close) > 0 else None

        return json.dumps(
            {
                "ok": True,
                "symbol": symbol,
                "source": "bitget",
                "interval": interval,
                "latest_close": latest_close,
                "latest_date": latest_date,
                "bars_used": int(len(close)),
                "indicators": indicators,
            },
            ensure_ascii=False,
            default=str,
        )
