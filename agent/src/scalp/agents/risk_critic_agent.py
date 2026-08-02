"""Agent 3 — Risk and Critic Agent."""

from __future__ import annotations

import logging
from typing import Any, Dict
from src.scalp.services.net_edge_calculator import NetEdgeCalculator

logger = logging.getLogger(__name__)


class RiskCriticAgent:
    def analyze(self, technical_output: Dict[str, Any], candidate_data: Dict[str, Any], margin_usdt: float, leverage: int) -> Dict[str, Any]:
        if technical_output.get("decision") != "TRADE":
            return {"approved": False, "rejection_reason": "Technical Agent returned WAIT decision."}

        entry_price = float(technical_output.get("entry_price", 0.0))
        stop_loss = float(technical_output.get("stop_loss", 0.0))
        take_profit = float(technical_output.get("take_profit_1", 0.0))
        direction = str(technical_output.get("direction", "LONG"))
        spread_bps = float(candidate_data.get("bid_ask_spread_bps", 3.0))

        net_edge = NetEdgeCalculator.calculate_net_edge(
            entry_price=entry_price,
            take_profit_price=take_profit,
            stop_loss_price=stop_loss,
            direction=direction,
            margin_usdt=margin_usdt,
            leverage=leverage,
            spread_bps=spread_bps,
        )

        approved = net_edge.has_positive_edge

        notional = margin_usdt * leverage
        risk_dist = abs(entry_price - stop_loss) / entry_price if entry_price > 0 else 0.01
        risk_usdt = notional * risk_dist

        # Liquidation distance calculation for isolated margin
        liq_dist = (1.0 / leverage) * 100.0 * 0.9  # approx
        liq_price = entry_price * (1 - (1 / leverage) * 0.9) if direction == "LONG" else entry_price * (1 + (1 / leverage) * 0.9)

        return {
            "approved": approved,
            "position_size_usdt": round(notional, 2),
            "margin_required_usdt": round(margin_usdt, 2),
            "leverage": leverage,
            "risk_amount_usdt": round(risk_usdt, 2),
            "risk_percent": round((risk_usdt / margin_usdt) * 100, 1),
            "net_edge": net_edge.model_dump(),
            "estimated_fees_usdt": net_edge.estimated_entry_fee_usdt + net_edge.estimated_exit_fee_usdt,
            "estimated_slippage_usdt": net_edge.estimated_slippage_usdt,
            "estimated_funding_usdt": net_edge.estimated_funding_cost_usdt,
            "expected_gross_profit_usdt": net_edge.expected_gross_profit_usdt,
            "expected_net_profit_usdt": net_edge.expected_net_profit_usdt,
            "estimated_liquidation_price": round(liq_price, 4),
            "liquidation_distance_percent": round(liq_dist, 1),
            "rejection_reason": "" if approved else "Net expected edge is negative or reward/risk below minimum requirement after transaction costs.",
            "risk_summary": "Risk/Reward verified with positive net edge." if approved else "Insufficient net edge after transaction costs.",
        }
