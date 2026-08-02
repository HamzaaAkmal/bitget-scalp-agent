"""Session policy definitions and natural-language extraction models."""

from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class AutonomyMode(str, Enum):
    COPILOT = "copilot"
    GUARDED_AUTOPILOT = "guarded_autopilot"
    FULL_AUTONOMOUS = "full_autonomous"


class TargetClassification(str, Enum):
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"
    EXTREMELY_AGGRESSIVE = "extremely_aggressive"


class PolicyWarning(BaseModel):
    level: str = "warning"  # warning, critical, caution
    code: str
    message: str
    impact: str


class SessionPolicy(BaseModel):
    autonomy_mode: AutonomyMode = AutonomyMode.COPILOT
    allocated_capital: float = Field(default=20.0, ge=1.0)
    target_profit: float = Field(default=5.0, gt=0.0)
    target_final_balance: float = Field(default=25.0, gt=0.0)
    target_classification: TargetClassification = TargetClassification.MODERATE
    maximum_session_loss: float = Field(default=2.0, gt=0.0)
    maximum_daily_loss: float = Field(default=5.0, gt=0.0)
    maximum_duration_minutes: int = Field(default=180, ge=15, le=1440)
    
    allowed_symbols: list[str] = Field(default_factory=lambda: ["BTCUSDT", "ETHUSDT", "SOLUSDT"])
    excluded_symbols: list[str] = Field(default_factory=list)
    market_type: str = "USDT-FUTURES"
    margin_mode: str = "isolated"
    maximum_leverage: int = Field(default=3, ge=1, le=5)
    hard_max_leverage: int = 5
    maximum_margin_per_trade: float = Field(default=10.0, gt=0.0)
    risk_per_trade_usdt: float = Field(default=0.50, gt=0.0)
    risk_per_trade_percent: float = Field(default=2.5, gt=0.0)
    
    maximum_concurrent_positions: int = Field(default=1, ge=1, le=3)
    maximum_consecutive_losses: int = Field(default=3, ge=1, le=10)
    minimum_setup_quality_score: float = Field(default=80.0, ge=0.0, le=100.0)
    minimum_historical_edge: bool = True
    minimum_risk_reward: float = Field(default=1.5, ge=1.0)
    
    allowed_strategy_templates: list[str] = Field(
        default_factory=lambda: [
            "ema_vwap_pullback_v1",
            "breakout_retest_v1",
            "liquidity_sweep_reversal_v1",
            "momentum_continuation_v1",
            "range_mean_reversion_v1",
            "volume_expansion_v1",
            "funding_oi_divergence_v1",
        ]
    )
    preferred_timeframes: list[str] = Field(default_factory=lambda: ["5m", "15m"])
    trade_cooldown_seconds: int = Field(default=600, ge=60)
    allowed_session_hours: list[int] = Field(default_factory=lambda: list(range(24)))
    news_research_requirement: bool = True
    
    automatic_early_exit_permission: bool = True
    partial_profit_permission: bool = True
    trailing_stop_permission: bool = False
    
    exchange_native_sl_required: bool = True
    exchange_native_tp_required: bool = True
    exa_critical_event_check_required: bool = True
    
    warnings: list[PolicyWarning] = Field(default_factory=list)


def create_default_policy() -> SessionPolicy:
    return SessionPolicy()
