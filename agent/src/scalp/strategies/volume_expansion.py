"""Volume Expansion Strategy Template."""

from __future__ import annotations

from typing import Any, Dict
from src.scalp.models.market_regime import MarketRegime

STRATEGY_ID = "volume_expansion_v1"
STRATEGY_NAME = "Volume Expansion Setup"
STRATEGY_VERSION = "1.0.0"

ELIGIBLE_REGIMES = [
    MarketRegime.BREAKOUT_VOLATILITY,
    MarketRegime.HIGH_VOLATILITY,
    MarketRegime.COIN_SPECIFIC,
    MarketRegime.NEWS_DRIVEN,
]


def analyze(indicators: Dict[str, Any], regime: str) -> Dict[str, Any]:
    close = float(indicators.get("close", 0.0))
    low = float(indicators.get("low", close))
    high = float(indicators.get("high", close))
    vol_ratio = float(indicators.get("volume_ratio_30", 1.0))
    ema20 = float(indicators.get("ema20", close))
    atr = float(indicators.get("atr14", close * 0.01))

    # Bullish Volume Expansion: Volume >= 2.5x 30-bar mean, bullish candle
    bullish_vol = (vol_ratio >= 2.5) and (close > ema20)

    # Bearish Volume Expansion: Volume >= 2.5x 30-bar mean, bearish candle
    bearish_vol = (vol_ratio >= 2.5) and (close < ema20)

    if bullish_vol:
        stop_loss = round(low - (atr * 0.8), 6)
        risk = close - stop_loss
        tp1 = round(close + (risk * 2.0), 6)
        tp2 = round(close + (risk * 3.2), 6)
        return {
            "strategy_id": STRATEGY_ID,
            "strategy_name": STRATEGY_NAME,
            "direction": "LONG",
            "entry_price": close,
            "stop_loss": stop_loss,
            "take_profit_1": tp1,
            "take_profit_2": tp2,
            "setup_quality_score": 89.0,
            "min_risk_reward": 2.0,
            "invalidation_conditions": ["Immediate volume collapse", "Candle low breach"],
            "supporting_signals": [f"Volume spike {vol_ratio:.2f}x average", "Strong buying pressure"],
        }

    if bearish_vol:
        stop_loss = round(high + (atr * 0.8), 6)
        risk = stop_loss - close
        tp1 = round(close - (risk * 2.0), 6)
        tp2 = round(close - (risk * 3.2), 6)
        return {
            "strategy_id": STRATEGY_ID,
            "strategy_name": STRATEGY_NAME,
            "direction": "SHORT",
            "entry_price": close,
            "stop_loss": stop_loss,
            "take_profit_1": tp1,
            "take_profit_2": tp2,
            "setup_quality_score": 89.0,
            "min_risk_reward": 2.0,
            "invalidation_conditions": ["Immediate volume collapse", "Candle high breach"],
            "supporting_signals": [f"Volume spike {vol_ratio:.2f}x average", "Strong selling pressure"],
        }

    return {"strategy_id": STRATEGY_ID, "direction": "WAIT", "setup_quality_score": 0.0}
