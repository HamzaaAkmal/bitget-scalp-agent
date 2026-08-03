"""Unit tests for the rebuilt AI Scalp Engine modules."""

from __future__ import annotations

import pytest
import time
from src.scalp.accounting.pnl_ledger import PnLLedger
from src.scalp.positions.position_state_machine import PositionStateMachine, PositionState
from src.scalp.execution.idempotency_service import IdempotencyService
from src.scalp.execution.capital_reservation_service import CapitalReservationService
from src.scalp.market_data.market_data_cache import MarketDataCache
from src.scalp.intelligence.news_risk_cache import NewsRiskCache


def test_pnl_ledger_long():
    # Long trade: 1 BTC entered at 50,000, exited at 51,000. Entry fee 10, Exit fee 10
    res = PnLLedger.calculate_realized_pnl(
        direction="LONG",
        entry_qty=1.0,
        avg_entry_price=50000.0,
        exit_qty=1.0,
        avg_exit_price=51000.0,
        entry_fees_usdt=10.0,
        exit_fees_usdt=10.0,
        funding_paid_usdt=2.0,
        funding_received_usdt=0.0,
    )
    assert res["gross_realized_pnl_usdt"] == 1000.0
    assert res["total_fees_usdt"] == 20.0
    assert res["net_realized_pnl_usdt"] == 978.0  # 1000 - 20 - 2


def test_pnl_ledger_short():
    # Short trade: 1 BTC entered at 50,000, exited at 49,000. Entry fee 10, Exit fee 10
    res = PnLLedger.calculate_realized_pnl(
        direction="SHORT",
        entry_qty=1.0,
        avg_entry_price=50000.0,
        exit_qty=1.0,
        avg_exit_price=49000.0,
        entry_fees_usdt=10.0,
        exit_fees_usdt=10.0,
    )
    assert res["gross_realized_pnl_usdt"] == 1000.0
    assert res["net_realized_pnl_usdt"] == 980.0


def test_position_state_machine():
    state = PositionStateMachine.transition(PositionState.PROPOSAL_CREATED, PositionState.RISK_APPROVED)
    assert state == "RISK_APPROVED"

    state = PositionStateMachine.transition(PositionState.RISK_APPROVED, PositionState.CAPITAL_RESERVED)
    assert state == "CAPITAL_RESERVED"


def test_capital_reservation_service():
    service = CapitalReservationService()
    res = service.reserve_capital(session_id="ses_test", proposal_id="prop_1", amount_usdt=10.0, available_capital_usdt=25.0)
    assert res["success"] is True

    # Try to reserve more than remaining free
    res2 = service.reserve_capital(session_id="ses_test", proposal_id="prop_2", amount_usdt=20.0, available_capital_usdt=25.0)
    assert res2["success"] is False

    service.release_reservation(session_id="ses_test", amount_usdt=10.0)


def test_market_data_cache():
    cache = MarketDataCache(default_stale_ms=1000)
    cache.update_snapshot("BTCUSDT", {
        "last_price": 50000.0,
        "best_bid": 49999.0,
        "best_ask": 50001.0,
    })
    snap = cache.get_snapshot("BTCUSDT")
    assert snap is not None
    assert snap["last_price"] == 50000.0
    assert snap["spread_bps"] > 0
    assert cache.is_stale("BTCUSDT") is False


def test_news_risk_cache():
    cache = NewsRiskCache(default_ttl_seconds=300)
    cache.update_news_risk("ETHUSDT", veto_active=True, risk_status="FOMC_VETO", reasons=["FOMC Rate Decision"], confidence=0.95, sources=[])
    risk = cache.get_news_risk("ETHUSDT")
    assert risk["veto_active"] is True
    assert risk["risk_status"] == "FOMC_VETO"
