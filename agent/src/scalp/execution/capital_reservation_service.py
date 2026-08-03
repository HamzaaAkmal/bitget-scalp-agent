"""Capital reservation service for atomic margin reservation and allocation."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict

logger = logging.getLogger(__name__)


class CapitalReservationService:
    def __init__(self) -> None:
        self._reservations: Dict[str, float] = {}

    def reserve_capital(self, session_id: str, proposal_id: str, amount_usdt: float, available_capital_usdt: float) -> Dict[str, Any]:
        current_reserved = self._reservations.get(session_id, 0.0)
        remaining_free = available_capital_usdt - current_reserved

        if amount_usdt > remaining_free:
            return {
                "success": False,
                "reason": f"Insufficient unreserved session capital (Requested: {amount_usdt:.2f} USDT, Unreserved: {remaining_free:.2f} USDT).",
                "reserved_amount": current_reserved,
            }

        self._reservations[session_id] = current_reserved + amount_usdt
        logger.info(f"Reserved {amount_usdt:.2f} USDT for session {session_id} (Proposal {proposal_id}). Total reserved: {self._reservations[session_id]:.2f} USDT.")

        return {
            "success": True,
            "reserved_amount": amount_usdt,
            "total_session_reserved": self._reservations[session_id],
        }

    def release_reservation(self, session_id: str, amount_usdt: float) -> None:
        current_reserved = self._reservations.get(session_id, 0.0)
        new_reserved = max(0.0, current_reserved - amount_usdt)
        self._reservations[session_id] = new_reserved
        logger.info(f"Released {amount_usdt:.2f} USDT reservation for session {session_id}. Remaining reserved: {new_reserved:.2f} USDT.")


_capital_reservation_service_instance: CapitalReservationService | None = None


def get_capital_reservation_service() -> CapitalReservationService:
    global _capital_reservation_service_instance
    if _capital_reservation_service_instance is None:
        _capital_reservation_service_instance = CapitalReservationService()
    return _capital_reservation_service_instance
