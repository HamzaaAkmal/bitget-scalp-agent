"""Range Mean Reversion Strategy Template."""

from __future__ import annotations

from typing import Any, Dict
from src.scalp.models.market_regime import MarketRegime

STRATEGY_ID = "range_mean_reversion_v1"
STRATEGY_NAME = "Range Mean Reversion"
STRATEGY_VERSION = "1.0.0"

ELIGIBLE_REGIMES = [
    MarketRegime.RANGE_BOUND,
    MarketRegime.MEAN_REVERTING,
    MarketRegime.LOW_VOLATILITY,
]


def analyze(indicators: Dict[str, Any], regime: str) -> Dict[str, Any]:
    close = float(indicators.get("close", 0.0))
    bb_upper = float(indicators.get("bollinger_upper", close * 1.02))
    bb_middle = float(indicators.get("bollinger_middle", close))
    bb_lower = float(indicators.get("bollinger_lower", close * 0.98))
    rsi = float(indicators.get("rsi14", 50.0))
    adx = float(indicators.get("adx14", 25.0))
    atr = float(indicators.get("atr14", close * 0.01))

    # Range long: low ADX (<22), price touching/below lower Bollinger Band, RSI oversold (<35)
    range_long = (adx < 22) and (close <= bb_lower * 1.002) and (rsi < 35)
    # Range short: low ADX (<22), price touching/above upper Bollinger Band, RSI overbought (>65)
    range_short = (adx < 22) and (close >= bb_upper * 0.998) and (rsi > 65)

    if range_long:
        stop_loss = round(bb_lower - (atr * 1.2), 6)
        risk = close - stop_loss
        tp1 = round(bb_middle, 6)
        tp2 = round(bb_upper, 6)
        return {
            "strategy_id": STRATEGY_ID,
            "strategy_name": STRATEGY_NAME,
            "direction": "LONG",
            "entry_price": close,
            "stop_loss": stop_loss,
            "take_profit_1": tp1,
            "take_profit_2": tp2,
            "setup_quality_score": 83.0,
            "min_risk_reward": 1.5,
            "invalidation_conditions": ["Bollinger band expansion breakout"],
            "supporting_signals": ["Price at lower Bollinger Band in range regime", f"RSI={rsi:.1f} oversold", f"ADX={adx:.1f} low trend"],
        }

    if range_short:
        stop_loss = round(bb_upper + (atr * 1.2), 6)
        risk = stop_loss - close
        tp1 = round(bb_middle, 6)
        tp2 = round(bb_lower, 6)
        return {
            "strategy_id": STRATEGY_ID,
            "strategy_name": STRATEGY_NAME,
            "direction": "SHORT",
            "entry_price": close,
            "stop_loss": stop_loss,
            "take_profit_1": tp1,
            "take_profit_2": tp2,
            "setup_quality_score": 83.0,
            "min_risk_reward": 1.5,
            "invalidation_conditions": ["Bollinger band expansion breakout"],
            "supporting_signals": ["Price at upper Bollinger Band in range regime", f"RSI={rsi:.1f} overbought", f"ADX={adx:.1f} low trend"],
        }

    return {"strategy_id": STRATEGY_ID, "direction": "WAIT", "setup_quality_score": 0.0}
