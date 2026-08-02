"""Fast 1s deterministic position monitoring loop (no LLM overhead)."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from src.scalp.models.scalp_trade import ScalpTrade
from src.services.bitget_mcp import fetch_ticker

logger = logging.getLogger(__name__)


class ScalpPositionMonitor:
    @staticmethod
    def update_position(trade: ScalpTrade, current_price: float | None = None) -> ScalpTrade:
        """Fast 1s deterministic check update for an active trade."""
        if trade.status != "OPEN":
            return trade

        # Fetch price if not provided
        if current_price is None or current_price <= 0:
            try:
                ticker = fetch_ticker(symbol=trade.symbol, category="USDT-FUTURES")
                current_price = float(ticker.get("lastPrice", trade.entry_price))
            except Exception:
                current_price = trade.entry_price

        trade.current_price = current_price
        entry = trade.entry_price

        # Calculate unrealized PnL
        if trade.direction == "LONG":
            pct_change = ((current_price - entry) / entry) * 100.0 if entry > 0 else 0.0
        else:
            pct_change = ((entry - current_price) / entry) * 100.0 if entry > 0 else 0.0

        pnl_pct = pct_change * trade.leverage
        pnl_usdt = trade.margin_usdt * (pnl_pct / 100.0)

        trade.unrealized_pnl_pct = round(pnl_pct, 2)
        trade.unrealized_pnl_usdt = round(pnl_usdt, 4)

        # MFE / MAE Tracking
        if pnl_pct > trade.max_favorable_excursion_pct:
            trade.max_favorable_excursion_pct = round(pnl_pct, 2)
        if pnl_pct < trade.max_adverse_excursion_pct:
            trade.max_adverse_excursion_pct = round(pnl_pct, 2)

        now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        # Check Stop Loss Trigger
        sl_hit = False
        if trade.direction == "LONG" and current_price <= trade.stop_loss_price:
            sl_hit = True
        elif trade.direction == "SHORT" and current_price >= trade.stop_loss_price:
            sl_hit = True

        if sl_hit:
            trade.status = "CLOSED"
            trade.exit_price = trade.stop_loss_price
            trade.exit_time = now_str
            trade.exit_reason = "STOP_LOSS"
            trade.realized_pnl_usdt = trade.unrealized_pnl_usdt
            trade.realized_pnl_pct = trade.unrealized_pnl_pct
            trade.net_pnl_usdt = trade.unrealized_pnl_usdt - trade.proposal.net_edge.estimated_entry_fee_usdt - trade.proposal.net_edge.estimated_exit_fee_usdt
            trade.timeline_events.append({
                "timestamp": now_str,
                "event": "STOP_LOSS_CLOSED",
                "details": f"Stop loss hit @ {trade.stop_loss_price:.4g}. Net PnL: {trade.net_pnl_usdt:.2f} USDT",
            })
            return trade

        # Check Take Profit Trigger
        tp_hit = False
        if trade.direction == "LONG" and current_price >= trade.take_profit_price:
            tp_hit = True
        elif trade.direction == "SHORT" and current_price <= trade.take_profit_price:
            tp_hit = True

        if tp_hit:
            trade.status = "CLOSED"
            trade.exit_price = trade.take_profit_price
            trade.exit_time = now_str
            trade.exit_reason = "TAKE_PROFIT"
            trade.realized_pnl_usdt = trade.unrealized_pnl_usdt
            trade.realized_pnl_pct = trade.unrealized_pnl_pct
            trade.net_pnl_usdt = trade.unrealized_pnl_usdt - trade.proposal.net_edge.estimated_entry_fee_usdt - trade.proposal.net_edge.estimated_exit_fee_usdt
            trade.timeline_events.append({
                "timestamp": now_str,
                "event": "TAKE_PROFIT_CLOSED",
                "details": f"Take profit hit @ {trade.take_profit_price:.4g}. Net PnL: +{trade.net_pnl_usdt:.2f} USDT",
            })
            return trade

        return trade
