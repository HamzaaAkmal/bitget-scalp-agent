"""Scalp execution service connecting TradeProposals to Bitget MCP / Simulation."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict

from src.scalp.models.scalp_trade import ScalpTrade
from src.scalp.models.trade_proposal import TradeProposal
from src.scalp.agents.execution_monitoring_agent import ExecutionMonitoringAgent
from src.scalp.services.protection_order_service import ProtectionOrderService
from src.scalp.services.duckdb_store import get_duckdb_store

logger = logging.getLogger(__name__)


class ScalpExecutionService:
    def __init__(self) -> None:
        self.exec_agent = ExecutionMonitoringAgent()
        self.store = get_duckdb_store()

    def execute_proposal(self, session_id: str, proposal: TradeProposal, dry_run: bool = False) -> ScalpTrade:
        trade_id = f"trd_{int(time.time())}_{proposal.symbol.lower()}"
        fill_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        # 1. Coordinate order execution
        exec_res = self.exec_agent.execute_and_verify(proposal.model_dump(), dry_run=dry_run)

        fill_price = exec_res.get("fill_price") or proposal.entry_price
        fill_qty = exec_res.get("fill_qty") or ((proposal.margin_required_usdt * proposal.leverage) / fill_price)

        # 2. Attach Exchange-Native Protection
        prot_res = ProtectionOrderService.attach_native_protection(
            symbol=proposal.symbol,
            pos_side=proposal.direction,
            take_profit=proposal.take_profit_1,
            stop_loss=proposal.stop_loss,
            qty=fill_qty,
            dry_run=dry_run,
        )

        trade = ScalpTrade(
            trade_id=trade_id,
            session_id=session_id,
            proposal=proposal,
            symbol=proposal.symbol,
            direction=proposal.direction,
            leverage=proposal.leverage,
            margin_mode=proposal.margin_mode,
            margin_usdt=proposal.margin_required_usdt,
            position_size_usdt=proposal.position_size_usdt,
            entry_order_id=exec_res.get("order_id"),
            entry_price=fill_price,
            fill_time=fill_time,
            fill_qty=fill_qty,
            sl_order_id=prot_res.get("sl_order_id"),
            tp_order_id=prot_res.get("tp_order_id"),
            stop_loss_price=proposal.stop_loss,
            take_profit_price=proposal.take_profit_1,
            protection_verified=prot_res.get("verified", False),
            current_price=fill_price,
            liquidation_price=proposal.estimated_liquidation_price,
            status="OPEN",
            timeline_events=[
                {
                    "timestamp": fill_time,
                    "event": "ORDER_FILLED",
                    "details": f"Entered {proposal.direction} on {proposal.symbol} @ {fill_price:.4g}",
                },
                {
                    "timestamp": fill_time,
                    "event": "PROTECTION_ATTACHED",
                    "details": f"Native SL: {proposal.stop_loss:.4g}, TP: {proposal.take_profit_1:.4g}",
                },
            ],
        )

        # Save to DuckDB
        self.store.save_trade(trade.model_dump())
        return trade


_execution_service_instance: ScalpExecutionService | None = None


def get_execution_service() -> ScalpExecutionService:
    global _execution_service_instance
    if _execution_service_instance is None:
        _execution_service_instance = ScalpExecutionService()
    return _execution_service_instance
