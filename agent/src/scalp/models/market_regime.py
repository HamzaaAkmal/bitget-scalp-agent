"""Market regime classification models."""

from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class MarketRegime(str, Enum):
    STRONG_UPTREND = "STRONG_UPTREND"
    STRONG_DOWNTREND = "STRONG_DOWNTREND"
    WEAK_TREND = "WEAK_TREND"
    RANGE_BOUND = "RANGE_BOUND"
    BREAKOUT_VOLATILITY = "BREAKOUT_VOLATILITY"
    MEAN_REVERTING = "MEAN_REVERTING"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    LOW_VOLATILITY = "LOW_VOLATILITY"
    LOW_LIQUIDITY = "LOW_LIQUIDITY"
    NEWS_DRIVEN = "NEWS_DRIVEN"
    RISK_ON = "RISK_ON"
    RISK_OFF = "RISK_OFF"
    BTC_LED = "BTC_LED"
    ALTCOIN_LED = "ALTCOIN_LED"
    COIN_SPECIFIC = "COIN_SPECIFIC"
    UNCERTAIN = "UNCERTAIN"


class RegimeClassification(BaseModel):
    primary_regime: MarketRegime = MarketRegime.UNCERTAIN
    secondary_regimes: list[MarketRegime] = Field(default_factory=list)
    confidence: float = Field(default=50.0, ge=0.0, le=100.0)
    atr_14: float = 0.0
    adx_14: float = 0.0
    ema_slope_20: float = 0.0
    volume_ratio_30: float = 1.0
    range_compression_ratio: float = 1.0
    btc_correlation: float = 0.0
    open_interest_delta_pct: float = 0.0
    funding_rate: float = 0.0
    orderbook_imbalance: float = 0.0
    trading_permitted: bool = True
    suggested_risk_multiplier: float = 1.0
    reasoning: list[str] = Field(default_factory=list)
