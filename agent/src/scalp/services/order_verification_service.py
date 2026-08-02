"""Independent order and position state verification service."""

from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class OrderVerificationService:
    @staticmethod
    def verify_order_and_position(symbol: str, order_id: str | None = None) -> Dict[str, Any]:
        try:
            from src.services.bitget_positions import get_positions, get_open_orders
            positions_res = get_positions(category="USDT-FUTURES", symbol=symbol)
            orders_res = get_open_orders(category="USDT-FUTURES", symbol=symbol)

            positions = positions_res.get("positions", [])
            orders = orders_res.get("orders", [])

            active_pos = None
            for p in positions:
                if float(p.get("total", 0.0)) > 0 or float(p.get("available", 0.0)) > 0:
                    active_pos = p
                    break

            return {
                "verified": True,
                "has_active_position": active_pos is not None,
                "position_data": active_pos,
                "open_orders_count": len(orders),
                "open_orders": orders,
            }
        except Exception as exc:
            logger.warning(f"Order verification exception for {symbol}: {exc}")
            return {
                "verified": False,
                "has_active_position": False,
                "error": str(exc),
            }
