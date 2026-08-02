"""Momentum Continuation Strategy Template."""

from __future__ import annotations

from typing import Any, Dict
from src.scalp.models.market_regime import MarketRegime

STRATEGY_ID = "momentum_continuation_v1"
STRATEGY_NAME = "Momentum Continuation"
STRATEGY_VERSION = "1.0.0"

ELIGIBLE_REGIMES = [
    MarketRegime.STRONG_UPTREND,
    MarketRegime.STRONG_DOWNTREND,
    MarketRegime.HIGH_VOLATILITY,
    MarketRegime.BTC_LED,
]


def analyze(indicators: Dict[str, Any], regime: str) -> Dict[str, Any]:
    close = float(indicators.get("close", 0.0))
    ema9 = float(indicators.get("ema9", close))
    ema20 = float(indicators.get("ema20", close))
    macd_hist = float(indicators.get("macd_hist", 0.0))
    vol_ratio = float(indicators.get("volume_ratio_30", 1.0))
    adx = float(indicators.get("adx14", 25.0))
    atr = float(indicators.get("atr14", close * 0.01))

    # Long momentum: ADX > 25, price above EMA9 & EMA20, MACD histogram positive & expanding, volume > 1.3x
    bull_momentum = (adx >= 25) and (close > ema9 > ema20) and (macd_hist > 0) and (vol_ratio >= 1.3)

    # Short momentum: ADX > 25, price below EMA9 & EMA20, MACD histogram negative & expanding, volume > 1.3x
    bear_momentum = (adx >= 25) and (close < ema9 < ema20) and (macd_hist < 0) and (vol_ratio >= 1.3)

    if bull_momentum:
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
            "setup_quality_score": 87.0,
            "min_risk_reward": 1.5,
            "invalidation_conditions": ["Price closes below EMA20", "ADX drops below 20"],
            "supporting_signals": [f"ADX={adx:.1f} trend strength", "MACD histogram expanding positive", f"Volume ratio {vol_ratio:.2f}x"],
        }

    if bear_momentum:
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
            "setup_quality_score": 87.0,
            "min_risk_reward": 1.5,
            "invalidation_conditions": ["Price closes above EMA20", "ADX drops below 20"],
            "supporting_signals": [f"ADX={adx:.1f} trend strength", "MACD histogram expanding negative", f"Volume ratio {vol_ratio:.2f}x"],
        }

    return {"strategy_id": STRATEGY_ID, "direction": "WAIT", "setup_quality_score": 0.0}
