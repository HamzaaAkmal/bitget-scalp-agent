"""Liquidity Sweep Reversal Strategy Template."""

from __future__ import annotations

from typing import Any, Dict
from src.scalp.models.market_regime import MarketRegime

STRATEGY_ID = "liquidity_sweep_reversal_v1"
STRATEGY_NAME = "Liquidity Sweep Reversal"
STRATEGY_VERSION = "1.0.0"

ELIGIBLE_REGIMES = [
    MarketRegime.RANGE_BOUND,
    MarketRegime.MEAN_REVERTING,
    MarketRegime.HIGH_VOLATILITY,
]


def analyze(indicators: Dict[str, Any], regime: str) -> Dict[str, Any]:
    close = float(indicators.get("close", 0.0))
    low = float(indicators.get("low", close))
    high = float(indicators.get("high", close))
    support = float(indicators.get("support_level", close * 0.98))
    resistance = float(indicators.get("resistance_level", close * 1.02))
    rsi = float(indicators.get("rsi14", 50.0))
    atr = float(indicators.get("atr14", close * 0.01))

    # Bullish Sweep: wick below key support, but candle close reclaims support level (Oversold RSI)
    bullish_sweep = (low < support) and (close > support) and (rsi < 42)

    # Bearish Sweep: wick above key resistance, but candle close rejects back below resistance (Overbought RSI)
    bearish_sweep = (high > resistance) and (close < resistance) and (rsi > 58)

    if bullish_sweep:
        stop_loss = round(low - (atr * 0.5), 6)
        risk = close - stop_loss
        tp1 = round(close + (risk * 2.0), 6)
        tp2 = round(close + (risk * 3.0), 6)
        return {
            "strategy_id": STRATEGY_ID,
            "strategy_name": STRATEGY_NAME,
            "direction": "LONG",
            "entry_price": close,
            "stop_loss": stop_loss,
            "take_profit_1": tp1,
            "take_profit_2": tp2,
            "setup_quality_score": 86.0,
            "min_risk_reward": 2.0,
            "invalidation_conditions": ["Price breaks below low of sweep candle"],
            "supporting_signals": ["Liquidity sweep of key low with sharp reclamation", f"RSI={rsi:.1f} oversold bounce"],
        }

    if bearish_sweep:
        stop_loss = round(high + (atr * 0.5), 6)
        risk = stop_loss - close
        tp1 = round(close - (risk * 2.0), 6)
        tp2 = round(close - (risk * 3.0), 6)
        return {
            "strategy_id": STRATEGY_ID,
            "strategy_name": STRATEGY_NAME,
            "direction": "SHORT",
            "entry_price": close,
            "stop_loss": stop_loss,
            "take_profit_1": tp1,
            "take_profit_2": tp2,
            "setup_quality_score": 86.0,
            "min_risk_reward": 2.0,
            "invalidation_conditions": ["Price breaks above high of sweep candle"],
            "supporting_signals": ["Liquidity sweep of key high with rejection back inside range", f"RSI={rsi:.1f} overbought rejection"],
        }

    return {"strategy_id": STRATEGY_ID, "direction": "WAIT", "setup_quality_score": 0.0}
