"""Funding and Open-Interest Divergence Strategy Template."""

from __future__ import annotations

from typing import Any, Dict
from src.scalp.models.market_regime import MarketRegime

STRATEGY_ID = "funding_oi_divergence_v1"
STRATEGY_NAME = "Funding & OI Divergence"
STRATEGY_VERSION = "1.0.0"

ELIGIBLE_REGIMES = [
    MarketRegime.HIGH_VOLATILITY,
    MarketRegime.MEAN_REVERTING,
    MarketRegime.RANGE_BOUND,
]


def analyze(indicators: Dict[str, Any], regime: str) -> Dict[str, Any]:
    close = float(indicators.get("close", 0.0))
    low = float(indicators.get("low", close))
    high = float(indicators.get("high", close))
    rsi = float(indicators.get("rsi14", 50.0))
    funding = float(indicators.get("funding_rate", 0.0001))
    atr = float(indicators.get("atr14", close * 0.01))

    # Overcrowded longs (extreme positive funding > 0.03%) with price stalling/rejecting -> SHORT squeeze/reversal
    bearish_squeeze = (funding >= 0.0003) and (rsi > 60)
    # Overcrowded shorts (extreme negative funding < -0.03%) with price bouncing -> LONG squeeze/reversal
    bullish_squeeze = (funding <= -0.0003) and (rsi < 40)

    if bullish_squeeze:
        stop_loss = round(low - (atr * 1.0), 6)
        risk = close - stop_loss
        tp1 = round(close + (risk * 2.1), 6)
        tp2 = round(close + (risk * 3.2), 6)
        return {
            "strategy_id": STRATEGY_ID,
            "strategy_name": STRATEGY_NAME,
            "direction": "LONG",
            "entry_price": close,
            "stop_loss": stop_loss,
            "take_profit_1": tp1,
            "take_profit_2": tp2,
            "setup_quality_score": 90.0,
            "min_risk_reward": 2.1,
            "invalidation_conditions": ["Short squeeze fails to materialise", "Funding normalises"],
            "supporting_signals": [f"Negative funding divergence ({funding * 100:.4f}%)", "Overcrowded short positioning"],
        }

    if bearish_squeeze:
        stop_loss = round(high + (atr * 1.0), 6)
        risk = stop_loss - close
        tp1 = round(close - (risk * 2.1), 6)
        tp2 = round(close - (risk * 3.2), 6)
        return {
            "strategy_id": STRATEGY_ID,
            "strategy_name": STRATEGY_NAME,
            "direction": "SHORT",
            "entry_price": close,
            "stop_loss": stop_loss,
            "take_profit_1": tp1,
            "take_profit_2": tp2,
            "setup_quality_score": 90.0,
            "min_risk_reward": 2.1,
            "invalidation_conditions": ["Long squeeze fails to materialise", "Funding normalises"],
            "supporting_signals": [f"High positive funding divergence ({funding * 100:.4f}%)", "Overcrowded long positioning"],
        }

    return {"strategy_id": STRATEGY_ID, "direction": "WAIT", "setup_quality_score": 0.0}
