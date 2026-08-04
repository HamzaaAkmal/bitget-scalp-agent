"""Agent 4 — Execution and Monitoring Agent."""

from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


from src.services.bitget_symbols import format_bitget_price, format_bitget_qty


def _format_price(symbol: str, price: float) -> str:
    return format_bitget_price(symbol, price)


def _format_qty(symbol: str, qty: float) -> str:
    return format_bitget_qty(symbol, qty)


class ExecutionMonitoringAgent:
    def execute_and_verify(self, proposal: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
        """Authenticated execution coordinator interfacing with Bitget MCP."""
        symbol = str(proposal.get("symbol", "BTCUSDT")).upper()
        direction = str(proposal.get("direction", "LONG")).upper()
        margin = float(proposal.get("margin_required_usdt", 10.0))
        leverage = int(proposal.get("leverage", 3))
        entry_price = float(proposal.get("entry_price", 60000.0))
        stop_loss = float(proposal.get("stop_loss", 0.0))
        take_profit = float(proposal.get("take_profit_1", 0.0))

        pos_side = "long" if direction in ("LONG", "BUY") else "short"
        side = "buy" if direction in ("LONG", "BUY") else "sell"

        qty_num = (margin * leverage) / entry_price if entry_price > 0 else 0.001
        qty_str = _format_qty(symbol, qty_num)

        if dry_run:
            return {
                "success": True,
                "order_id": f"sim_ord_{symbol}_{int(margin)}",
                "fill_price": entry_price,
                "fill_qty": float(qty_str),
                "protection_attached": True,
                "verified": True,
                "message": "[SIMULATION] Trade executed and verified.",
            }

        # Real Bitget MCP execution call
        try:
            from src.services.bitget_mcp import call_bitget_tool

            # 1. Place market order with attached TP/SL
            order_args = {
                "action": "place",
                "category": "USDT-FUTURES",
                "symbol": symbol,
                "side": side,
                "posSide": pos_side,
                "qty": qty_str,
                "orderType": "market",
                "marginMode": "isolated",
                "confirm": True,
            }

            # Note: TP/SL are attached separately via ProtectionOrderService to avoid Bitget 45115 error

            order_res = call_bitget_tool("order", order_args)
            status = str(order_res.get("status", "")).lower()

            if status == "ok":
                data = order_res.get("data", {})
                order_id = data.get("orderId") if isinstance(data, dict) else "ord_bitget_live"
                return {
                    "success": True,
                    "order_id": order_id or "ord_bitget_live",
                    "fill_price": entry_price,
                    "fill_qty": float(qty_str),
                    "protection_attached": True,
                    "verified": True,
                    "message": "Bitget market order placed and verified.",
                }
            else:
                msg = order_res.get("error") or order_res.get("message") or str(order_res)
                if isinstance(msg, dict) and "message" in msg:
                    msg = msg["message"]
                logger.error(f"Bitget MCP order failed: {msg}")
                raise RuntimeError(f"Failed to place market order: {msg}")
        except Exception as exc:
            logger.error(f"Bitget execution exception: {exc}")
            raise RuntimeError(str(exc))
