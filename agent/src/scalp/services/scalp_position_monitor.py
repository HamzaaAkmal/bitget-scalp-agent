"""Fast 1s deterministic position monitoring loop (no LLM overhead)."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from src.scalp.models.scalp_trade import ScalpTrade
from src.services.bitget_mcp import fetch_ticker

logger = logging.getLogger(__name__)


class ScalpPositionMonitor:
    @staticmethod
    def update_position(trade: ScalpTrade, current_price: float | None = None) -> ScalpTrade:
        """Fast 1s deterministic check update for an active trade."""
        if trade.status != "OPEN":
            return trade

        # Direct live exchange reconciliation from Bitget
        from src.services.bitget_positions import get_positions
        try:
            pos_res = get_positions(category="USDT-FUTURES")
            payload = pos_res.get("structured_content") or pos_res.get("data") or {}
            pos_list = (payload.get("data") or {}).get("list") if isinstance(payload.get("data"), dict) else payload.get("list")
            if not isinstance(pos_list, list):
                pos_list = []

            bitget_pos = None
            for p in pos_list:
                sym = p.get("symbol", "")
                if (sym == trade.symbol or sym.startswith(trade.symbol) or trade.symbol.startswith(sym)) and float(p.get("total") or 0.0) > 0:
                    bitget_pos = p
                    break

            if bitget_pos:
                # Reconcile exact values straight from Bitget Exchange
                trade.leverage = int(bitget_pos.get("leverage") or trade.leverage)
                trade.margin_mode = str(bitget_pos.get("marginMode") or trade.margin_mode).lower()
                trade.entry_price = float(bitget_pos.get("avgPrice") or trade.entry_price)
                trade.current_price = float(bitget_pos.get("markPrice") or current_price or trade.entry_price)
                trade.direction = "LONG" if str(bitget_pos.get("posSide") or "").lower() in ("long", "buy") else "SHORT"
                trade.unrealized_pnl_usdt = round(float(bitget_pos.get("unrealisedPnl") or 0.0), 4)

                if trade.entry_price > 0:
                    if trade.direction == "LONG":
                        pct_change = ((trade.current_price - trade.entry_price) / trade.entry_price) * 100.0
                    else:
                        pct_change = ((trade.entry_price - trade.current_price) / trade.entry_price) * 100.0
                    trade.unrealized_pnl_pct = round(pct_change * trade.leverage, 2)
            else:
                # No open position on Bitget -> Fetch ticker price for fallback estimation
                if current_price is None or current_price <= 0:
                    try:
                        ticker = fetch_ticker(symbol=trade.symbol, category="USDT-FUTURES")
                        current_price = float(ticker.get("lastPrice", trade.entry_price))
                    except Exception:
                        current_price = trade.entry_price
                trade.current_price = current_price
        except Exception as exc:
            logger.warning(f"Live Bitget position query fallback for {trade.symbol}: {exc}")
            if current_price is None or current_price <= 0:
                try:
                    ticker = fetch_ticker(symbol=trade.symbol, category="USDT-FUTURES")
                    current_price = float(ticker.get("lastPrice", trade.entry_price))
                except Exception:
                    current_price = trade.entry_price
            trade.current_price = current_price

        pnl_pct = trade.unrealized_pnl_pct or 0.0
        mfe = trade.max_favorable_excursion_pct or 0.0
        mae = trade.max_adverse_excursion_pct or 0.0

        # MFE / MAE Tracking
        if pnl_pct > mfe:
            trade.max_favorable_excursion_pct = round(pnl_pct, 2)
        if pnl_pct < mae:
            trade.max_adverse_excursion_pct = round(pnl_pct, 2)

        now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        current_px = trade.current_price or 0.0
        sl_px = trade.stop_loss_price or 0.0
        tp_px = trade.take_profit_price or 0.0

        entry_fee = 0.05
        exit_fee = 0.05
        if trade.proposal and hasattr(trade.proposal, "net_edge") and trade.proposal.net_edge:
            entry_fee = getattr(trade.proposal.net_edge, "estimated_entry_fee_usdt", 0.05)
            exit_fee = getattr(trade.proposal.net_edge, "estimated_exit_fee_usdt", 0.05)

        # Check Stop Loss Trigger
        sl_hit = False
        if sl_px > 0 and current_px > 0:
            if trade.direction == "LONG" and current_px <= sl_px:
                sl_hit = True
            elif trade.direction == "SHORT" and current_px >= sl_px:
                sl_hit = True

        if sl_hit:
            trade.status = "CLOSED"
            trade.exit_price = sl_px
            trade.exit_time = now_str
            trade.exit_reason = "STOP_LOSS"
            trade.realized_pnl_usdt = trade.unrealized_pnl_usdt
            trade.realized_pnl_pct = trade.unrealized_pnl_pct
            trade.net_pnl_usdt = trade.unrealized_pnl_usdt - entry_fee - exit_fee
            trade.timeline_events.append({
                "timestamp": now_str,
                "event": "STOP_LOSS_CLOSED",
                "details": f"Stop loss hit @ {sl_px:.4g}. Net PnL: {trade.net_pnl_usdt:.2f} USDT",
            })
            return trade

        # Check Take Profit Trigger
        tp_hit = False
        if tp_px > 0 and current_px > 0:
            if trade.direction == "LONG" and current_px >= tp_px:
                tp_hit = True
            elif trade.direction == "SHORT" and current_px <= tp_px:
                tp_hit = True

        if tp_hit:
            trade.status = "CLOSED"
            trade.exit_price = tp_px
            trade.exit_time = now_str
            trade.exit_reason = "TAKE_PROFIT"
            trade.realized_pnl_usdt = trade.unrealized_pnl_usdt
            trade.realized_pnl_pct = trade.unrealized_pnl_pct
            trade.net_pnl_usdt = trade.unrealized_pnl_usdt - entry_fee - exit_fee
            trade.timeline_events.append({
                "timestamp": now_str,
                "event": "TAKE_PROFIT_CLOSED",
                "details": f"Take profit hit @ {tp_px:.4g}. Net PnL: +{trade.net_pnl_usdt:.2f} USDT",
            })
            return trade

        return trade
