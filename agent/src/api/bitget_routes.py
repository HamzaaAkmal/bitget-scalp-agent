"""Bitget HTTP routes for the Web UI."""

from __future__ import annotations

import asyncio
import secrets
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from src.services.bitget_account import get_account_overview, get_connection_status
from src.services.bitget_execution import cancel_order, close_position, execute_confirmed_trade
from src.services.bitget_management import (
    build_trailing_stop_proposal,
    get_alerts,
    get_order_fills,
    get_risk_dashboard,
    get_strategy_orders,
    modify_tpsl,
    partial_close_position,
    scale_position,
)
from src.services.bitget_mcp import fetch_candles, normalize_category, normalize_interval, normalize_symbol
from src.services.bitget_positions import get_open_orders, get_positions
from src.services.bitget_symbols import search_symbols
from src.services.risk_engine import build_risk_plan
from src.services.signal_engine import build_market_signal, parse_trade_intent
from src.services.trade_confirmation import create_trade_proposal


class TradeProposalRequest(BaseModel):
    """Request body for a Bitget trade proposal."""

    prompt: str = Field(..., min_length=3, max_length=4000)
    symbol: str | None = Field(default=None, max_length=32)
    category: str | None = Field(default=None, max_length=32)


class ExecuteProposalRequest(BaseModel):
    """Request body for executing a confirmed Bitget trade proposal."""

    confirmation_text: str = Field(..., min_length=2, max_length=200)
    dry_run: bool = False


class CancelOrderRequest(BaseModel):
    order_id: str = Field(..., min_length=1, max_length=128)
    symbol: str | None = Field(default=None, max_length=32)
    category: str = "USDT-FUTURES"


class ClosePositionRequest(BaseModel):
    symbol: str = Field(..., min_length=3, max_length=32)
    category: str = "USDT-FUTURES"
    pos_side: str | None = Field(default=None, max_length=16)
    confirmation_text: str = Field(..., min_length=2, max_length=200)
    dry_run: bool = False


class ModifyTpslRequest(BaseModel):
    symbol: str = Field(..., min_length=3, max_length=32)
    category: str = "USDT-FUTURES"
    pos_side: str = Field("long", max_length=16)
    take_profit: float | None = None
    stop_loss: float | None = None
    qty: float | None = Field(default=None, gt=0)
    strategy_order_id: str | None = Field(default=None, max_length=128)
    confirmation_text: str = Field(..., min_length=2, max_length=200)
    dry_run: bool = False


class PartialCloseRequest(BaseModel):
    symbol: str = Field(..., min_length=3, max_length=32)
    category: str = "USDT-FUTURES"
    pos_side: str = Field("long", max_length=16)
    qty: float = Field(..., gt=0)
    confirmation_text: str = Field(..., min_length=2, max_length=200)
    dry_run: bool = False


class ScalePositionRequest(BaseModel):
    symbol: str = Field(..., min_length=3, max_length=32)
    category: str = "USDT-FUTURES"
    side: str = Field(..., max_length=16)
    qty: float = Field(..., gt=0)
    pos_side: str | None = Field(default=None, max_length=16)
    confirmation_text: str = Field(..., min_length=2, max_length=200)
    dry_run: bool = False


class TrailingStopProposalRequest(BaseModel):
    symbol: str = Field(..., min_length=3, max_length=32)
    category: str = "USDT-FUTURES"
    pos_side: str = Field("long", max_length=16)
    callback_percent: float = Field(1.0, ge=0.1, le=25)


