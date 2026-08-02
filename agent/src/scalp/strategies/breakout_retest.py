"""Breakout and Retest Strategy Template."""

from __future__ import annotations

from typing import Any, Dict
from src.scalp.models.market_regime import MarketRegime

STRATEGY_ID = "breakout_retest_v1"
STRATEGY_NAME = "Breakout & Retest"
STRATEGY_VERSION = "1.0.0"

ELIGIBLE_REGIMES = [
    MarketRegime.BREAKOUT_VOLATILITY,
    MarketRegime.STRONG_UPTREND,
    MarketRegime.STRONG_DOWNTREND,
    MarketRegime.HIGH_VOLATILITY,
]


def analyze(indicators: Dict[str, Any], regime: str) -> Dict[str, Any]:
    close = float(indicators.get("close", 0.0))
    low = float(indicators.get("low", close))
    high = float(indicators.get("high", close))
    resistance = float(indicators.get("resistance_level", close * 1.02))
    support = float(indicators.get("support_level", close * 0.98))
    vol_ratio = float(indicators.get("volume_ratio_30", 1.0))
    atr = float(indicators.get("atr14", close * 0.01))

    # Bullish Breakout & Retest: price broke above resistance, retesting former resistance as support
    bullish_retest = (close >= resistance * 0.998) and (low <= resistance * 1.002) and (vol_ratio >= 1.25)
    # Bearish Breakout & Retest: price broke below support, retesting former support as resistance
    bearish_retest = (close <= support * 1.002) and (high >= support * 0.998) and (vol_ratio >= 1.25)

    if bullish_retest:
        stop_loss = round(resistance - (atr * 1.1), 6)
        risk = close - stop_loss
        tp1 = round(close + (risk * 1.8), 6)
        tp2 = round(close + (risk * 2.8), 6)
        return {
            "strategy_id": STRATEGY_ID,
            "strategy_name": STRATEGY_NAME,
            "direction": "LONG",
            "entry_price": close,
            "stop_loss": stop_loss,
            "take_profit_1": tp1,
            "take_profit_2": tp2,
            "setup_quality_score": 88.0,
            "min_risk_reward": 1.8,
            "invalidation_conditions": ["Price closes back inside prior range", "Volume fails to hold"],
            "supporting_signals": ["Confirmed retest of former resistance level", f"Volume ratio {vol_ratio:.2f}x"],
        }

    if bearish_retest:
        stop_loss = round(support + (atr * 1.1), 6)
        risk = stop_loss - close
        tp1 = round(close - (risk * 1.8), 6)
        tp2 = round(close - (risk * 2.8), 6)
        return {
            "strategy_id": STRATEGY_ID,
            "strategy_name": STRATEGY_NAME,
            "direction": "SHORT",
            "entry_price": close,
            "stop_loss": stop_loss,
            "take_profit_1": tp1,
            "take_profit_2": tp2,
            "setup_quality_score": 88.0,
            "min_risk_reward": 1.8,
            "invalidation_conditions": ["Price re-enters prior support range"],
            "supporting_signals": ["Confirmed retest of broken support level", f"Volume ratio {vol_ratio:.2f}x"],
        }

    return {"strategy_id": STRATEGY_ID, "direction": "WAIT", "setup_quality_score": 0.0}
