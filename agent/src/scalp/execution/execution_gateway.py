"""Unified Execution Gateway providing idempotent order execution, margin reservation, and protection attachment."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from src.scalp.execution.idempotency_service import get_idempotency_service
from src.scalp.execution.capital_reservation_service import get_capital_reservation_service
from src.scalp.positions.position_state_machine import PositionStateMachine, PositionState
from src.scalp.services.protection_order_service import ProtectionOrderService
from src.scalp.services.duckdb_store import get_duckdb_store

logger = logging.getLogger(__name__)


class ExecutionGateway:
    def __init__(self) -> None:
        self.idempotency = get_idempotency_service()
        self.reservation = get_capital_reservation_service()
        self.store = get_duckdb_store()

    def execute_proposal(
        self,
        session_id: str,
        proposal: Dict[str, Any],
        available_capital_usdt: float,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        proposal_id = proposal.get("proposal_id") or f"prop_{int(time.time())}"
        idem_key = f"exec_{proposal_id}"

        # 1. Idempotency Check
        cached_resp = self.idempotency.get_idempotent_response(idem_key)
        if cached_resp:
            logger.info(f"Returning cached idempotent response for proposal {proposal_id}")
            return cached_resp

        # 2. Capital Reservation Check
        symbol = proposal.get("symbol", "BTCUSDT")
        margin_needed = float(proposal.get("margin_required_usdt") or proposal.get("margin_usdt") or 5.0)
        res_check = self.reservation.reserve_capital(session_id, proposal_id, margin_needed, available_capital_usdt)
        if not res_check["success"]:
            resp = {"status": "error", "error": res_check["reason"]}
            return self.idempotency.record_idempotent_response(idem_key, "EXECUTE_PROPOSAL", resp)

        # 3. Call Execution Agent
        from src.scalp.agents.execution_monitoring_agent import ExecutionMonitoringAgent
        exec_agent = ExecutionMonitoringAgent()
        exec_res = exec_agent.execute_and_verify(proposal, dry_run=dry_run)

        if not exec_res.get("success"):
            self.reservation.release_reservation(session_id, margin_needed)
            resp = {"status": "error", "error": exec_res.get("error", "Execution agent failed")}
            return self.idempotency.record_idempotent_response(idem_key, "EXECUTE_PROPOSAL", resp)

        fill_price = float(exec_res.get("fill_price") or proposal.get("entry_price", 0.0))
        fill_qty = float(exec_res.get("fill_qty") or 0.001)

        # 4. Attach Exchange-Native Protection
        tp = float(proposal.get("take_profit_1") or proposal.get("take_profit", 0.0))
        sl = float(proposal.get("stop_loss", 0.0))
        direction = str(proposal.get("direction", "LONG")).upper()

        prot_res = ProtectionOrderService.attach_native_protection(
            symbol=symbol,
            pos_side=direction,
            take_profit=tp,
            stop_loss=sl,
            qty=fill_qty,
            dry_run=dry_run,
        )

        pos_state = PositionState.PROTECTED if prot_res.get("verified") else PositionState.FILLED_UNPROTECTED

        trade_id = f"trd_{int(time.time())}_{symbol.lower()}"
        now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        trade_data = {
            "trade_id": trade_id,
            "session_id": session_id,
            "proposal": proposal,
            "symbol": symbol,
            "direction": direction,
            "leverage": int(proposal.get("leverage", 1)),
            "margin_mode": proposal.get("margin_mode", "isolated"),
            "margin_usdt": margin_needed,
            "position_size_usdt": float(proposal.get("position_size_usdt", margin_needed)),
            "entry_order_id": exec_res.get("order_id"),
            "entry_price": fill_price,
            "fill_time": now_str,
            "fill_qty": fill_qty,
            "remaining_qty": fill_qty,
            "sl_order_id": prot_res.get("sl_order_id"),
            "tp_order_id": prot_res.get("tp_order_id"),
            "stop_loss_price": sl,
            "take_profit_price": tp,
            "protection_verified": prot_res.get("verified", False),
            "current_price": fill_price,
            "status": "OPEN",
            "position_state": pos_state,
            "net_pnl_usdt": 0.0,
            "unrealized_pnl_usdt": 0.0,
            "timeline_events": [
                {"timestamp": now_str, "event": "ORDER_FILLED", "details": f"Entered {direction} on {symbol} @ {fill_price:.4g}"},
                {"timestamp": now_str, "event": "PROTECTION_ATTACHED", "details": f"Native SL: {sl:.4g}, TP: {tp:.4g} (Verified: {prot_res.get('verified')})"},
            ],
        }

        self.store.save_trade(trade_data)
        result = {"status": "ok", "trade": trade_data}
        return self.idempotency.record_idempotent_response(idem_key, "EXECUTE_PROPOSAL", result)

    def close_position(self, trade_data: Dict[str, Any], reason: str = "MANUAL_CLOSE", dry_run: bool = False) -> Dict[str, Any]:
        trade_id = trade_data["trade_id"]
        idem_key = f"close_{trade_id}"

        cached_resp = self.idempotency.get_idempotent_response(idem_key)
        if cached_resp:
            logger.info(f"Returning cached idempotent close response for trade {trade_id}")
            return cached_resp

        symbol = trade_data["symbol"]
        direction = trade_data["direction"]
        close_side = "sell" if direction.upper() in ("LONG", "BUY") else "buy"
        pos_side = "long" if direction.upper() in ("LONG", "BUY") else "short"
        fill_qty = trade_data.get("fill_qty") or 0.001

        now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        if dry_run:
            exit_price = float(trade_data.get("current_price") or trade_data.get("entry_price", 0.0))
        else:
            try:
                from src.services.bitget_mcp import call_bitget_tool
                order_res = call_bitget_tool(
                    "order",
                    {
                        "action": "place",
                        "category": "USDT-FUTURES",
                        "symbol": symbol,
                        "side": close_side,
                        "posSide": pos_side,
                        "qty": str(fill_qty),
                        "orderType": "market",
                        "confirm": True,
                    },
                )
                status = str(order_res.get("status", "")).lower()
                if status != "ok":
                    msg = order_res.get("error") or order_res.get("message") or str(order_res)
                    msg_str = msg["message"] if isinstance(msg, dict) and "message" in msg else str(msg)
                    
                    if "25227" in msg_str or "No position available to close" in msg_str:
                        logger.warning(f"Position {symbol} is already closed on the exchange. Marking as closed locally.")
                    else:
                        raise RuntimeError(f"Bitget MCP order failed: {msg_str}")
                exit_price = float(trade_data.get("current_price") or trade_data.get("entry_price", 0.0))
            except Exception as exc:
                logger.error(f"Close market order exception for {symbol}: {exc}")
                resp = {"status": "error", "error": f"Failed to close position on exchange: {exc}"}
                return self.idempotency.record_idempotent_response(idem_key, "CLOSE_POSITION", resp)

        # Calculate exact Net PnL via PnLLedger
        from src.scalp.accounting.pnl_ledger import PnLLedger
        pnl_res = PnLLedger.calculate_realized_pnl(
            direction=direction,
            entry_qty=fill_qty,
            avg_entry_price=float(trade_data.get("entry_price", 0.0)),
            exit_qty=fill_qty,
            avg_exit_price=exit_price,
            entry_fees_usdt=float(trade_data.get("margin_usdt", 0.0)) * 0.0006,
            exit_fees_usdt=float(trade_data.get("margin_usdt", 0.0)) * 0.0006,
        )

        trade_data["status"] = "CLOSED"
        trade_data["position_state"] = PositionState.CLOSED
        trade_data["exit_price"] = exit_price
        trade_data["exit_time"] = now_str
        trade_data["exit_reason"] = reason
        trade_data["net_pnl_usdt"] = pnl_res["net_realized_pnl_usdt"]
        trade_data["gross_pnl_usdt"] = pnl_res["gross_realized_pnl_usdt"]
        trade_data["total_fees_usdt"] = pnl_res["total_fees_usdt"]
        trade_data["timeline_events"].append({
            "timestamp": now_str,
            "event": "TRADE_CLOSED",
            "details": f"Closed via {reason} @ {exit_price:.4g}. Net PnL: {pnl_res['net_realized_pnl_usdt']:.2f} USDT",
        })

        self.store.save_trade(trade_data)

        # Release capital reservation
        session_id = trade_data["session_id"]
        margin_used = float(trade_data.get("margin_usdt", 0.0))
        self.reservation.release_reservation(session_id, margin_used)

        resp = {"status": "ok", "trade": trade_data}
        return self.idempotency.record_idempotent_response(idem_key, "CLOSE_POSITION", resp)


_execution_gateway_instance: ExecutionGateway | None = None


def get_execution_gateway() -> ExecutionGateway:
    global _execution_gateway_instance
    if _execution_gateway_instance is None:
        _execution_gateway_instance = ExecutionGateway()
    return _execution_gateway_instance
