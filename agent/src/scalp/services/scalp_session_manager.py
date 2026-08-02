"""Session lifecycle manager and multi-agent workflow coordinator."""

from __future__ import annotations

import logging
import threading
import time

from typing import Any, Dict, List, Optional
from src.scalp.models.scalp_session import ScalpSession, SessionStats
from src.scalp.models.session_policy import SessionPolicy, AutonomyMode
from src.scalp.models.trade_proposal import TradeProposal, NetEdgeBreakdown
from src.scalp.models.scalp_trade import ScalpTrade
from src.scalp.services.session_policy_parser import parse_session_mission
from src.scalp.services.market_universe_scanner import get_market_scanner
from src.scalp.services.technical_indicator_service import TechnicalIndicatorService
from src.scalp.services.market_regime_classifier import MarketRegimeClassifier
from src.scalp.agents.market_intelligence_agent import MarketIntelligenceAgent
from src.scalp.agents.technical_strategy_agent import TechnicalStrategyAgent
from src.scalp.agents.risk_critic_agent import RiskCriticAgent
from src.scalp.agents.execution_monitoring_agent import ExecutionMonitoringAgent
from src.scalp.services.scalp_risk_engine import ScalpRiskEngine
from src.scalp.services.scalp_execution_service import get_execution_service
from src.scalp.services.scalp_position_monitor import ScalpPositionMonitor
from src.scalp.services.scalp_learning_service import ScalpLearningService
from src.scalp.services.duckdb_store import get_duckdb_store
from src.scalp.services.scalp_audit_service import get_audit_service

logger = logging.getLogger(__name__)


