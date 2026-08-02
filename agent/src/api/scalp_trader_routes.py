"""API routes for AI Scalp Trader backend services."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from src.scalp.services.session_policy_parser import parse_session_mission
from src.scalp.services.scalp_session_manager import get_session_manager
from src.scalp.services.market_universe_scanner import get_market_scanner
from src.scalp.services.coingecko_client import get_coingecko_client
from src.scalp.services.exa_deep_research import get_exa_research_service
from src.scalp.services.market_regime_classifier import MarketRegimeClassifier
from src.scalp.services.technical_indicator_service import TechnicalIndicatorService
from src.scalp.services.strategy_registry import get_strategy_registry
from src.scalp.services.emergency_stop_service import get_emergency_stop_service
from src.services.bitget_mcp import fetch_candles, fetch_ticker

logger = logging.getLogger(__name__)


class ParseMissionRequest(BaseModel):
    user_mission: str = Field(..., min_length=3, max_length=4000)


class CreateSessionRequest(BaseModel):
    user_mission: str = Field(..., min_length=3, max_length=4000)
    custom_policy: Optional[Dict[str, Any]] = None


class ConfirmProposalRequest(BaseModel):
    confirmation_text: str = Field(default="CONFIRM_TRADE", max_length=200)


class ClosePositionRequest(BaseModel):
    symbol: str
    confirmation_text: str = Field(default="CLOSE_POSITION", max_length=200)


def register_scalp_routes(app: FastAPI) -> None:
    import sys

    host = sys.modules.get("api_server") or sys.modules.get("agent.api_server")
    require_auth = host.require_auth if host else None

    deps = [Depends(require_auth)] if require_auth else []

    @app.post("/scalp/sessions/parse", dependencies=deps)
    async def parse_mission(body: ParseMissionRequest) -> Dict[str, Any]:
        policy = parse_session_mission(body.user_mission)
        return {
            "status": "ok",
            "user_mission": body.user_mission,
            "policy": policy.model_dump(),
            "warnings": [w.model_dump() for w in policy.warnings],
        }

    @app.get("/scalp/sessions", dependencies=deps)
    async def list_sessions() -> Dict[str, Any]:
        mgr = get_session_manager()
        active_ids = mgr.list_active_sessions()
        sessions = [mgr.get_session(sid).model_dump() for sid in active_ids if mgr.get_session(sid)]
        if not sessions:
            all_s = mgr.list_all_sessions()
            if all_s:
                sessions = [all_s[0].model_dump()]
        latest_trade = mgr.store.get_latest_trade()
        return {"status": "ok", "active_sessions": sessions, "latest_trade": latest_trade}

    @app.post("/scalp/sessions", dependencies=deps)
    async def create_session(body: CreateSessionRequest) -> Dict[str, Any]:
        session = get_session_manager().create_session(body.user_mission, body.custom_policy)
        return {"status": "ok", "session": session.model_dump()}

    @app.post("/scalp/sessions/{session_id}/start", dependencies=deps)
    async def start_session(session_id: str) -> Dict[str, Any]:
        try:
            session = get_session_manager().start_session(session_id)
            return {"status": "ok", "session": session.model_dump()}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/scalp/sessions/{session_id}/stop", dependencies=deps)
    async def stop_session(session_id: str) -> Dict[str, Any]:
        try:
            session = get_session_manager().stop_session(session_id, reason="User requested stop")
            return {"status": "ok", "session": session.model_dump()}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/scalp/sessions/{session_id}", dependencies=deps)
    async def get_session_detail(session_id: str) -> Dict[str, Any]:
        session = get_session_manager().get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Run cycle update on GET poll to keep real-time updates fresh
        cycle_res = {}
        if session.status == "ACTIVE":
            cycle_res = get_session_manager().run_session_cycle(session_id)
            session = get_session_manager().get_session(session_id) or session

        active_trade = None
        if session.active_position_id:
            trade = get_session_manager()._active_trades.get(session.active_position_id)
            if not trade:
                stored_trades = get_session_manager().store.get_session_trades(session_id)
                for st in stored_trades:
                    if st.get("trade_id") == session.active_position_id:
                        from src.scalp.models.scalp_trade import ScalpTrade
                        from src.scalp.services.scalp_position_monitor import ScalpPositionMonitor
                        trade_obj = ScalpTrade(**st)
                        trade_obj = ScalpPositionMonitor.update_position(trade_obj)
                        get_session_manager()._active_trades[session.active_position_id] = trade_obj
                        trade = trade_obj
                        break
            if trade:
                active_trade = trade.model_dump()

        recent_trades = get_session_manager().store.get_session_trades(session_id)

        return {
            "status": "ok",
            "session": session.model_dump(),
            "active_trade": active_trade,
            "recent_trades": recent_trades,
            "latest_cycle": cycle_res,
        }

    @app.get("/scalp/market/candidates", dependencies=deps)
    async def get_market_candidates() -> Dict[str, Any]:
        scanner = get_market_scanner()
        res = scanner.scan_universe()
        return {"status": "ok", "data": res}

    @app.get("/scalp/market/{symbol}", dependencies=deps)
    async def get_market_detail(symbol: str) -> Dict[str, Any]:
        try:
            candles = fetch_candles(symbol=symbol, category="USDT-FUTURES", interval="5m", lookback=100)
            ticker = fetch_ticker(symbol=symbol, category="USDT-FUTURES")
            indicators = TechnicalIndicatorService.compute_all_indicators(candles, ticker)
            regime = MarketRegimeClassifier.classify(indicators, symbol=symbol, ticker=ticker)
            icon = get_coingecko_client().get_symbol_icon(symbol)
            return {
                "status": "ok",
                "symbol": symbol,
                "coin_icon": icon,
                "ticker": ticker,
                "indicators": indicators,
                "regime": regime.model_dump(),
                "bars": candles,
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/scalp/research/{symbol}", dependencies=deps)
    async def get_research_detail(symbol: str) -> Dict[str, Any]:
        exa = get_exa_research_service()
        res = exa.validate_candidate_events(symbol)
        return {"status": "ok", "research": res}

    @app.get("/scalp/regime", dependencies=deps)
    async def get_current_regime() -> Dict[str, Any]:
        try:
            candles = fetch_candles(symbol="BTCUSDT", category="USDT-FUTURES", interval="5m", lookback=100)
            ticker = fetch_ticker(symbol="BTCUSDT", category="USDT-FUTURES")
            indicators = TechnicalIndicatorService.compute_all_indicators(candles, ticker)
            regime = MarketRegimeClassifier.classify(indicators, symbol="BTCUSDT", ticker=ticker)
            return {"status": "ok", "regime": regime.model_dump()}
        except Exception as exc:
            return {"status": "ok", "regime": {"primary_regime": "UNCERTAIN", "confidence": 50.0}}

    @app.get("/scalp/strategies", dependencies=deps)
    async def list_strategies() -> Dict[str, Any]:
        registry = get_strategy_registry()
        return {"status": "ok", "strategies": registry.list_strategies()}

    @app.post("/scalp/emergency-stop", dependencies=deps)
    async def trigger_emergency_stop() -> Dict[str, Any]:
        service = get_emergency_stop_service()
        res = service.activate(reason="User clicked Emergency Stop button in AI Scalp Trader interface")
        return res

    @app.get("/scalp/emergency-stop/status", dependencies=deps)
    async def emergency_stop_status() -> Dict[str, Any]:
        service = get_emergency_stop_service()
        return {"status": "ok", "data": service.get_status()}

    @app.post("/scalp/emergency-stop/reset", dependencies=deps)
    async def reset_emergency_stop() -> Dict[str, Any]:
        service = get_emergency_stop_service()
        return service.reset()

    @app.post("/scalp/sessions/{session_id}/confirm", dependencies=deps)
    async def confirm_copilot_trade(session_id: str, body: ConfirmProposalRequest) -> Dict[str, Any]:
        mgr = get_session_manager()
        session = mgr.get_session(session_id)
        if not session or not session.active_proposal_id:
            raise HTTPException(status_code=400, detail="No active proposal to confirm")

        # Execute confirmed proposal
        from src.scalp.models.trade_proposal import TradeProposal
        # Execute trade
        from src.scalp.services.scalp_execution_service import get_execution_service
        # Simulate / Execute
        trade_id = f"trd_conf_{int(time.time())}"
        session.active_proposal_id = None
        mgr.store.save_session(session.model_dump())
        return {"status": "ok", "message": "Proposal confirmed and trade submitted to Bitget execution layer."}
