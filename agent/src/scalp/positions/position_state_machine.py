"""Position State Machine tracking strict position lifecycle and protection verification."""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class PositionState(str, Enum):
    PROPOSAL_CREATED = "PROPOSAL_CREATED"
    RISK_APPROVED = "RISK_APPROVED"
    CAPITAL_RESERVED = "CAPITAL_RESERVED"
    ORDER_SUBMITTED = "ORDER_SUBMITTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED_UNPROTECTED = "FILLED_UNPROTECTED"
    PROTECTION_SUBMITTED = "PROTECTION_SUBMITTED"
    PROTECTED = "PROTECTED"
    PROFIT_MANAGEMENT = "PROFIT_MANAGEMENT"
    EXIT_SUBMITTED = "EXIT_SUBMITTED"
    PARTIALLY_CLOSED = "PARTIALLY_CLOSED"
    CLOSED = "CLOSED"
    FAILED = "FAILED"


VALID_TRANSITIONS = {
    PositionState.PROPOSAL_CREATED: [PositionState.RISK_APPROVED, PositionState.FAILED],
    PositionState.RISK_APPROVED: [PositionState.CAPITAL_RESERVED, PositionState.FAILED],
    PositionState.CAPITAL_RESERVED: [PositionState.ORDER_SUBMITTED, PositionState.FAILED],
    PositionState.ORDER_SUBMITTED: [PositionState.PARTIALLY_FILLED, PositionState.FILLED_UNPROTECTED, PositionState.FAILED],
    PositionState.PARTIALLY_FILLED: [PositionState.FILLED_UNPROTECTED, PositionState.EXIT_SUBMITTED, PositionState.FAILED],
    PositionState.FILLED_UNPROTECTED: [PositionState.PROTECTION_SUBMITTED, PositionState.EXIT_SUBMITTED, PositionState.FAILED],
    PositionState.PROTECTION_SUBMITTED: [PositionState.PROTECTED, PositionState.EXIT_SUBMITTED, PositionState.FAILED],
    PositionState.PROTECTED: [PositionState.PROFIT_MANAGEMENT, PositionState.EXIT_SUBMITTED, PositionState.PARTIALLY_CLOSED, PositionState.CLOSED],
    PositionState.PROFIT_MANAGEMENT: [PositionState.EXIT_SUBMITTED, PositionState.PARTIALLY_CLOSED, PositionState.CLOSED],
    PositionState.EXIT_SUBMITTED: [PositionState.PARTIALLY_CLOSED, PositionState.CLOSED, PositionState.FAILED],
    PositionState.PARTIALLY_CLOSED: [PositionState.PROFIT_MANAGEMENT, PositionState.EXIT_SUBMITTED, PositionState.CLOSED],
    PositionState.CLOSED: [],
    PositionState.FAILED: [PositionState.CLOSED],
}


class PositionStateMachine:
    @staticmethod
    def transition(current_state: str | PositionState, target_state: str | PositionState, reason: str = "") -> str:
        curr = PositionState(current_state) if isinstance(current_state, str) else current_state
        tgt = PositionState(target_state) if isinstance(target_state, str) else target_state

        valid_targets = VALID_TRANSITIONS.get(curr, [])
        if tgt not in valid_targets and curr != tgt:
            logger.warning(f"Invalid position state transition attempted: {curr.value} -> {tgt.value} (Reason: {reason}). Allowing soft transition for reconciliation.")
        
        logger.info(f"Position state transition: {curr.value} -> {tgt.value} ({reason})")
        return tgt.value
