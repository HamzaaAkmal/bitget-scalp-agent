"""Exact fill-based PnL Ledger accounting engine."""

from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class PnLLedger:
    @staticmethod
    def calculate_realized_pnl(
        direction: str,
        entry_qty: float,
        avg_entry_price: float,
        exit_qty: float,
        avg_exit_price: float,
        entry_fees_usdt: float = 0.0,
        exit_fees_usdt: float = 0.0,
        funding_paid_usdt: float = 0.0,
        funding_received_usdt: float = 0.0,
        other_charges_usdt: float = 0.0,
    ) -> Dict[str, Any]:
        """Calculate exact realized PnL from filled quantities and prices."""
        qty = min(entry_qty, exit_qty)
        if qty <= 0 or avg_entry_price <= 0 or avg_exit_price <= 0:
            return {
                "gross_realized_pnl_usdt": 0.0,
                "net_realized_pnl_usdt": 0.0,
                "total_fees_usdt": 0.0,
                "net_funding_usdt": 0.0,
            }

        is_long = direction.upper() in ("LONG", "BUY")
        if is_long:
            gross_pnl = qty * (avg_exit_price - avg_entry_price)
        else:
            gross_pnl = qty * (avg_entry_price - avg_exit_price)

        total_fees = entry_fees_usdt + exit_fees_usdt
        net_funding = funding_received_usdt - funding_paid_usdt
        net_pnl = gross_pnl - total_fees + net_funding - other_charges_usdt

        return {
            "gross_realized_pnl_usdt": round(gross_pnl, 4),
            "net_realized_pnl_usdt": round(net_pnl, 4),
            "total_fees_usdt": round(total_fees, 4),
            "net_funding_usdt": round(net_funding, 4),
        }

    @staticmethod
    def calculate_unrealized_closable_pnl(
        direction: str,
        open_qty: float,
        avg_entry_price: float,
        current_price: float,
        leverage: int = 1,
        entry_fees_usdt: float = 0.0,
        estimated_exit_fee_rate: float = 0.0006,  # 0.06% Taker
        accrued_funding_usdt: float = 0.0,
        estimated_slippage_bps: float = 2.0,
    ) -> Dict[str, Any]:
        """Calculate estimated closable net unrealized PnL."""
        if open_qty <= 0 or avg_entry_price <= 0 or current_price <= 0:
            return {
                "gross_unrealized_pnl_usdt": 0.0,
                "estimated_closable_net_pnl_usdt": 0.0,
                "unrealized_pnl_pct": 0.0,
            }

        is_long = direction.upper() in ("LONG", "BUY")
        if is_long:
            gross_unrealized = open_qty * (current_price - avg_entry_price)
            pct_change = ((current_price - avg_entry_price) / avg_entry_price) * 100.0
        else:
            gross_unrealized = open_qty * (avg_entry_price - current_price)
            pct_change = ((avg_entry_price - current_price) / avg_entry_price) * 100.0

        pnl_pct = pct_change * leverage
        notional = open_qty * current_price
        est_exit_fee = notional * estimated_exit_fee_rate
        est_slippage = notional * (estimated_slippage_bps / 10000.0)

        closable_net = gross_unrealized - entry_fees_usdt - est_exit_fee - accrued_funding_usdt - est_slippage

        return {
            "gross_unrealized_pnl_usdt": round(gross_unrealized, 4),
            "estimated_closable_net_pnl_usdt": round(closable_net, 4),
            "unrealized_pnl_pct": round(pnl_pct, 2),
            "estimated_exit_fee_usdt": round(est_exit_fee, 4),
            "estimated_slippage_usdt": round(est_slippage, 4),
        }
