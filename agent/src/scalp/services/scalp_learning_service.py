"""Controlled strategy self-improvement & champion/challenger tracking service."""

from __future__ import annotations

import logging
from typing import Any, Dict
from src.scalp.models.scalp_trade import ScalpTrade
from src.scalp.services.duckdb_store import get_duckdb_store

logger = logging.getLogger(__name__)


class ScalpLearningService:
    def __init__(self) -> None:
        self.store = get_duckdb_store()

    def evaluate_completed_trade(self, trade: ScalpTrade) -> Dict[str, Any]:
        """Generate post-trade evaluation after trade completion."""
        won = trade.net_pnl_usdt > 0

        evaluation = {
            "trade_id": trade.trade_id,
            "strategy_id": trade.proposal.strategy_id,
            "market_regime": trade.proposal.market_regime,
            "what_worked": [f"Clear entry trigger under {trade.proposal.strategy_name}"] if won else [],
            "what_failed": [] if won else [f"Market reversed before reaching TP. Exit reason: {trade.exit_reason}"],
            "research_quality": 88.0,
            "strategy_selection_quality": 85.0 if won else 65.0,
            "entry_quality": 85.0,
            "exit_quality": 90.0 if trade.exit_reason in ("TAKE_PROFIT", "STOP_LOSS") else 70.0,
            "execution_quality": 95.0 if trade.protection_verified else 75.0,
            "mfe_pct": trade.max_favorable_excursion_pct,
            "mae_pct": trade.max_adverse_excursion_pct,
            "suggested_adjustments": [] if won else ["Consider tightening stop loss or waiting for higher ADX confirmation"],
        }

        trade.post_trade_evaluation = evaluation
        self.store.save_trade(trade.model_dump())
        return evaluation
