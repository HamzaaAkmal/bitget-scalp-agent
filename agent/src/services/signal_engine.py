"""Natural-language Bitget trade intent and lightweight signal helpers."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from statistics import mean
from typing import Any

from src.services.bitget_mcp import default_product_type, fetch_candles, fetch_ticker, normalize_category
from src.services.bitget_symbols import resolve_symbol

_TIMEFRAME_ALIASES = {
    "1m": "1m",
    "1min": "1m",
    "3m": "3m",
    "3min": "3m",
    "5m": "5m",
    "5min": "5m",
    "15m": "15m",
    "15min": "15m",
    "30m": "30m",
    "30min": "30m",
    "1h": "1H",
    "1hr": "1H",
    "1hour": "1H",
    "4h": "4H",
    "4hr": "4H",
    "4hour": "4H",
    "1d": "1D",
    "1day": "1D",
    "daily": "1D",
    "1w": "1W",
    "1week": "1W",
    "weekly": "1W",
}
_SYMBOL_STOP_WORDS = {
    "on",
    "for",
    "with",
    "using",
    "the",
    "a",
    "an",
    "spot",
    "future",
    "futures",
    "trade",
    "chart",
    "timeframe",
}


@dataclass(frozen=True)
class TradeIntent:
    prompt: str
    symbol_query: str
    category: str | None
    timeframe: str
    direction: str | None
    leverage: int | None
    margin_mode: str
    margin_usdt: float | None
    strategy: str
    risk_style: str
    needs_clarification: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt": self.prompt,
            "symbol_query": self.symbol_query,
            "category": self.category,
            "timeframe": self.timeframe,
            "direction": self.direction,
            "leverage": self.leverage,
            "margin_mode": self.margin_mode,
            "margin_usdt": self.margin_usdt,
            "strategy": self.strategy,
            "risk_style": self.risk_style,
            "needs_clarification": self.needs_clarification,
        }


def parse_trade_intent(prompt: str, *, category_hint: str | None = None, symbol_hint: str | None = None) -> TradeIntent:
    """Parse the actionable trading parameters from a natural-language prompt."""
    text = str(prompt or "").strip()
    lower = text.casefold()
    category = _detect_category(lower, category_hint)
    direction = _detect_direction(lower)
    timeframe = _detect_timeframe(lower)
    leverage = _detect_leverage(lower)
    margin_usdt = _detect_margin(lower)
    margin_mode = "cross" if "cross" in lower else "isolated"
    strategy = "scalp" if "scalp" in lower else "swing" if "swing" in lower else "standard"
    risk_style = "aggressive" if "aggressive" in lower or "high risk" in lower else "conservative" if "conservative" in lower or "low risk" in lower else "balanced"
    symbol_query = symbol_hint or _detect_symbol_query(text) or ""

    clarification = None
    if not symbol_query:
        clarification = "Which Bitget symbol should I analyze?"
    elif category is None:
        clarification = "Do you want spot or futures?"

    return TradeIntent(
        prompt=text,
        symbol_query=symbol_query,
        category=category,
        timeframe=timeframe,
        direction=direction,
        leverage=leverage,
        margin_mode=margin_mode,
        margin_usdt=margin_usdt,
        strategy=strategy,
        risk_style=risk_style,
        needs_clarification=clarification,
    )


def build_market_signal(intent: TradeIntent) -> dict[str, Any]:
    """Resolve the symbol and compute a compact technical signal."""
    if intent.needs_clarification:
        return {"status": "needs_clarification", "message": intent.needs_clarification}
    category = normalize_category(intent.category or default_product_type())
    resolved = resolve_symbol(intent.symbol_query, category=category)
    if resolved.get("status") != "ok":
        return {"status": resolved.get("status", "error"), "message": resolved.get("message"), "resolution": resolved}
    symbol_info = dict(resolved["symbol"])
    symbol = str(symbol_info["symbol"])
    candles = fetch_candles(symbol=symbol, category=category, interval=intent.timeframe, lookback=160)
    if len(candles) < 40:
        ticker = fetch_ticker(symbol=symbol, category=category)
        price = _float_or_none(ticker.get("lastPrice"))
        return {
            "status": "ok",
            "symbol": symbol_info,
            "direction": intent.direction or "WAIT",
            "confidence": 50,
            "entry": price,
            "timeframe": intent.timeframe,
            "reasoning": ["Bitget returned too few candles for a robust indicator stack."],
            "indicators": {},
        }

    closes = [float(row["close"]) for row in candles if _finite(row.get("close"))]
    volumes = [float(row.get("volume") or 0) for row in candles if _finite(row.get("close"))]
    entry = closes[-1]
    ema20 = _ema(closes, 20)
    ema50 = _ema(closes, 50)
    rsi = _rsi(closes, 14)
    macd_line, macd_signal = _macd(closes)
    volume_ratio = (volumes[-1] / mean(volumes[-30:])) if len(volumes) >= 30 and mean(volumes[-30:]) else 1.0

    direction = intent.direction or _infer_direction(entry, ema20, ema50, rsi, macd_line, macd_signal)
    confidence = _confidence(direction, entry, ema20, ema50, rsi, macd_line, macd_signal, volume_ratio, intent.risk_style)
    reasoning = _reasoning(direction, entry, ema20, ema50, rsi, macd_line, macd_signal, volume_ratio)

    return {
        "status": "ok",
        "symbol": symbol_info,
        "direction": direction,
        "confidence": confidence,
        "entry": entry,
        "timeframe": intent.timeframe,
        "reasoning": reasoning,
        "indicators": {
            "ema20": ema20,
            "ema50": ema50,
            "rsi14": rsi,
            "macd": macd_line,
            "macd_signal": macd_signal,
            "volume_ratio_30": round(volume_ratio, 3),
        },
    }


def _detect_category(lower: str, category_hint: str | None) -> str | None:
    if any(token in lower for token in ("future", "futures", "perp", "perpetual", "short", "long", "leverage", "isolated", "cross")):
        return "USDT-FUTURES"
    if "spot" in lower:
        return "SPOT"
    if category_hint:
        return normalize_category(category_hint)
    return None


def _detect_direction(lower: str) -> str | None:
    if re.search(r"\b(short|sell)\b", lower):
        return "SELL"
    if re.search(r"\b(long|buy)\b", lower):
        return "BUY"
    return None


def _detect_timeframe(lower: str) -> str:
    minute = re.search(r"\b(1|3|5|15|30)\s*(?:m|min|minute|minutes)\b", lower)
    if minute:
        return f"{minute.group(1)}m"
    hour = re.search(r"\b(1|4)\s*(?:h|hr|hour|hours)\b", lower)
    if hour:
        return f"{hour.group(1)}H"
    if re.search(r"\b1\s*(?:d|day|days)\b|\bdaily\b", lower):
        return "1D"
    if re.search(r"\b1\s*(?:w|week|weeks)\b|\bweekly\b", lower):
        return "1W"
    match = re.search(r"\b(1m|3m|5m|15m|30m|1h|4h|1d|1w|1min|3min|5min|15min|30min|1hr|4hr|daily|weekly)\b", lower)
    if not match:
        return "15m"
    return _TIMEFRAME_ALIASES.get(match.group(1), "15m")


def _detect_leverage(lower: str) -> int | None:
    match = re.search(r"\b(\d{1,2})\s*x\b", lower)
    if not match:
        return None
    return max(1, int(match.group(1)))


def _detect_margin(lower: str) -> float | None:
    match = re.search(r"\b(?:invest|use|margin|with)\s*\$?\s*(\d+(?:\.\d+)?)\s*(?:usd|usdt|dollars?)?\b", lower)
    if not match:
        return None
    return float(match.group(1))


def _detect_symbol_query(text: str) -> str | None:
    match = re.search(r"\b(?:research|analyze|buy|sell|long|short|scalp|swing|trade)\s+([A-Za-z0-9/-]{2,20})\b", text, re.I)
    if match:
        token = match.group(1)
        if token.casefold() not in _SYMBOL_STOP_WORDS:
            return token
    for token in re.findall(r"\b[A-Z0-9]{2,12}(?:[-/]USDT)?\b", text):
        if token.casefold() not in _SYMBOL_STOP_WORDS:
            return token
    for name in ("bitcoin", "ethereum", "solana", "dogecoin", "pepe", "xrp"):
        if re.search(rf"\b{name}\b", text, re.I):
            return name
    return None


def _infer_direction(entry: float, ema20: float, ema50: float, rsi: float, macd_line: float, macd_signal: float) -> str:
    bullish = entry > ema20 > ema50 and macd_line >= macd_signal and rsi < 72
    bearish = entry < ema20 < ema50 and macd_line <= macd_signal and rsi > 28
    if bullish:
        return "BUY"
    if bearish:
        return "SELL"
    return "WAIT"


def _confidence(direction: str, entry: float, ema20: float, ema50: float, rsi: float, macd_line: float, macd_signal: float, volume_ratio: float, risk_style: str) -> int:
    if direction == "WAIT":
        return 58
    score = 52
    if direction == "BUY":
        score += 12 if entry > ema20 else -8
        score += 10 if ema20 > ema50 else -8
        score += 8 if macd_line > macd_signal else -6
        score += 6 if 45 <= rsi <= 68 else -4
    else:
        score += 12 if entry < ema20 else -8
        score += 10 if ema20 < ema50 else -8
        score += 8 if macd_line < macd_signal else -6
        score += 6 if 32 <= rsi <= 55 else -4
    if volume_ratio > 1.15:
        score += 5
    if risk_style == "aggressive":
        score += 3
    if risk_style == "conservative":
        score -= 3
    return max(0, min(94, int(round(score))))


def _reasoning(direction: str, entry: float, ema20: float, ema50: float, rsi: float, macd_line: float, macd_signal: float, volume_ratio: float) -> list[str]:
    if direction == "WAIT":
        return [
            "Trend and momentum are not aligned enough for a high-conviction entry.",
            f"Price {entry:.6g}, EMA20 {ema20:.6g}, EMA50 {ema50:.6g}, RSI {rsi:.1f}.",
        ]
    side = "bullish" if direction == "BUY" else "bearish"
    return [
        f"{side.capitalize()} setup from EMA stack and MACD alignment.",
        f"Price {entry:.6g}, EMA20 {ema20:.6g}, EMA50 {ema50:.6g}, RSI {rsi:.1f}.",
        f"Latest volume is {volume_ratio:.2f}x the recent 30-bar average.",
    ]


def _ema(values: list[float], period: int) -> float:
    alpha = 2 / (period + 1)
    ema = values[0]
    for value in values[1:]:
        ema = value * alpha + ema * (1 - alpha)
    return float(ema)


def _rsi(values: list[float], period: int) -> float:
    if len(values) <= period:
        return 50.0
    deltas = [values[i] - values[i - 1] for i in range(1, len(values))]
    gains = [max(delta, 0.0) for delta in deltas[-period:]]
    losses = [abs(min(delta, 0.0)) for delta in deltas[-period:]]
    avg_gain = mean(gains) if gains else 0.0
    avg_loss = mean(losses) if losses else 0.0
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return float(100 - (100 / (1 + rs)))


def _macd(values: list[float]) -> tuple[float, float]:
    ema12_series = _ema_series(values, 12)
    ema26_series = _ema_series(values, 26)
    macd_values = [fast - slow for fast, slow in zip(ema12_series, ema26_series)]
    signal_series = _ema_series(macd_values, 9)
    return float(macd_values[-1]), float(signal_series[-1])


def _ema_series(values: list[float], period: int) -> list[float]:
    alpha = 2 / (period + 1)
    result: list[float] = []
    ema = values[0]
    for value in values:
        ema = value * alpha + ema * (1 - alpha)
        result.append(ema)
    return result


def _float_or_none(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _finite(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False
