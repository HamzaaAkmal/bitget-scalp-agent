"""Scalp session model."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field
from src.scalp.models.session_policy import SessionPolicy, AutonomyMode


class SessionStats(BaseModel):
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate_pct: float = 0.0
    net_pnl_usdt: float = 0.0
    gross_pnl_usdt: float = 0.0
    total_fees_usdt: float = 0.0
    total_funding_usdt: float = 0.0
    total_slippage_usdt: float = 0.0
    profit_factor: float = 0.0
    max_drawdown_usdt: float = 0.0
    max_drawdown_pct: float = 0.0
    average_win_usdt: float = 0.0
    average_loss_usdt: float = 0.0
    consecutive_losses: int = 0
    current_risk_multiplier: float = 1.0


class ScalpSession(BaseModel):
    session_id: str
    user_mission: str
    policy: SessionPolicy
    status: str = "DRAFT"  # DRAFT, ACTIVE, PAUSED, COMPLETED, STOPPED_TARGET, STOPPED_LOSS, STOPPED_TIMEOUT, EMERGENCY_STOPPED
    
    starting_capital_usdt: float
    current_capital_usdt: float
    session_pnl_usdt: float = 0.0
    session_pnl_pct: float = 0.0
    
    active_position_id: str | None = None
    active_position_ids: list[str] = Field(default_factory=list)
    active_proposal_id: str | None = None
    
    created_at: str
    started_at: str | None = None
    stopped_at: str | None = None
    stop_reason: str | None = None
    
    stats: SessionStats = Field(default_factory=SessionStats)
    recent_candidates: list[str] = Field(default_factory=list)
    recent_regime: str = "UNCERTAIN"