class ScalpSessionManager:
    def __init__(self) -> None:
        self._sessions: Dict[str, ScalpSession] = {}
        self._active_trades: Dict[str, ScalpTrade] = {}
        self._lock = threading.Lock()
        self.store = get_duckdb_store()
        self.intel_agent = MarketIntelligenceAgent()
        self.tech_agent = TechnicalStrategyAgent()
        self.risk_critic = RiskCriticAgent()
        self.exec_service = get_execution_service()
        self.learning_service = ScalpLearningService()
        self.audit_service = get_audit_service()

        # Start autonomous background execution loop thread
        self._bg_thread = threading.Thread(target=self._background_execution_loop, daemon=True)
        self._bg_thread.start()

    def _background_execution_loop(self) -> None:
        """Background thread executing session cycles for active sessions continuously."""
        while True:
            time.sleep(4.0)
            try:
                active_sids = self.list_active_sessions()
                for sid in active_sids:
                    self.run_session_cycle(sid)
            except Exception as exc:
                logger.warning(f"Background scalp session cycle error: {exc}")

    def create_session(self, user_mission: str, custom_policy: Optional[Dict[str, Any]] = None) -> ScalpSession:
        session_id = f"ses_{hex(int(time.time() * 1000))[2:]}"
        created_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        if custom_policy:
            policy = SessionPolicy(**custom_policy)
        else:
            policy = parse_session_mission(user_mission)

        session = ScalpSession(
            session_id=session_id,
            user_mission=user_mission,
            policy=policy,
            status="DRAFT",
            starting_capital_usdt=policy.allocated_capital,
            current_capital_usdt=policy.allocated_capital,
            session_pnl_usdt=0.0,
            created_at=created_at,
        )

        with self._lock:
            self._sessions[session_id] = session

        self.store.save_session(session.model_dump())
        self.audit_service.record_audit(session_id, "SESSION_CREATE", "USER", {"mission": user_mission})
        return session

    def start_session(self, session_id: str) -> ScalpSession:
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                stored = self.store.get_session(session_id)
                if stored:
                    session = ScalpSession(**stored)
                    self._sessions[session_id] = session
            if not session:
                raise ValueError(f"Session {session_id} not found")

            session.status = "ACTIVE"
            session.started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            self.store.save_session(session.model_dump())

        self.audit_service.record_audit(session_id, "SESSION_START", "USER", {})
        return session

    def stop_session(self, session_id: str, reason: str = "User requested stop") -> ScalpSession:
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                stored = self.store.get_session(session_id)
                if stored:
                    session = ScalpSession(**stored)
            if not session:
                raise ValueError(f"Session {session_id} not found")

            session.status = "STOPPED" if "stop" in reason.lower() else "COMPLETED"
            session.stopped_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            session.stop_reason = reason
            self.store.save_session(session.model_dump())

        self.audit_service.record_audit(session_id, "SESSION_STOP", "USER", {"reason": reason})
        return session

    def get_session(self, session_id: str) -> Optional[ScalpSession]:
        with self._lock:
            if session_id in self._sessions:
                return self._sessions[session_id]
            stored = self.store.get_session(session_id)
            if stored:
                session = ScalpSession(**stored)
                self._sessions[session_id] = session
                return session
            return None

    def list_active_sessions(self) -> List[str]:
        with self._lock:
            stored = self.store.list_all_sessions()
            for sdata in stored:
                sid = sdata["session_id"]
                if sid not in self._sessions:
                    try:
                        self._sessions[sid] = ScalpSession(**sdata)
                    except Exception:
                        pass
            return [sid for sid, s in self._sessions.items() if s.status == "ACTIVE"]

    def list_all_sessions(self) -> List[ScalpSession]:
        with self._lock:
            stored = self.store.list_all_sessions()
            for sdata in stored:
                sid = sdata["session_id"]
                if sid not in self._sessions:
                    try:
                        self._sessions[sid] = ScalpSession(**sdata)
                    except Exception:
                        pass
            return list(self._sessions.values())

    def run_session_cycle(self, session_id: str) -> Dict[str, Any]:
        """Execute one complete multi-agent cycle for a session."""
        session = self.get_session(session_id)
        if not session or session.status != "ACTIVE":
            return {"status": "inactive", "message": "Session is not active"}

        # 1. Fast position check if active trade exists
        if session.active_position_id:
            trade = self._active_trades.get(session.active_position_id)
            if trade and trade.status == "OPEN":
                trade = ScalpPositionMonitor.update_position(trade)
                if trade.status == "CLOSED":
                    # Trade completed!
                    session.active_position_id = None
                    session.session_pnl_usdt += trade.net_pnl_usdt
                    session.current_capital_usdt += trade.net_pnl_usdt
                    session.session_pnl_pct = (session.session_pnl_usdt / session.starting_capital_usdt) * 100.0

                    # Update stats
                    session.stats.total_trades += 1
                    if trade.net_pnl_usdt > 0:
                        session.stats.winning_trades += 1
                        session.stats.consecutive_losses = 0
                    else:
                        session.stats.losing_trades += 1
                        session.stats.consecutive_losses += 1

                    win_count = session.stats.winning_trades
                    total_count = session.stats.total_trades
                    session.stats.win_rate_pct = round((win_count / total_count) * 100.0, 1) if total_count > 0 else 0.0

                    # Evaluate learning
                    self.learning_service.evaluate_completed_trade(trade)

                    # Check Target Profit or Max Loss Stop conditions
                    if session.session_pnl_usdt >= session.policy.target_profit:
                        self.stop_session(session_id, reason="TARGET_PROFIT_REACHED")
                    elif abs(session.session_pnl_usdt) >= session.policy.maximum_session_loss and session.session_pnl_usdt < 0:
                        self.stop_session(session_id, reason="MAXIMUM_SESSION_LOSS_HIT")

                    self.store.save_session(session.model_dump())
                    return {"status": "trade_closed", "trade": trade.model_dump()}

                return {"status": "position_monitored", "trade": trade.model_dump()}

        # 2. Run Market Universe Scan
        scanner = get_market_scanner()
        scan_res = scanner.scan_universe(session.policy.allowed_symbols)
        candidates = scan_res.get("candidates", [])
        if not candidates:
            return {"status": "no_candidates", "message": "No liquid markets found"}

        top_cand_data = candidates[0]
        symbol = top_cand_data["symbol"]

        # 3. Agent 1: Market Intelligence Agent (Exa + CoinGecko)
        intel_res = self.intel_agent.analyze(symbol, top_cand_data.get("coin_name", ""))
        if intel_res.get("event_veto"):
            return {
                "status": "vetoed",
                "symbol": symbol,
                "reason": f"Event veto by Market Intelligence Agent: {intel_res.get('critical_risks')}",
            }

        # 4. Fetch indicators & Agent 2: Technical Strategy Agent
        from src.services.bitget_mcp import fetch_candles, fetch_ticker
        candles = fetch_candles(symbol=symbol, category="USDT-FUTURES", interval="5m", lookback=100)
        ticker = fetch_ticker(symbol=symbol, category="USDT-FUTURES")
        indicators = TechnicalIndicatorService.compute_all_indicators(candles, ticker)
        regime_res = MarketRegimeClassifier.classify(indicators, symbol=symbol, ticker=ticker)

        tech_res = self.tech_agent.analyze(indicators, regime_res.primary_regime.value, session.policy.allowed_strategy_templates)
        if tech_res.get("decision") == "WAIT":
            return {
                "status": "no_trade",
                "symbol": symbol,
                "funnel_summary": scan_res.get("funnel_counts"),
                "reason": "NO TRADE — No candidate met required strategy edge & quality score threshold.",
            }

        # 5. Agent 3: Risk & Critic Agent
        critic_res = self.risk_critic.analyze(
            technical_output=tech_res,
            candidate_data=top_cand_data,
            margin_usdt=session.policy.maximum_margin_per_trade,
            leverage=session.policy.maximum_leverage,
        )

        # Build Proposal
        net_edge_data = critic_res.get("net_edge", {})
        proposal = TradeProposal(
            proposal_id=f"prop_{int(time.time())}_{symbol.lower()}",
            symbol=symbol,
            coin_name=top_cand_data.get("coin_name", ""),
            coin_icon=top_cand_data.get("coin_icon", ""),
            strategy_id=tech_res.get("strategy_id", "ema_vwap_pullback_v1"),
            strategy_name=tech_res.get("strategy_name", "EMA & VWAP Pullback"),
            market_regime=regime_res.primary_regime.value,
            direction=tech_res.get("direction", "LONG"),
            timeframe="5m",
            entry_price=tech_res.get("entry_price", 0.0),
            stop_loss=tech_res.get("stop_loss", 0.0),
            take_profit_1=tech_res.get("take_profit_1", 0.0),
            leverage=session.policy.maximum_leverage,
            margin_mode=session.policy.margin_mode,
            position_size_usdt=critic_res.get("position_size_usdt", 30.0),
            margin_required_usdt=session.policy.maximum_margin_per_trade,
            risk_amount_usdt=critic_res.get("risk_amount_usdt", 0.5),
            risk_percent=critic_res.get("risk_percent", 2.5),
            estimated_liquidation_price=critic_res.get("estimated_liquidation_price", 0.0),
            liquidation_distance_percent=critic_res.get("liquidation_distance_percent", 30.0),
            setup_quality_score=tech_res.get("setup_quality_score", 85.0),
            net_edge=NetEdgeBreakdown(**net_edge_data) if net_edge_data else NetEdgeBreakdown(),
            why_this_trade={
                "market_selection": f"Ranked #1 candidate with opportunity score {top_cand_data.get('opportunity_score')}/100",
                "market_regime": regime_res.primary_regime.value,
                "strategy": tech_res.get("strategy_name"),
                "supporting_signals": tech_res.get("supporting_signals"),
                "expected_net_edge": f"+{critic_res.get('expected_net_profit_usdt', 0.0):.2f} USDT after fees & slippage",
            },
            created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )

        # 6. Deterministic Risk Engine Gate
        risk_check = ScalpRiskEngine.evaluate_proposal(proposal, session, session.policy)
        if not risk_check.get("approved"):
            proposal.status = "REJECTED"
            proposal.rejection_reason = "; ".join(risk_check.get("rejection_reasons", []))
            return {
                "status": "risk_rejected",
                "proposal": proposal.model_dump(),
                "reason": proposal.rejection_reason,
            }

        # 7. Autonomy Mode Approval
        if session.policy.autonomy_mode == AutonomyMode.COPILOT:
            session.active_proposal_id = proposal.proposal_id
            self.store.save_session(session.model_dump())
            return {
                "status": "proposal_created",
                "proposal": proposal.model_dump(),
                "requires_user_approval": True,
            }

        # Guarded Autopilot / Full Autonomous -> Execute automatically
        try:
            trade = self.exec_service.execute_proposal(session_id, proposal, dry_run=False)
            with self._lock:
                self._active_trades[trade.trade_id] = trade
            session.active_position_id = trade.trade_id
            session.active_proposal_id = None
            self.store.save_session(session.model_dump())

            return {
                "status": "trade_executed",
                "trade": trade.model_dump(),
                "proposal": proposal.model_dump(),
            }
        except Exception as exc:
            logger.error(f"Execution failed for {session_id}: {exc}")
            return {
                "status": "error",
                "symbol": symbol,
                "message": str(exc)
            }


_manager_instance: ScalpSessionManager | None = None


def get_session_manager() -> ScalpSessionManager:
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = ScalpSessionManager()
    return _manager_instance
