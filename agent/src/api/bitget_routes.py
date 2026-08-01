"""Bitget HTTP routes for the Web UI."""

from __future__ import annotations

from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from src.services.bitget_account import get_account_overview, get_connection_status
from src.services.bitget_execution import cancel_order, close_position, execute_confirmed_trade
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


def register_bitget_routes(app: FastAPI) -> None:
    """Mount Bitget routes."""
    import sys

    host = sys.modules.get("api_server") or sys.modules.get("agent.api_server")
    if host is None:
        raise RuntimeError("register_bitget_routes: api_server module not in sys.modules")

    require_auth = host.require_auth

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

    @app.post("/bitget/positions/close", dependencies=[Depends(require_auth)])
    async def close_bitget_position(body: ClosePositionRequest) -> dict[str, Any]:
        return close_position(
            category=body.category,
            symbol=body.symbol,
            pos_side=body.pos_side,
            confirmation_text=body.confirmation_text,
            dry_run=body.dry_run,
        )

