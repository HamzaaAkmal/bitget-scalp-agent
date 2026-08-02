"""Emergency Stop service operating independently of frontend connection."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict

logger = logging.getLogger(__name__)


class EmergencyStopService:
    def __init__(self) -> None:
        self._emergency_active: bool = False
        self._activated_at: str | None = None
        self._reason: str | None = None

    def is_active(self) -> bool:
        return self._emergency_active

    def get_status(self) -> Dict[str, Any]:
        return {
            "emergency_active": self._emergency_active,
            "activated_at": self._activated_at,
            "reason": self._reason,
        }

    def activate(self, reason: str = "User initiated Emergency Stop") -> Dict[str, Any]:
        self._emergency_active = True
        self._activated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self._reason = reason

        logger.critical(f"🚨 EMERGENCY STOP ACTIVATED: {reason} 🚨")

        # 1. Stop all active sessions
        from src.scalp.services.scalp_session_manager import get_session_manager
        sessions = get_session_manager().list_active_sessions()
        for session_id in sessions:
            get_session_manager().stop_session(session_id, reason="EMERGENCY_STOP")

        # 2. Cancel all pending Bitget orders
        cancelled_orders = 0
        try:
            from src.services.bitget_positions import get_open_orders
            from src.services.bitget_execution import cancel_order
            orders = get_open_orders(category="USDT-FUTURES")
            for ord in orders.get("orders", []):
                oid = ord.get("orderId")
                sym = ord.get("symbol")
                if oid:
                    cancel_order(order_id=oid, category="USDT-FUTURES", symbol=sym)
                    cancelled_orders += 1
        except Exception as exc:
            logger.warning(f"Emergency order cancellation exception: {exc}")

        # 3. Log Audit Record
        from src.scalp.services.duckdb_store import get_duckdb_store
        get_duckdb_store().save_audit(
            audit_id=f"aud_emerg_{int(time.time())}",
            session_id="GLOBAL",
            action_type="EMERGENCY_STOP",
            actor="USER",
            data={"reason": reason, "cancelled_orders": cancelled_orders},
            timestamp=self._activated_at,
        )

        return {
            "status": "ok",
            "emergency_active": True,
            "cancelled_orders": cancelled_orders,
            "message": f"Emergency Stop executed. All sessions stopped and {cancelled_orders} open orders cancelled.",
        }

    def reset(self) -> Dict[str, Any]:
        self._emergency_active = False
        self._activated_at = None
        self._reason = None
        return {"status": "ok", "emergency_active": False, "message": "Emergency Stop reset."}


_emergency_service_instance: EmergencyStopService | None = None


def get_emergency_stop_service() -> EmergencyStopService:
    global _emergency_service_instance
    if _emergency_service_instance is None:
        _emergency_service_instance = EmergencyStopService()
    return _emergency_service_instance
