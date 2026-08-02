"""Scalp trade execution & tracking model."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field
from src.scalp.models.trade_proposal import TradeProposal, NetEdgeBreakdown


class ScalpTrade(BaseModel):
    trade_id: str
    session_id: str
    proposal: TradeProposal
    
    symbol: str
    direction: str  # LONG or SHORT
    leverage: int
    margin_mode: str
    margin_usdt: float
    position_size_usdt: float
    
    # Fill Data
    entry_order_id: str | None = None
    entry_price: float = 0.0
    fill_time: str = ""
    fill_qty: float = 0.0
    
    # Protection Orders
    sl_order_id: str | None = None
    tp_order_id: str | None = None
    stop_loss_price: float = 0.0
    take_profit_price: float = 0.0
    protection_verified: bool = False
    
    # Live Monitoring State
    current_price: float = 0.0
    unrealized_pnl_usdt: float = 0.0
    unrealized_pnl_pct: float = 0.0
    max_favorable_excursion_pct: float = 0.0  # MFE
    max_adverse_excursion_pct: float = 0.0    # MAE
    liquidation_price: float = 0.0
    thesis_status: str = "INTACT"  # INTACT, WEAKENING, INVALIDATED
    
    # Exit Data
    status: str = "OPEN"  # OPEN, CLOSED, CANCELLED, FORCE_CLOSED
    exit_price: float = 0.0
    exit_time: str = ""
    exit_reason: str = ""  # TAKE_PROFIT, STOP_LOSS, EARLY_EXIT, INVALIDATION, SESSION_STOP, EMERGENCY_STOP
    
    realized_pnl_usdt: float = 0.0
    realized_pnl_pct: float = 0.0
    gross_pnl_usdt: float = 0.0
    total_fees_usdt: float = 0.0
    total_funding_usdt: float = 0.0
    total_slippage_usdt: float = 0.0
    net_pnl_usdt: float = 0.0
    
    # Evaluation & Learning
    post_trade_evaluation: dict[str, Any] = Field(default_factory=dict)
    timeline_events: list[dict[str, Any]] = Field(default_factory=list)
