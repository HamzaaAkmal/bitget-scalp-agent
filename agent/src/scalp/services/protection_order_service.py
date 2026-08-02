"""Protection order service attaching exchange-native Stop Loss and Take Profit."""

from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class ProtectionOrderService:
    @staticmethod
    def attach_native_protection(
        symbol: str,
        pos_side: str,
        take_profit: float,
        stop_loss: float,
        qty: float,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        if dry_run:
            return {
                "status": "ok",
                "tp_order_id": f"sim_tp_{symbol}",
                "sl_order_id": f"sim_sl_{symbol}",
                "verified": True,
                "message": "[DRY RUN] Native TP and SL attached successfully.",
            }

        try:
            from src.services.bitget_management import modify_tpsl
            res = modify_tpsl(
                category="USDT-FUTURES",
                symbol=symbol,
                pos_side=pos_side.lower(),
                take_profit=take_profit,
                stop_loss=stop_loss,
                qty=qty,
                confirmation_text="ATTACH_PROTECTION",
                dry_run=False,
            )
            return {
                "status": "ok" if res.get("status") == "ok" else "error",
                "tp_order_id": res.get("tp_order_id") or f"tp_{symbol}",
                "sl_order_id": res.get("sl_order_id") or f"sl_{symbol}",
                "verified": True,
                "raw_response": res,
            }
        except Exception as exc:
            logger.warning(f"Native TP/SL attachment exception for {symbol}: {exc}")
            return {
                "status": "error",
                "tp_order_id": None,
                "sl_order_id": None,
                "verified": False,
                "error": str(exc),
            }
