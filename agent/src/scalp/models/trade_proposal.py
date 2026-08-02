"""Trade proposal model."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class NetEdgeBreakdown(BaseModel):
    expected_gross_profit_usdt: float = 0.0
    estimated_entry_fee_usdt: float = 0.0
    estimated_exit_fee_usdt: float = 0.0
    estimated_slippage_usdt: float = 0.0
    estimated_spread_cost_usdt: float = 0.0
    estimated_funding_cost_usdt: float = 0.0
    expected_net_profit_usdt: float = 0.0
    expected_net_reward_risk_ratio: float = 0.0
    has_positive_edge: bool = False


class TradeProposal(BaseModel):
    proposal_id: str
    symbol: str
    coin_name: str = ""
    coin_icon: str = ""
    strategy_id: str
    strategy_name: str
    market_regime: str
    direction: str  # LONG, SHORT, WAIT
    timeframe: str = "5m"
    
    entry_type: str = "LIMIT"  # LIMIT or MARKET
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float | None = None
    
    leverage: int = 3
    margin_mode: str = "isolated"
    position_size_usdt: float
    margin_required_usdt: float
    risk_amount_usdt: float
    risk_percent: float
    
    estimated_liquidation_price: float
    liquidation_distance_percent: float
    expected_duration_minutes: int = 30
    
    setup_quality_score: float = Field(default=80.0, ge=0.0, le=100.0)
    net_edge: NetEdgeBreakdown = Field(default_factory=NetEdgeBreakdown)
    
    invalidation_conditions: list[str] = Field(default_factory=list)
    supporting_signals: list[str] = Field(default_factory=list)
    conflicting_signals: list[str] = Field(default_factory=list)
    
    market_intelligence_approved: bool = True
    technical_strategy_approved: bool = True
    risk_critic_approved: bool = True
    risk_engine_approved: bool = True
    
    status: str = "PROPOSED" # PROPOSED, APPROVED, REJECTED, EXECUTED, EXPIRED
    rejection_reason: str | None = None
    why_this_trade: dict[str, Any] = Field(default_factory=dict)
    created_at: str = ""