def register_bitget_routes(app: FastAPI) -> None:
    """Mount Bitget routes."""
    import sys

    host = sys.modules.get("api_server") or sys.modules.get("agent.api_server")
    if host is None:
        raise RuntimeError("register_bitget_routes: api_server module not in sys.modules")

    require_auth = host.require_auth

    async def _authorize_ws(websocket: WebSocket) -> bool:
        configured = host._configured_api_key()
        if not configured:
            return True
        ticket = websocket.query_params.get("ticket")
        if ticket and host._consume_sse_ticket(ticket):
            return True
        token = websocket.query_params.get("api_key") or websocket.query_params.get("token")
        if token and secrets.compare_digest(token, configured):
            return True
        await websocket.close(code=1008)
        return False

    @app.get("/bitget/status", dependencies=[Depends(require_auth)])
    async def bitget_status() -> dict[str, Any]:
        return get_connection_status()

    @app.get("/bitget/symbols/search", dependencies=[Depends(require_auth)])
    async def bitget_symbol_search(
        query: str = Query(..., min_length=1, max_length=64),
        category: str | None = Query(default=None, max_length=32),
        limit: int = Query(default=10, ge=1, le=25),
    ) -> dict[str, Any]:
        return search_symbols(query, category=category, limit=limit)

    @app.get("/bitget/market/candles", dependencies=[Depends(require_auth)])
    async def bitget_candles(
        symbol: str = Query("BTCUSDT", min_length=3, max_length=32),
        category: str = Query("USDT-FUTURES", max_length=32),
        interval: str = Query("5m", max_length=8),
        lookback: int = Query(300, ge=20, le=1500),
    ) -> dict[str, Any]:
        try:
            bars = fetch_candles(
                symbol=normalize_symbol(symbol),
                category=normalize_category(category),
                interval=normalize_interval(interval),
                lookback=lookback,
            )
        except Exception as exc:  # noqa: BLE001 - route boundary
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return {
            "status": "ok",
            "provider": "bitget",
            "symbol": normalize_symbol(symbol),
            "product_id": normalize_symbol(symbol),
            "category": normalize_category(category),
            "interval": normalize_interval(interval),
            "bars": bars,
            "provenance": {"source": "official_bitget_mcp", "fallback_used": False},
        }

    @app.get("/bitget/account", dependencies=[Depends(require_auth)])
    async def bitget_account(
        category: str | None = Query(default=None, max_length=32),
        symbol: str | None = Query(default=None, max_length=32),
        coin: str | None = Query(default=None, max_length=16),
    ) -> dict[str, Any]:
        return get_account_overview(category=category, symbol=symbol, coin=coin)

    @app.get("/bitget/positions", dependencies=[Depends(require_auth)])
    async def bitget_positions(
        category: str = Query("USDT-FUTURES", max_length=32),
        symbol: str | None = Query(default=None, max_length=32),
    ) -> dict[str, Any]:
        return get_positions(category=category, symbol=symbol)

    @app.get("/bitget/orders", dependencies=[Depends(require_auth)])
    async def bitget_orders(
        category: str = Query("USDT-FUTURES", max_length=32),
        symbol: str | None = Query(default=None, max_length=32),
    ) -> dict[str, Any]:
        return get_open_orders(category=category, symbol=symbol)

    @app.get("/bitget/fills", dependencies=[Depends(require_auth)])
    async def bitget_fills(
        category: str = Query("USDT-FUTURES", max_length=32),
        symbol: str | None = Query(default=None, max_length=32),
        limit: int = Query(default=50, ge=1, le=100),
    ) -> dict[str, Any]:
        return get_order_fills(category=category, symbol=symbol, limit=limit)

    @app.get("/bitget/strategy-orders", dependencies=[Depends(require_auth)])
    async def bitget_strategy_orders(
        category: str = Query("USDT-FUTURES", max_length=32),
        symbol: str | None = Query(default=None, max_length=32),
        status: str = Query("open", max_length=16),
        limit: int = Query(default=50, ge=1, le=100),
    ) -> dict[str, Any]:
        return get_strategy_orders(category=category, symbol=symbol, status=status, limit=limit)

    @app.get("/bitget/risk-dashboard", dependencies=[Depends(require_auth)])
    async def bitget_risk_dashboard(
        category: str = Query("USDT-FUTURES", max_length=32),
        symbol: str | None = Query(default=None, max_length=32),
    ) -> dict[str, Any]:
        return get_risk_dashboard(category=category, symbol=symbol)

    @app.get("/bitget/alerts", dependencies=[Depends(require_auth)])
    async def bitget_alerts(
        category: str = Query("USDT-FUTURES", max_length=32),
        symbol: str | None = Query(default=None, max_length=32),
    ) -> dict[str, Any]:
        return get_alerts(category=category, symbol=symbol)

    @app.post("/bitget/trade-proposals", dependencies=[Depends(require_auth)])
    async def create_bitget_trade_proposal(body: TradeProposalRequest) -> dict[str, Any]:
        intent = parse_trade_intent(body.prompt, category_hint=body.category, symbol_hint=body.symbol)
        if intent.needs_clarification:
            return {
                "status": "needs_clarification",
                "message": intent.needs_clarification,
                "intent": intent.to_dict(),
            }
        signal = build_market_signal(intent)
        if signal.get("status") != "ok":
            return {
                "status": signal.get("status", "error"),
                "message": signal.get("message") or "Unable to build Bitget signal",
                "intent": intent.to_dict(),
                "signal": signal,
            }
        risk = build_risk_plan(intent.to_dict(), signal)
        proposal = create_trade_proposal(prompt=body.prompt, intent=intent.to_dict(), signal=signal, risk=risk)
        return {
            "status": "ok",
            "intent": intent.to_dict(),
            "proposal": proposal,
            "question": "Would you like me to execute this trade?",
        }

    @app.post("/bitget/trade-proposals/{proposal_id}/execute", dependencies=[Depends(require_auth)])
    async def execute_bitget_trade_proposal(proposal_id: str, body: ExecuteProposalRequest) -> dict[str, Any]:
        return execute_confirmed_trade(
            proposal_id,
            confirmation_text=body.confirmation_text,
            dry_run=body.dry_run,
        )

    @app.post("/bitget/orders/cancel", dependencies=[Depends(require_auth)])
    async def cancel_bitget_order(body: CancelOrderRequest) -> dict[str, Any]:
        return cancel_order(order_id=body.order_id, category=body.category, symbol=body.symbol)

    @app.post("/bitget/strategy-orders/tpsl", dependencies=[Depends(require_auth)])
    async def modify_bitget_tpsl(body: ModifyTpslRequest) -> dict[str, Any]:
        return modify_tpsl(
            category=body.category,
            symbol=body.symbol,
            pos_side=body.pos_side,
            take_profit=body.take_profit,
            stop_loss=body.stop_loss,
            qty=body.qty,
            strategy_order_id=body.strategy_order_id,
            confirmation_text=body.confirmation_text,
            dry_run=body.dry_run,
        )

    @app.post("/bitget/positions/close", dependencies=[Depends(require_auth)])
    async def close_bitget_position(body: ClosePositionRequest) -> dict[str, Any]:
        return close_position(
            category=body.category,
            symbol=body.symbol,
            pos_side=body.pos_side,
            confirmation_text=body.confirmation_text,
            dry_run=body.dry_run,
        )

    @app.post("/bitget/positions/partial-close", dependencies=[Depends(require_auth)])
    async def partial_close_bitget_position(body: PartialCloseRequest) -> dict[str, Any]:
        return partial_close_position(
            category=body.category,
            symbol=body.symbol,
            pos_side=body.pos_side,
            qty=body.qty,
            confirmation_text=body.confirmation_text,
            dry_run=body.dry_run,
        )

    @app.post("/bitget/positions/scale", dependencies=[Depends(require_auth)])
    async def scale_bitget_position(body: ScalePositionRequest) -> dict[str, Any]:
        return scale_position(
            category=body.category,
            symbol=body.symbol,
            side=body.side,
            qty=body.qty,
            pos_side=body.pos_side,
            confirmation_text=body.confirmation_text,
            dry_run=body.dry_run,
        )

    @app.post("/bitget/trailing-stop-proposals", dependencies=[Depends(require_auth)])
    async def bitget_trailing_stop_proposal(body: TrailingStopProposalRequest) -> dict[str, Any]:
        return build_trailing_stop_proposal(
            category=body.category,
            symbol=body.symbol,
            pos_side=body.pos_side,
            callback_percent=body.callback_percent,
        )

    @app.websocket("/bitget/ws/positions")
    async def bitget_position_stream(websocket: WebSocket) -> None:
        if not await _authorize_ws(websocket):
            return
        await websocket.accept()
        category = websocket.query_params.get("category") or "USDT-FUTURES"
        symbol = websocket.query_params.get("symbol") or None
        interval_ms = int(websocket.query_params.get("interval_ms") or "5000")
        interval_s = max(3.0, min(interval_ms / 1000, 60.0))
        try:
            while True:
                await websocket.send_json(
                    {
                        "type": "positions_snapshot",
                        "category": normalize_category(category),
                        "symbol": normalize_symbol(symbol) if symbol else None,
                        "positions": get_positions(category=category, symbol=symbol),
                        "orders": get_open_orders(category=category, symbol=symbol),
                    }
                )
                await asyncio.sleep(interval_s)
        except WebSocketDisconnect:
            return
