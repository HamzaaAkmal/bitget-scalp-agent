"""Technical indicator calculation service for multi-timeframe futures analysis."""

from __future__ import annotations

import math
from statistics import mean
from typing import Any, Dict, List


class TechnicalIndicatorService:
    @staticmethod
    def compute_all_indicators(candles: List[Dict[str, Any]], ticker: Dict[str, Any] | None = None) -> Dict[str, Any]:
        if not candles or len(candles) < 20:
            last_price = float(ticker.get("lastPrice", 0.0)) if ticker else 0.0
            return {
                "close": last_price,
                "ema9": last_price,
                "ema20": last_price,
                "ema50": last_price,
                "ema200": last_price,
                "vwap": last_price,
                "rsi14": 50.0,
                "macd": 0.0,
                "macd_signal": 0.0,
                "macd_hist": 0.0,
                "atr14": last_price * 0.01,
                "adx14": 25.0,
                "bollinger_upper": last_price * 1.02,
                "bollinger_middle": last_price,
                "bollinger_lower": last_price * 0.98,
                "volume_ratio_30": 1.0,
                "support_level": last_price * 0.98,
                "resistance_level": last_price * 1.02,
            }

        closes = [float(c["close"]) for c in candles if TechnicalIndicatorService._finite(c.get("close"))]
        highs = [float(c["high"]) for c in candles if TechnicalIndicatorService._finite(c.get("high"))]
        lows = [float(c["low"]) for c in candles if TechnicalIndicatorService._finite(c.get("low"))]
        volumes = [float(c.get("volume", 0.0)) for c in candles if TechnicalIndicatorService._finite(c.get("close"))]

        current_close = closes[-1]
        ema9 = TechnicalIndicatorService._ema(closes, 9)
        ema20 = TechnicalIndicatorService._ema(closes, 20)
        ema50 = TechnicalIndicatorService._ema(closes, min(50, len(closes)))
        ema200 = TechnicalIndicatorService._ema(closes, min(200, len(closes)))

        vwap = TechnicalIndicatorService._vwap(candles)
        rsi14 = TechnicalIndicatorService._rsi(closes, 14)
        macd, macd_sig = TechnicalIndicatorService._macd(closes)
        macd_hist = macd - macd_sig

        atr14 = TechnicalIndicatorService._atr(highs, lows, closes, 14)
        adx14 = TechnicalIndicatorService._adx(highs, lows, closes, 14)
        bb_upper, bb_mid, bb_lower = TechnicalIndicatorService._bollinger_bands(closes, 20, 2.0)

        vol_mean30 = mean(volumes[-30:]) if len(volumes) >= 30 and mean(volumes[-30:]) > 0 else 1.0
        vol_ratio = (volumes[-1] / vol_mean30) if vol_mean30 > 0 else 1.0

        support = min(lows[-20:])
        resistance = max(highs[-20:])

        return {
            "close": current_close,
            "high": highs[-1],
            "low": lows[-1],
            "ema9": round(ema9, 6),
            "ema20": round(ema20, 6),
            "ema50": round(ema50, 6),
            "ema200": round(ema200, 6),
            "vwap": round(vwap, 6),
            "rsi14": round(rsi14, 2),
            "macd": round(macd, 6),
            "macd_signal": round(macd_sig, 6),
            "macd_hist": round(macd_hist, 6),
            "atr14": round(atr14, 6),
            "adx14": round(adx14, 2),
            "bollinger_upper": round(bb_upper, 6),
            "bollinger_middle": round(bb_mid, 6),
            "bollinger_lower": round(bb_lower, 6),
            "volume_ratio_30": round(vol_ratio, 2),
            "support_level": round(support, 6),
            "resistance_level": round(resistance, 6),
        }

    @staticmethod
    def _finite(val: Any) -> bool:
        try:
            return math.isfinite(float(val))
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _ema(values: List[float], period: int) -> float:
        if len(values) < period:
            return values[-1] if values else 0.0
        alpha = 2.0 / (period + 1.0)
        ema = values[0]
        for v in values[1:]:
            ema = v * alpha + ema * (1.0 - alpha)
        return float(ema)

    @staticmethod
    def _vwap(candles: List[Dict[str, Any]]) -> float:
        cum_vol = 0.0
        cum_pv = 0.0
        for c in candles[-50:]:
            high = float(c.get("high", 0.0))
            low = float(c.get("low", 0.0))
            close = float(c.get("close", 0.0))
            vol = float(c.get("volume", 0.0))
            typical_price = (high + low + close) / 3.0
            cum_pv += typical_price * vol
            cum_vol += vol
        return (cum_pv / cum_vol) if cum_vol > 0 else (candles[-1]["close"] if candles else 0.0)

    @staticmethod
    def _rsi(values: List[float], period: int = 14) -> float:
        if len(values) <= period:
            return 50.0
        deltas = [values[i] - values[i - 1] for i in range(1, len(values))]
        recent_deltas = deltas[-period:]
        gains = [max(d, 0.0) for d in recent_deltas]
        losses = [abs(min(d, 0.0)) for d in recent_deltas]
        avg_gain = mean(gains) if gains else 0.0
        avg_loss = mean(losses) if losses else 0.0
        if avg_loss == 0.0:
            return 100.0
        rs = avg_gain / avg_loss
        return float(100.0 - (100.0 / (1.0 + rs)))

    @staticmethod
    def _macd(values: List[float]) -> tuple[float, float]:
        if len(values) < 26:
            return 0.0, 0.0
        ema12 = TechnicalIndicatorService._ema_series(values, 12)
        ema26 = TechnicalIndicatorService._ema_series(values, 26)
        macd_series = [f - s for f, s in zip(ema12, ema26)]
        signal_series = TechnicalIndicatorService._ema_series(macd_series, 9)
        return float(macd_series[-1]), float(signal_series[-1])

    @staticmethod
    def _ema_series(values: List[float], period: int) -> List[float]:
        alpha = 2.0 / (period + 1.0)
        res = [values[0]]
        for v in values[1:]:
            res.append(v * alpha + res[-1] * (1.0 - alpha))
        return res

    @staticmethod
    def _atr(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> float:
        if len(closes) < 2:
            return (highs[-1] - lows[-1]) if highs else 0.0
        tr_list = []
        for i in range(1, len(closes)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
            tr_list.append(tr)
        return mean(tr_list[-period:]) if tr_list else 0.0

    @staticmethod
    def _adx(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> float:
        if len(closes) < period + 1:
            return 25.0
        dx_list = []
        for i in range(1, len(closes)):
            up_move = highs[i] - highs[i - 1]
            down_move = lows[i - 1] - lows[i]
            pos_dm = up_move if (up_move > down_move and up_move > 0) else 0.0
            neg_dm = down_move if (down_move > up_move and down_move > 0) else 0.0
            tr = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
            if tr > 0:
                pos_di = (pos_dm / tr) * 100
                neg_di = (neg_dm / tr) * 100
                di_sum = pos_di + neg_di
                if di_sum > 0:
                    dx_list.append((abs(pos_di - neg_di) / di_sum) * 100)
        return mean(dx_list[-period:]) if dx_list else 25.0

    @staticmethod
    def _bollinger_bands(values: List[float], period: int = 20, std_dev_mult: float = 2.0) -> tuple[float, float, float]:
        if len(values) < period:
            last = values[-1] if values else 0.0
            return last * 1.02, last, last * 0.98
        sub = values[-period:]
        mid = mean(sub)
        variance = sum((x - mid) ** 2 for x in sub) / period
        std_dev = math.sqrt(variance)
        return mid + (std_dev * std_dev_mult), mid, mid - (std_dev * std_dev_mult)
