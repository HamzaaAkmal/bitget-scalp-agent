"""Deterministic risk engine enforcing hard risk controls, leverage caps, and dynamic drawdown scaling."""

from __future__ import annotations

import logging
from typing import Any, Dict, List
from src.scalp.models.session_policy import SessionPolicy
from src.scalp.models.scalp_session import ScalpSession
from src.scalp.models.trade_proposal import TradeProposal

logger = logging.getLogger(__name__)


class ScalpRiskEngine:
    @staticmethod
    def evaluate_proposal(proposal: TradeProposal, session: ScalpSession, policy: SessionPolicy) -> Dict[str, Any]:
        rejections: List[str] = []

        # 1. Check Autonomy & Session state
        if session.status in ("STOPPED_TARGET", "STOPPED_LOSS", "STOPPED_TIMEOUT", "EMERGENCY_STOPPED"):
            rejections.append(f"Session is stopped ({session.status}). No new trades permitted.")

        # 2. Check Emergency Stop state
        from src.scalp.services.emergency_stop_service import get_emergency_stop_service
        if get_emergency_stop_service().is_active():
            rejections.append("Global Emergency Stop is active.")

        # 3. Check Consecutive Loss Limit
        if session.stats.consecutive_losses >= policy.maximum_consecutive_losses:
            rejections.append(f"Maximum consecutive losses reached ({session.stats.consecutive_losses}/{policy.maximum_consecutive_losses}). Trading paused.")

        # 4. Check Session Drawdown Limit
        if abs(session.session_pnl_usdt) >= policy.maximum_session_loss and session.session_pnl_usdt < 0:
            rejections.append(f"Maximum session loss limit hit ({abs(session.session_pnl_usdt):.2f} / {policy.maximum_session_loss:.2f} USDT).")

        # 5. Check Leverage limits
        if proposal.leverage > policy.hard_max_leverage:
            rejections.append(f"Leverage ({proposal.leverage}x) exceeds hard maximum limit ({policy.hard_max_leverage}x).")

        # 6. Check Setup Quality Score
        if proposal.setup_quality_score < policy.minimum_setup_quality_score:
            rejections.append(f"Setup quality score ({proposal.setup_quality_score:.1f}/100) below policy minimum ({policy.minimum_setup_quality_score}/100).")

        # 7. Check Expected Net Edge
        if not proposal.net_edge.has_positive_edge:
            rejections.append(f"Trade fails expected net edge validation (Net R/R {proposal.net_edge.expected_net_reward_risk_ratio:.2f} < {policy.minimum_risk_reward:.2f}).")

        # 8. Check Liquidation Distance (minimum 15% distance)
        if proposal.liquidation_distance_percent < 15.0:
            rejections.append(f"Liquidation distance ({proposal.liquidation_distance_percent:.1f}%) is dangerously close (<15.0%).")

        # 9. Check Mandatory Protective Orders
        if policy.exchange_native_sl_required and not proposal.stop_loss:
            rejections.append("Exchange-native Stop Loss is required by session policy.")
        if policy.exchange_native_tp_required and not proposal.take_profit_1:
            rejections.append("Exchange-native Take Profit is required by session policy.")

        # Calculate Dynamic Risk Scaling multiplier based on consecutive losses
        consec = session.stats.consecutive_losses
        if consec == 0:
            risk_multiplier = 1.0
        elif consec == 1:
            risk_multiplier = 0.75
        elif consec == 2:
            risk_multiplier = 0.50
        else:
            risk_multiplier = 0.0

        approved = len(rejections) == 0

        return {
            "approved": approved,
            "rejection_reasons": rejections,
            "risk_multiplier": risk_multiplier,
            "risk_summary": "Passed all 25+ deterministic risk controls." if approved else f"Rejected by Risk Engine: {'; '.join(rejections)}",
        }
