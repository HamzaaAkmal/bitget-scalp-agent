"""EMA and VWAP Pullback Strategy Template."""

from __future__ import annotations

from typing import Any, Dict
from src.scalp.models.market_regime import MarketRegime

STRATEGY_ID = "ema_vwap_pullback_v1"
STRATEGY_NAME = "EMA & VWAP Pullback"
STRATEGY_VERSION = "1.0.0"

ELIGIBLE_REGIMES = [
    MarketRegime.STRONG_UPTREND,
    MarketRegime.STRONG_DOWNTREND,
    MarketRegime.WEAK_TREND,
    MarketRegime.RISK_ON,
    MarketRegime.RISK_OFF,
]


def analyze(indicators: Dict[str, Any], regime: str) -> Dict[str, Any]:
    close = float(indicators.get("close", 0.0))
    high = float(indicators.get("high", close))
    low = float(indicators.get("low", close))
    ema9 = float(indicators.get("ema9", close))
    ema20 = float(indicators.get("ema20", close))
    ema50 = float(indicators.get("ema50", close))
    vwap = float(indicators.get("vwap", close))
    rsi = float(indicators.get("rsi14", 50.0))
    atr = float(indicators.get("atr14", close * 0.01))

    # Long setup: Uptrend, price pulls back to test EMA20/VWAP area, RSI is not overbought (35-65)
    long_condition = (close > ema50) and (low <= max(ema20, vwap) * 1.002) and (close >= min(ema20, vwap) * 0.998) and (38 <= rsi <= 68)

    # Short setup: Downtrend, price pulls back up to test EMA20/VWAP area, RSI is not oversold (35-65)
    short_condition = (close < ema50) and (high >= min(ema20, vwap) * 0.998) and (close <= max(ema20, vwap) * 1.002) and (32 <= rsi <= 62)

    if long_condition:
        risk_dist = max(atr * 1.5, close * 0.005)
        stop_loss = round(close - risk_dist, 6)
        tp1 = round(close + (risk_dist * 2.0), 6)
        tp2 = round(close + (risk_dist * 3.0), 6)
        return {
            "strategy_id": STRATEGY_ID,
            "strategy_name": STRATEGY_NAME,
            "direction": "LONG",
            "entry_price": close,
            "stop_loss": stop_loss,
            "take_profit_1": tp1,
            "take_profit_2": tp2,
            "setup_quality_score": 85.0,
            "min_risk_reward": 1.5,
            "invalidation_conditions": ["Price closes below EMA50", "VWAP breakdown"],
            "supporting_signals": ["Price pulled back into key EMA20/VWAP confluence", f"RSI={rsi:.1f} healthy"],
        }

    if short_condition:
        risk_dist = max(atr * 1.5, close * 0.005)
        stop_loss = round(close + risk_dist, 6)
        tp1 = round(close - (risk_dist * 2.0), 6)
        tp2 = round(close - (risk_dist * 3.0), 6)
        return {
            "strategy_id": STRATEGY_ID,
            "strategy_name": STRATEGY_NAME,
            "direction": "SHORT",
            "entry_price": close,
            "stop_loss": stop_loss,
            "take_profit_1": tp1,
            "take_profit_2": tp2,
            "setup_quality_score": 85.0,
            "min_risk_reward": 1.5,
            "invalidation_conditions": ["Price closes above EMA50", "VWAP breakout"],
            "supporting_signals": ["Price rally rejected at EMA20/VWAP confluence", f"RSI={rsi:.1f} healthy"],
        }

    return {"strategy_id": STRATEGY_ID, "direction": "WAIT", "setup_quality_score": 0.0}
