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

from src.scalp.intelligence.news_risk_cache import get_news_risk_cache
from src.scalp.execution.execution_gateway import get_execution_gateway
from src.scalp.market_data.market_data_cache import get_market_data_cache

logger = logging.getLogger(__name__)


class ScalpSessionManager:
    def __init__(self) -> None:
        self._sessions: Dict[str, ScalpSession] = {}
        self._active_trades: Dict[str, ScalpTrade] = {}
        self._agent_logs: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
        self._session_locks: Dict[str, threading.Lock] = {}
        self.store = get_duckdb_store()
        self.intel_agent = MarketIntelligenceAgent()
        self.tech_agent = TechnicalStrategyAgent()
        self.risk_critic = RiskCriticAgent()
        self.exec_gateway = get_execution_gateway()
        self.news_risk_cache = get_news_risk_cache()
        self.market_cache = get_market_data_cache()
        self.learning_service = ScalpLearningService()
        self.audit_service = get_audit_service()

        # Start autonomous background execution loop thread
        self._bg_thread = threading.Thread(target=self._background_execution_loop, daemon=True)
        self._bg_thread.start()

    def add_agent_log(self, session_id: str, agent: str, level: str, action: str, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        entry = {
            "timestamp": time.strftime("%H:%M:%S", time.localtime()),
            "session_id": session_id,
            "agent": agent,
            "level": level,
            "action": action,
            "message": message,
            "details": details or {},
        }
        with self._lock:
            self._agent_logs.append(entry)
            if len(self._agent_logs) > 300:
                self._agent_logs.pop(0)

    def get_agent_logs(self, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            session_logs = [l for l in reversed(self._agent_logs) if l.get("session_id") == session_id]
            if not session_logs:
                # Return all recent system agent logs if session-specific logs empty
                session_logs = list(reversed(self._agent_logs))
            return session_logs[:limit]

    def _get_session_lock(self, session_id: str) -> threading.Lock:
        with self._lock:
            if session_id not in self._session_locks:
                self._session_locks[session_id] = threading.Lock()
            return self._session_locks[session_id]

    def _background_execution_loop(self) -> None:
        """Background thread executing session cycles for active sessions continuously."""
        while True:
            time.sleep(3.0)
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
        self.add_agent_log(session_id, "Agent 4 — Autonomous Execution", "CREATE", "SESSION_CREATED", f"Initialized Scalp Trading Session {session_id}. Policy target: +{policy.target_profit} USDT.")
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
        self.add_agent_log(session_id, "Agent 4 — Autonomous Execution", "START", "SESSION_STARTED", f"Launched autonomous session loop for {session_id}. 4 Multi-Agents ACTIVE.")
        return session

    def stop_session(self, session_id: str, reason: str = "User requested stop") -> ScalpSession:
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                stored = self.store.get_session(session_id)
                if stored:
                    session = ScalpSession(**stored)
            if not session:
                session = ScalpSession(
                    session_id=session_id,
                    user_mission="User requested stop",
                    policy=SessionPolicy(),
                    status="STOPPED",
                    starting_capital_usdt=20.0,
                    current_capital_usdt=20.0,
                    session_pnl_usdt=0.0,
                    created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                )

            session.status = "STOPPED"
            session.active_position_id = None
            session.active_proposal_id = None
            session.stopped_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            session.stop_reason = reason
            self._sessions[session_id] = session
            self.store.save_session(session.model_dump())

            # Clear active trades for stopped session
            trades_to_pop = [tid for tid, trd in self._active_trades.items() if trd.session_id == session_id]
            for tid in trades_to_pop:
                self._active_trades.pop(tid, None)

        self.audit_service.record_audit(session_id, "SESSION_STOP", "USER", {"reason": reason})
        self.add_agent_log(session_id, "Agent 4 — Autonomous Execution", "STOP", "SESSION_STOPPED", f"Session {session_id} stopped cleanly. Reason: {reason}")
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
        """Execute one complete multi-agent cycle for a session with per-session execution locking."""
        s_lock = self._get_session_lock(session_id)
        if not s_lock.acquire(blocking=False):
            return {"status": "locked", "message": f"Session cycle for {session_id} is already in progress."}

        try:
            session = self.get_session(session_id)
            if not session or session.status != "ACTIVE":
                return {"status": "inactive", "message": "Session is not active"}

            # 1. Position monitoring check for ALL active trades
            stored_trades = self.store.get_session_trades(session_id)
            open_trades = []
            for st in stored_trades:
                if st.get("status") == "OPEN":
                    from src.scalp.models.scalp_trade import ScalpTrade
                    from src.scalp.services.scalp_position_monitor import ScalpPositionMonitor
                    trade_obj = ScalpTrade(**st)
                    trade_obj = ScalpPositionMonitor.update_position(trade_obj)
                    if trade_obj.status == "CLOSED":
                        # Trade completed!
                        if trade_obj.trade_id in session.active_position_ids:
                            session.active_position_ids.remove(trade_obj.trade_id)
                        if session.active_position_id == trade_obj.trade_id:
                            session.active_position_id = session.active_position_ids[-1] if session.active_position_ids else None
                        
                        session.session_pnl_usdt += trade_obj.net_pnl_usdt
                        session.current_capital_usdt += trade_obj.net_pnl_usdt
                        session.session_pnl_pct = (session.session_pnl_usdt / session.starting_capital_usdt) * 100.0

                        # Update stats
                        session.stats.total_trades += 1
                        if trade_obj.net_pnl_usdt > 0:
                            session.stats.winning_trades += 1
                            session.stats.consecutive_losses = 0
                        else:
                            session.stats.losing_trades += 1
                            session.stats.consecutive_losses += 1

                        win_count = session.stats.winning_trades
                        total_count = session.stats.total_trades
                        session.stats.win_rate_pct = round((win_count / total_count) * 100.0, 1) if total_count > 0 else 0.0

                        # Evaluate learning
                        self.learning_service.evaluate_completed_trade(trade_obj)
                        self.add_agent_log(session_id, "Agent 4 — Autonomous Execution", "CLOSED", "TRADE_CLOSED", f"Closed {trade_obj.symbol} ({trade_obj.exit_reason}). Net PnL: {trade_obj.net_pnl_usdt:.4f} USDT", trade_obj.model_dump())

                        # Check Target Profit or Max Loss Stop conditions
                        if session.session_pnl_usdt >= session.policy.target_profit:
                            self.stop_session(session_id, reason="TARGET_PROFIT_REACHED")
                        elif abs(session.session_pnl_usdt) >= session.policy.maximum_session_loss and session.session_pnl_usdt < 0:
                            self.stop_session(session_id, reason="MAXIMUM_SESSION_LOSS_HIT")

                        self.store.save_session(session.model_dump())
                    else:
                        open_trades.append(trade_obj)
                        self.add_agent_log(
                            session_id,
                            "Agent 4 — Autonomous Execution",
                            "MONITORING",
                            "POSITION_CHECK",
                            f"Live Monitoring {trade_obj.symbol} ({trade_obj.direction} {trade_obj.leverage}x): Mark Price ${trade_obj.current_price} | PnL: {trade_obj.unrealized_pnl_usdt} USDT ({trade_obj.unrealized_pnl_pct}%)",
                            trade_obj.model_dump()
                        )

            # Max concurrent positions check
            max_pos = session.policy.maximum_concurrent_positions or 3
            if len(open_trades) >= max_pos:
                self.add_agent_log(session_id, "Agent 3 — Risk & Critic", "INFO", "MAX_POSITIONS", f"Holding maximum active concurrent positions ({len(open_trades)}/{max_pos}). Monitoring open positions for TP/SL triggers.")

            # 2. Run Market Universe Scan (Agent 1)
            scanner = get_market_scanner()
            scan_res = scanner.scan_universe(session.policy.allowed_symbols)
            candidates = scan_res.get("candidates", [])
            if not candidates:
                self.add_agent_log(session_id, "Agent 1 — Market Scanner", "INFO", "SCAN_EMPTY", "No liquid candidates passed volume & liquidity filters.")
                return {"status": "no_candidates", "message": "No liquid markets found"}

            top_cand_data = candidates[0]
            symbol = top_cand_data["symbol"]
            self.add_agent_log(session_id, "Agent 1 — Market Scanner", "SUCCESS", "CANDIDATE_SELECTED", f"Selected #1 Candidate: {symbol} (Opportunity Score: {top_cand_data.get('opportunity_score')}/100)", top_cand_data)

            # Prevent opening duplicate position on the same symbol if already open
            if any(t.symbol == symbol for t in open_trades):
                self.add_agent_log(session_id, "Agent 1 — Market Scanner", "WARN", "SYMBOL_OPEN", f"Position already open for {symbol}. Skipping duplicate entry.")
                return {"status": "symbol_already_open", "symbol": symbol, "message": f"Position already open for {symbol}"}

            if len(open_trades) >= max_pos:
                return {"status": "max_positions_reached", "open_count": len(open_trades), "message": f"Maximum concurrent positions ({max_pos}) reached."}

            # 3. Check News Risk Cache
            news_risk = self.news_risk_cache.get_news_risk(symbol, policy_mode="guarded")
            if news_risk.get("veto_active"):
                self.add_agent_log(session_id, "Agent 1 — Market Scanner", "VETO", "NEWS_RISK_VETO", f"News Risk Veto active for {symbol}: {news_risk.get('reasons')}")
                return {
                    "status": "vetoed",
                    "symbol": symbol,
                    "reason": f"Event veto by News Risk Cache: {news_risk.get('reasons')}",
                }

            # 4. Fetch indicators & Agent 2: Technical Strategy Agent
            from src.services.bitget_mcp import fetch_candles, fetch_ticker
            candles = fetch_candles(symbol=symbol, category="USDT-FUTURES", interval="5m", lookback=100)
            ticker = fetch_ticker(symbol=symbol, category="USDT-FUTURES")
            indicators = TechnicalIndicatorService.compute_all_indicators(candles, ticker)
            regime_res = MarketRegimeClassifier.classify(indicators, symbol=symbol, ticker=ticker)

            tech_res = self.tech_agent.analyze(indicators, regime_res.primary_regime.value, session.policy.allowed_strategy_templates)
            self.add_agent_log(
                session_id,
                "Agent 2 — Technical Strategy",
                "SUCCESS" if tech_res.get("decision") == "ENTER" else "INFO",
                "STRATEGY_ANALYSIS",
                f"Regime: {regime_res.primary_regime.value} | Strategy: {tech_res.get('strategy_name')} | Decision: {tech_res.get('decision')} ({tech_res.get('direction', 'LONG')}) @ {tech_res.get('entry_price')}",
                {"indicators": indicators, "regime": regime_res.primary_regime.value, "tech_output": tech_res}
            )

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
            self.add_agent_log(
                session_id,
                "Agent 3 — Risk & Critic",
                "SUCCESS",
                "RISK_EVALUATION",
                f"Evaluated Expected Net Edge: +{critic_res.get('expected_net_profit_usdt', 0.0):.2f} USDT | Liq Distance: {critic_res.get('liquidation_distance_percent', 30.0)}%",
                critic_res
            )

            # Build Proposal
            net_edge_data = critic_res.get("net_edge", {})
            proposal_id = f"prop_{int(time.time())}_{symbol.lower()}"
            created_at_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            expires_at_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 180))  # 3-minute expiration

            proposal = TradeProposal(
                proposal_id=proposal_id,
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
                created_at=created_at_str,
            )

            # 6. Deterministic Risk Engine Gate
            risk_check = ScalpRiskEngine.evaluate_proposal(proposal, session, session.policy)
            if not risk_check.get("approved"):
                proposal.status = "REJECTED"
                proposal.rejection_reason = "; ".join(risk_check.get("rejection_reasons", []))
                self.add_agent_log(session_id, "Agent 3 — Risk & Critic", "REJECT", "RISK_ENGINE_REJECT", f"Risk Engine rejected proposal for {symbol}: {proposal.rejection_reason}")
                return {
                    "status": "risk_rejected",
                    "proposal": proposal.model_dump(),
                    "reason": proposal.rejection_reason,
                }

            # Save Proposal to persistent DB
            self.store.save_proposal(proposal_id, session_id, symbol, proposal.direction, proposal.model_dump(), expires_at_str, "PENDING")

            # 7. Human Approval / Autonomy Mode Approval Gate (Agent 4)
            require_human = getattr(session.policy, "require_human_approval", True)
            if require_human or session.policy.autonomy_mode == AutonomyMode.COPILOT:
                session.active_proposal_id = proposal.proposal_id
                self.store.save_session(session.model_dump())
                self.add_agent_log(
                    session_id,
                    "Agent 4 — Autonomous Execution",
                    "HUMAN_APPROVAL_GATE",
                    "PROPOSAL_PENDING",
                    f"Created trade proposal {proposal_id} for {symbol} ({proposal.direction} {proposal.leverage}x). Awaiting user approval.",
                    proposal.model_dump()
                )
                return {
                    "status": "proposal_created",
                    "proposal": proposal.model_dump(),
                    "requires_user_approval": True,
                }

            # Guarded Autopilot / Full Autonomous -> Execute automatically via ExecutionGateway
            exec_res = self.exec_gateway.execute_proposal(
                session_id=session_id,
                proposal=proposal.model_dump(),
                available_capital_usdt=session.current_capital_usdt,
                dry_run=False,
            )

            if exec_res.get("status") == "ok":
                trade_dict = exec_res["trade"]
                trade_obj = ScalpTrade(**trade_dict)
                with self._lock:
                    self._active_trades[trade_obj.trade_id] = trade_obj
                if trade_obj.trade_id not in session.active_position_ids:
                    session.active_position_ids.append(trade_obj.trade_id)
                session.active_position_id = trade_obj.trade_id
                session.active_proposal_id = None
                self.store.save_session(session.model_dump())

                return {
                    "status": "trade_executed",
                    "trade": trade_dict,
                    "proposal": proposal.model_dump(),
                }
            else:
                return {
                    "status": "error",
                    "symbol": symbol,
                    "message": exec_res.get("error", "Execution gateway failure"),
                }
        finally:
            s_lock.release()


_manager_instance: ScalpSessionManager | None = None


def get_session_manager() -> ScalpSessionManager:
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = ScalpSessionManager()
    return _manager_instance
