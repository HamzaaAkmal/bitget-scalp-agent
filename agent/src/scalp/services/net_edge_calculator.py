"""Net edge calculator taking into account fees, spread, slippage, and funding costs."""

from __future__ import annotations

from typing import Any, Dict
from src.scalp.models.trade_proposal import NetEdgeBreakdown


class NetEdgeCalculator:
    @staticmethod
    def calculate_net_edge(
        entry_price: float,
        take_profit_price: float,
        stop_loss_price: float,
        direction: str,
        margin_usdt: float,
        leverage: int,
        spread_bps: float = 3.0,
        funding_rate: float = 0.0001,
        maker_fee_rate: float = 0.0002,  # 0.02% maker
        taker_fee_rate: float = 0.0006,  # 0.06% taker
        min_reward_risk_ratio: float = 1.0,
    ) -> NetEdgeBreakdown:
        notional_usdt = margin_usdt * leverage
        if entry_price <= 0 or notional_usdt <= 0:
            return NetEdgeBreakdown(has_positive_edge=False)

        qty = notional_usdt / entry_price

        # Expected Gross Profit
        if direction.upper() in ("LONG", "BUY"):
            gross_reward_per_unit = max(0.0, take_profit_price - entry_price)
            risk_per_unit = max(0.0001, entry_price - stop_loss_price)
        else:
            gross_reward_per_unit = max(0.0, entry_price - take_profit_price)
            risk_per_unit = max(0.0001, stop_loss_price - entry_price)

        expected_gross_profit = gross_reward_per_unit * qty
        risk_amount_usdt = risk_per_unit * qty

        # 1. Fees: Limit entry (maker) + Limit/Market exit (taker)
        entry_fee = notional_usdt * maker_fee_rate
        exit_fee = notional_usdt * taker_fee_rate

        # 2. Spread Cost: half spread on entry + half spread on exit
        spread_cost = notional_usdt * (spread_bps / 10000.0)

        # 3. Slippage: estimated 5 bps execution slippage for market orders
        estimated_slippage = notional_usdt * (5.0 / 10000.0)

        # 4. Funding Cost: estimated 1 funding cycle (8h)
        estimated_funding = notional_usdt * abs(funding_rate)

        total_costs = entry_fee + exit_fee + spread_cost + estimated_slippage + estimated_funding
        expected_net_profit = expected_gross_profit - total_costs

        net_risk = risk_amount_usdt + total_costs
        net_rr = (expected_net_profit / net_risk) if net_risk > 0 else 0.0

        has_positive_edge = (expected_net_profit > 0) and (net_rr >= min_reward_risk_ratio) and (total_costs < expected_gross_profit * 0.45)

        return NetEdgeBreakdown(
            expected_gross_profit_usdt=round(expected_gross_profit, 4),
            estimated_entry_fee_usdt=round(entry_fee, 4),
            estimated_exit_fee_usdt=round(exit_fee, 4),
            estimated_slippage_usdt=round(estimated_slippage, 4),
            estimated_spread_cost_usdt=round(spread_cost, 4),
            estimated_funding_cost_usdt=round(estimated_funding, 4),
            expected_net_profit_usdt=round(expected_net_profit, 4),
            expected_net_reward_risk_ratio=round(net_rr, 2),
            has_positive_edge=has_positive_edge,
        )
