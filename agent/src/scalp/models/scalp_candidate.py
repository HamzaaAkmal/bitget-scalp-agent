"""Market candidate and opportunity scoring models."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field
from src.scalp.models.market_regime import RegimeClassification


class ScoreComponents(BaseModel):
    liquidity_quality: float = 0.0      # 25% weight
    volume_anomaly: float = 0.0         # 20% weight
    spread_quality: float = 0.0         # 15% weight
    volatility_suitability: float = 0.0 # 15% weight
    open_interest_change: float = 0.0   # 10% weight
    market_structure_quality: float = 0.0 # 10% weight
    catalyst_context: float = 0.0       # 5% weight
    raw_metrics: dict[str, Any] = Field(default_factory=dict)


class ScalpCandidate(BaseModel):
    symbol: str
    coin_name: str = ""
    coin_icon: str = ""
    coingecko_id: str = ""
    market_cap_rank: int | None = None
    price_usdt: float = 0.0
    volume_24h_usdt: float = 0.0
    price_change_24h_pct: float = 0.0
    bid_ask_spread_bps: float = 0.0
    funding_rate: float = 0.0
    open_interest_usdt: float = 0.0
    
    opportunity_score: float = 0.0
    score_breakdown: ScoreComponents = Field(default_factory=ScoreComponents)
    regime: RegimeClassification = Field(default_factory=RegimeClassification)
    eligible_strategies: list[str] = Field(default_factory=list)
    
    funnel_stage: str = "INITIAL" # Funnel stages: ALL, LIQUIDITY, VOLUME_VOL, TOP_20, REGIME_STRUCT, TOP_5, TECH_SCORE, TOP_2, FINAL
    passed_filters: bool = True
    rejection_reason: str | None = None
    
    research_summary: str = ""
    event_veto: bool = False
