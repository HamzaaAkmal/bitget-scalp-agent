"""Autonomous Profit Manager handling deterministic profit locking, break-even adjustments, and time exits."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from src.scalp.accounting.pnl_ledger import PnLLedger

logger = logging.getLogger(__name__)


class AutonomousProfitManager:
    @staticmethod
    def evaluate_position(
        trade: Dict[str, Any],
        current_price: float,
        policy: Dict[str, Any],
        max_holding_seconds: int = 1800,
    ) -> Dict[str, Any]:
        """Evaluate position for break-even, trailing stop, partial TP, or time exit."""
        direction = str(trade.get("direction", "LONG")).upper()
        entry_price = float(trade.get("entry_price", 0.0))
        fill_qty = float(trade.get("fill_qty", 0.0) or trade.get("margin_usdt", 0.0))
        tp_price = float(trade.get("take_profit_price", 0.0))
        sl_price = float(trade.get("stop_loss_price", 0.0))
        fill_time_str = trade.get("fill_time") or trade.get("created_at", "")

        if entry_price <= 0 or current_price <= 0:
            return {"action": "HOLD", "reason": "Invalid price data"}

        # Calculate exact cost-adjusted break-even price
        # Fee buffer is approx 0.12% round trip
        fee_buffer_pct = 0.0012
        if direction in ("LONG", "BUY"):
            cost_adjusted_breakeven = entry_price * (1.0 + fee_buffer_pct)
            dist_to_tp = (tp_price - entry_price) if tp_price > entry_price else (entry_price * 0.01)
            pct_tp_reached = ((current_price - entry_price) / dist_to_tp) if dist_to_tp > 0 else 0.0
        else:
            cost_adjusted_breakeven = entry_price * (1.0 - fee_buffer_pct)
            dist_to_tp = (entry_price - tp_price) if tp_price < entry_price else (entry_price * 0.01)
            pct_tp_reached = ((entry_price - current_price) / dist_to_tp) if dist_to_tp > 0 else 0.0

        # Check holding duration
        now_ts = time.time()
        fill_ts = now_ts
        if fill_time_str:
            try:
                fill_ts = time.mktime(time.strptime(fill_time_str, "%Y-%m-%dT%H:%M:%SZ"))
            except Exception:
                fill_ts = now_ts

        holding_seconds = int(now_ts - fill_ts)

        # 1. Time-based Exit: If held over max duration with non-negative profit, exit cleanly
        if holding_seconds >= max_holding_seconds:
            unreal = PnLLedger.calculate_unrealized_closable_pnl(
                direction=direction,
                open_qty=fill_qty,
                avg_entry_price=entry_price,
                current_price=current_price,
            )
            if unreal.get("estimated_closable_net_pnl_usdt", -1) >= 0:
                return {
                    "action": "EXIT",
                    "exit_reason": "MAX_HOLDING_TIME_EXPIRED",
                    "details": f"Position reached maximum holding time ({holding_seconds}s >= {max_holding_seconds}s). Closing to free margin.",
                }

        # 2. True Break-Even Protection: Move SL to cost-adjusted break-even if >50% of TP distance achieved
        if pct_tp_reached >= 0.50:
            if direction in ("LONG", "BUY") and sl_price < cost_adjusted_breakeven:
                return {
                    "action": "MOVE_SL",
                    "new_stop_loss": round(cost_adjusted_breakeven, 4),
                    "reason": "MOVE_TO_COST_ADJUSTED_BREAKEVEN",
                    "details": f"50%+ TP progress reached ({pct_tp_reached * 100:.1f}%). Moving SL to cost-adjusted break-even ({cost_adjusted_breakeven:.4g}).",
                }
            elif direction in ("SHORT", "SELL") and (sl_price > cost_adjusted_breakeven or sl_price == 0):
                return {
                    "action": "MOVE_SL",
                    "new_stop_loss": round(cost_adjusted_breakeven, 4),
                    "reason": "MOVE_TO_COST_ADJUSTED_BREAKEVEN",
                    "details": f"50%+ TP progress reached ({pct_tp_reached * 100:.1f}%). Moving SL to cost-adjusted break-even ({cost_adjusted_breakeven:.4g}).",
                }

        return {"action": "HOLD", "reason": "Position operating within normal profit parameters."}
