"""DuckDB storage layer for AI Scalp Trader persistence."""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any, List, Dict, Optional

from src.config.paths import get_runs_dir

logger = logging.getLogger(__name__)

DB_PATH = get_runs_dir() / "scalp_trader.duckdb"

# We use duckdb if installed, falling back cleanly to sqlite3 if duckdb module has binary lock issues.
try:
    import duckdb  # type: ignore
    HAS_DUCKDB = True
except ImportError:
    HAS_DUCKDB = False


class ScalpDuckDBStore:
    def __init__(self, db_file: Path | str = DB_PATH) -> None:
        self.db_file = Path(db_file)
        self.db_file.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self):
        if HAS_DUCKDB:
            return duckdb.connect(str(self.db_file))
        else:
            return sqlite3.connect(str(self.db_file.with_suffix(".sqlite")))

    def _init_db(self) -> None:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scalp_sessions (
                    session_id VARCHAR PRIMARY KEY,
                    user_mission TEXT,
                    status VARCHAR,
                    starting_capital DOUBLE,
                    current_capital DOUBLE,
                    session_pnl DOUBLE,
                    policy_json TEXT,
                    stats_json TEXT,
                    created_at VARCHAR,
                    updated_at VARCHAR
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scalp_trades (
                    trade_id VARCHAR PRIMARY KEY,
                    session_id VARCHAR,
                    symbol VARCHAR,
                    direction VARCHAR,
                    status VARCHAR,
                    entry_price DOUBLE,
                    exit_price DOUBLE,
                    net_pnl DOUBLE,
                    proposal_json TEXT,
                    trade_json TEXT,
                    created_at VARCHAR
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scalp_audit_logs (
                    audit_id VARCHAR PRIMARY KEY,
                    session_id VARCHAR,
                    timestamp VARCHAR,
                    action_type VARCHAR,
                    actor VARCHAR,
                    data_json TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS strategy_performance (
                    strategy_id VARCHAR PRIMARY KEY,
                    version VARCHAR,
                    total_trades INT,
                    wins INT,
                    losses INT,
                    net_pnl DOUBLE,
                    profit_factor DOUBLE,
                    win_rate DOUBLE,
                    updated_at VARCHAR
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scalp_proposals (
                    proposal_id VARCHAR PRIMARY KEY,
                    session_id VARCHAR,
                    symbol VARCHAR,
                    direction VARCHAR,
                    proposal_json TEXT,
                    created_at VARCHAR,
                    expires_at VARCHAR,
                    status VARCHAR
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scalp_orders (
                    order_id VARCHAR PRIMARY KEY,
                    client_order_id VARCHAR,
                    session_id VARCHAR,
                    trade_id VARCHAR,
                    symbol VARCHAR,
                    side VARCHAR,
                    pos_side VARCHAR,
                    order_type VARCHAR,
                    qty DOUBLE,
                    price DOUBLE,
                    status VARCHAR,
                    order_json TEXT,
                    created_at VARCHAR,
                    updated_at VARCHAR
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scalp_fills (
                    fill_id VARCHAR PRIMARY KEY,
                    order_id VARCHAR,
                    trade_id VARCHAR,
                    symbol VARCHAR,
                    side VARCHAR,
                    pos_side VARCHAR,
                    price DOUBLE,
                    qty DOUBLE,
                    fee DOUBLE,
                    fee_currency VARCHAR,
                    liquidity_role VARCHAR,
                    exchange_timestamp VARCHAR,
                    fill_json TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scalp_idempotency (
                    idempotency_key VARCHAR PRIMARY KEY,
                    request_type VARCHAR,
                    response_json TEXT,
                    created_at VARCHAR
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scalp_news_risk (
                    symbol VARCHAR PRIMARY KEY,
                    veto_active BOOLEAN,
                    risk_status VARCHAR,
                    reasons_json TEXT,
                    confidence DOUBLE,
                    sources_json TEXT,
                    created_at VARCHAR,
                    expires_at VARCHAR
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def save_session(self, session_data: Dict[str, Any]) -> None:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            session_id = session_data["session_id"]
            user_mission = session_data.get("user_mission", "")
            status = session_data.get("status", "DRAFT")
            starting_capital = float(session_data.get("starting_capital_usdt", 20.0))
            current_capital = float(session_data.get("current_capital_usdt", 20.0))
            session_pnl = float(session_data.get("session_pnl_usdt", 0.0))
            policy_json = json.dumps(session_data.get("policy", {}))
            stats_json = json.dumps(session_data.get("stats", {}))
            created_at = session_data.get("created_at", "")
            updated_at = session_data.get("stopped_at") or created_at

            if HAS_DUCKDB:
                cursor.execute("""
                    INSERT INTO scalp_sessions (
                        session_id, user_mission, status, starting_capital, current_capital, session_pnl, policy_json, stats_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(session_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        current_capital = EXCLUDED.current_capital,
                        session_pnl = EXCLUDED.session_pnl,
                        stats_json = EXCLUDED.stats_json,
                        updated_at = EXCLUDED.updated_at
                """, (session_id, user_mission, status, starting_capital, current_capital, session_pnl, policy_json, stats_json, created_at, updated_at))
            else:
                cursor.execute("""
                    INSERT OR REPLACE INTO scalp_sessions (
                        session_id, user_mission, status, starting_capital, current_capital, session_pnl, policy_json, stats_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (session_id, user_mission, status, starting_capital, current_capital, session_pnl, policy_json, stats_json, created_at, updated_at))
            conn.commit()
        finally:
            conn.close()

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT session_id, user_mission, status, starting_capital, current_capital, session_pnl, policy_json, stats_json, created_at, updated_at FROM scalp_sessions WHERE session_id = ?", (session_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return {
                "session_id": row[0],
                "user_mission": row[1],
                "status": row[2],
                "starting_capital_usdt": row[3],
                "current_capital_usdt": row[4],
                "session_pnl_usdt": row[5],
                "policy": json.loads(row[6]) if row[6] else {},
                "stats": json.loads(row[7]) if row[7] else {},
                "created_at": row[8],
                "updated_at": row[9],
            }
        finally:
            conn.close()

    def save_trade(self, trade_data: Dict[str, Any]) -> None:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            trade_id = trade_data["trade_id"]
            session_id = trade_data["session_id"]
            symbol = trade_data.get("symbol", "")
            direction = trade_data.get("direction", "")
            status = trade_data.get("status", "OPEN")
            entry_price = float(trade_data.get("entry_price", 0.0))
            exit_price = float(trade_data.get("exit_price", 0.0))
            net_pnl = float(trade_data.get("net_pnl_usdt", 0.0))
            proposal_json = json.dumps(trade_data.get("proposal", {}))
            trade_json = json.dumps(trade_data)
            created_at = trade_data.get("fill_time", "")

            if HAS_DUCKDB:
                cursor.execute("""
                    INSERT INTO scalp_trades (
                        trade_id, session_id, symbol, direction, status, entry_price, exit_price, net_pnl, proposal_json, trade_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(trade_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        exit_price = EXCLUDED.exit_price,
                        net_pnl = EXCLUDED.net_pnl,
                        trade_json = EXCLUDED.trade_json
                """, (trade_id, session_id, symbol, direction, status, entry_price, exit_price, net_pnl, proposal_json, trade_json, created_at))
            else:
                cursor.execute("""
                    INSERT OR REPLACE INTO scalp_trades (
                        trade_id, session_id, symbol, direction, status, entry_price, exit_price, net_pnl, proposal_json, trade_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (trade_id, session_id, symbol, direction, status, entry_price, exit_price, net_pnl, proposal_json, trade_json, created_at))
            conn.commit()
        finally:
            conn.close()

    def get_session_trades(self, session_id: str) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT trade_json FROM scalp_trades WHERE session_id = ? ORDER BY created_at ASC", (session_id,))
            rows = cursor.fetchall()
            return [json.loads(r[0]) for r in rows if r[0]]
        finally:
            conn.close()

    def list_all_sessions(self) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT session_id, user_mission, status, starting_capital, current_capital, session_pnl, policy_json, stats_json, created_at, updated_at FROM scalp_sessions ORDER BY created_at DESC")
            rows = cursor.fetchall()
            result = []
            for row in rows:
                result.append({
                    "session_id": row[0],
                    "user_mission": row[1],
                    "status": row[2],
                    "starting_capital_usdt": row[3],
                    "current_capital_usdt": row[4],
                    "session_pnl_usdt": row[5],
                    "policy": json.loads(row[6]) if row[6] else {},
                    "stats": json.loads(row[7]) if row[7] else {},
                    "created_at": row[8],
                    "updated_at": row[9],
                })
            return result
        finally:
            conn.close()

    def get_latest_trade(self) -> Optional[Dict[str, Any]]:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT trade_json FROM scalp_trades ORDER BY created_at DESC LIMIT 1")
            row = cursor.fetchone()
            if row and row[0]:
                return json.loads(row[0])
            return None
        finally:
            conn.close()

    def save_audit(self, audit_id: str, session_id: str, action_type: str, actor: str, data: Dict[str, Any], timestamp: str) -> None:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            data_json = json.dumps(data)
            cursor.execute("""
                INSERT INTO scalp_audit_logs (audit_id, session_id, timestamp, action_type, actor, data_json)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (audit_id, session_id, timestamp, action_type, actor, data_json))
            conn.commit()
        finally:
            conn.close()

    def save_proposal(self, proposal_id: str, session_id: str, symbol: str, direction: str, proposal_data: Dict[str, Any], expires_at: str, status: str = "PENDING") -> None:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            p_json = json.dumps(proposal_data)
            created_at = proposal_data.get("created_at") or json.dumps(proposal_data).get("timestamp", "")
            if HAS_DUCKDB:
                cursor.execute("""
                    INSERT INTO scalp_proposals (proposal_id, session_id, symbol, direction, proposal_json, created_at, expires_at, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(proposal_id) DO UPDATE SET status = EXCLUDED.status, proposal_json = EXCLUDED.proposal_json
                """, (proposal_id, session_id, symbol, direction, p_json, str(created_at), expires_at, status))
            else:
                cursor.execute("""
                    INSERT OR REPLACE INTO scalp_proposals (proposal_id, session_id, symbol, direction, proposal_json, created_at, expires_at, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (proposal_id, session_id, symbol, direction, p_json, str(created_at), expires_at, status))
            conn.commit()
        finally:
            conn.close()

    def get_proposal(self, proposal_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT proposal_json, status, expires_at FROM scalp_proposals WHERE proposal_id = ?", (proposal_id,))
            row = cursor.fetchone()
            if row and row[0]:
                data = json.loads(row[0])
                data["_status"] = row[1]
                data["_expires_at"] = row[2]
                return data
            return None
        finally:
            conn.close()

    def save_idempotency(self, key: str, req_type: str, resp_data: Dict[str, Any], created_at: str) -> None:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            r_json = json.dumps(resp_data)
            if HAS_DUCKDB:
                cursor.execute("""
                    INSERT INTO scalp_idempotency (idempotency_key, request_type, response_json, created_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(idempotency_key) DO UPDATE SET response_json = EXCLUDED.response_json
                """, (key, req_type, r_json, created_at))
            else:
                cursor.execute("""
                    INSERT OR REPLACE INTO scalp_idempotency (idempotency_key, request_type, response_json, created_at)
                    VALUES (?, ?, ?, ?)
                """, (key, req_type, r_json, created_at))
            conn.commit()
        finally:
            conn.close()

    def get_idempotency(self, key: str) -> Optional[Dict[str, Any]]:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT response_json FROM scalp_idempotency WHERE idempotency_key = ?", (key,))
            row = cursor.fetchone()
            if row and row[0]:
                return json.loads(row[0])
            return None
        finally:
            conn.close()

    def save_news_risk(self, symbol: str, veto_active: bool, risk_status: str, reasons: List[str], confidence: float, sources: List[str], created_at: str, expires_at: str) -> None:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            r_json = json.dumps(reasons)
            s_json = json.dumps(sources)
            if HAS_DUCKDB:
                cursor.execute("""
                    INSERT INTO scalp_news_risk (symbol, veto_active, risk_status, reasons_json, confidence, sources_json, created_at, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(symbol) DO UPDATE SET
                        veto_active = EXCLUDED.veto_active,
                        risk_status = EXCLUDED.risk_status,
                        reasons_json = EXCLUDED.reasons_json,
                        confidence = EXCLUDED.confidence,
                        sources_json = EXCLUDED.sources_json,
                        created_at = EXCLUDED.created_at,
                        expires_at = EXCLUDED.expires_at
                """, (symbol, veto_active, risk_status, r_json, confidence, s_json, created_at, expires_at))
            else:
                cursor.execute("""
                    INSERT OR REPLACE INTO scalp_news_risk (symbol, veto_active, risk_status, reasons_json, confidence, sources_json, created_at, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (symbol, veto_active, risk_status, r_json, confidence, s_json, created_at, expires_at))
            conn.commit()
        finally:
            conn.close()

    def get_news_risk(self, symbol: str) -> Optional[Dict[str, Any]]:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT veto_active, risk_status, reasons_json, confidence, sources_json, created_at, expires_at FROM scalp_news_risk WHERE symbol = ?", (symbol,))
            row = cursor.fetchone()
            if row:
                return {
                    "symbol": symbol,
                    "veto_active": bool(row[0]),
                    "risk_status": row[1],
                    "reasons": json.loads(row[2]) if row[2] else [],
                    "confidence": float(row[3]),
                    "sources": json.loads(row[4]) if row[4] else [],
                    "created_at": row[5],
                    "expires_at": row[6],
                }
            return None
        finally:
            conn.close()


_duckdb_store_instance: ScalpDuckDBStore | None = None


def get_duckdb_store() -> ScalpDuckDBStore:
    global _duckdb_store_instance
    if _duckdb_store_instance is None:
        _duckdb_store_instance = ScalpDuckDBStore()
    return _duckdb_store_instance

