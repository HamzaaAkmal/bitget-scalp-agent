"""Quantitative market regime classifier."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from src.scalp.models.market_regime import MarketRegime, RegimeClassification

logger = logging.getLogger(__name__)


class MarketRegimeClassifier:
    @staticmethod
    def classify(indicators: Dict[str, Any], symbol: str = "BTCUSDT", ticker: Dict[str, Any] | None = None) -> RegimeClassification:
        close = float(indicators.get("close", 0.0))
        ema9 = float(indicators.get("ema9", close))
        ema20 = float(indicators.get("ema20", close))
        ema50 = float(indicators.get("ema50", close))
        ema200 = float(indicators.get("ema200", close))
        vwap = float(indicators.get("vwap", close))
        rsi = float(indicators.get("rsi14", 50.0))
        adx = float(indicators.get("adx14", 25.0))
        vol_ratio = float(indicators.get("volume_ratio_30", 1.0))
        atr = float(indicators.get("atr14", close * 0.01))

        # Check trend strength
        ema_aligned_bull = (close > ema9 > ema20 > ema50) and (close > vwap)
        ema_aligned_bear = (close < ema9 < ema20 < ema50) and (close < vwap)

        primary = MarketRegime.UNCERTAIN
        secondaries: List[MarketRegime] = []
        confidence = 60.0
        risk_mult = 1.0
        permitted = True
        reasons: List[str] = []

        if adx >= 28 and ema_aligned_bull:
            primary = MarketRegime.STRONG_UPTREND
            secondaries.append(MarketRegime.HIGH_VOLATILITY if vol_ratio > 1.5 else MarketRegime.RISK_ON)
            confidence = min(95.0, 70.0 + (adx - 28) * 0.8)
            risk_mult = 1.0
            reasons.append(f"ADX={adx:.1f} indicates strong trend; price ({close:.4g}) above EMA stack & VWAP.")
        elif adx >= 28 and ema_aligned_bear:
            primary = MarketRegime.STRONG_DOWNTREND
            secondaries.append(MarketRegime.HIGH_VOLATILITY if vol_ratio > 1.5 else MarketRegime.RISK_OFF)
            confidence = min(95.0, 70.0 + (adx - 28) * 0.8)
            risk_mult = 1.0
            reasons.append(f"ADX={adx:.1f} indicates strong downtrend; price ({close:.4g}) below EMA stack & VWAP.")
        elif adx < 20:
            primary = MarketRegime.RANGE_BOUND
            secondaries.append(MarketRegime.MEAN_REVERTING)
            confidence = min(90.0, 65.0 + (20.0 - adx) * 1.2)
            risk_mult = 0.85
            reasons.append(f"ADX={adx:.1f} < 20 signals range-bound / mean-reverting market conditions.")
        elif vol_ratio > 2.2:
            primary = MarketRegime.BREAKOUT_VOLATILITY
            secondaries.append(MarketRegime.HIGH_VOLATILITY)
            confidence = 82.0
            risk_mult = 0.9
            reasons.append(f"Volume surge {vol_ratio:.2f}x 30-bar mean signals potential breakout volatility.")
        elif 20 <= adx < 28:
            primary = MarketRegime.WEAK_TREND
            secondaries.append(MarketRegime.RANGE_BOUND)
            confidence = 65.0
            risk_mult = 0.9
            reasons.append(f"ADX={adx:.1f} indicates weak or developing trend.")
        else:
            primary = MarketRegime.UNCERTAIN
            confidence = 50.0
            risk_mult = 0.75
            reasons.append("Market conditions are mixed with no dominant directional trend.")

        # Special risk gates
        if vol_ratio < 0.3:
            secondaries.append(MarketRegime.LOW_LIQUIDITY)
            risk_mult *= 0.5
            reasons.append("Low liquidity detected (volume <30% of average). Risk scaled down.")

        return RegimeClassification(
            primary_regime=primary,
            secondary_regimes=secondaries,
            confidence=round(confidence, 1),
            atr_14=round(atr, 6),
            adx_14=round(adx, 2),
            ema_slope_20=round(((ema9 - ema20) / ema20) * 100, 4) if ema20 > 0 else 0.0,
            volume_ratio_30=round(vol_ratio, 2),
            range_compression_ratio=1.0,
            btc_correlation=0.85 if "BTC" not in symbol else 1.0,
            trading_permitted=permitted,
            suggested_risk_multiplier=round(risk_mult, 2),
            reasoning=reasons,
        )
