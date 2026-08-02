"""Quantitative market universe scanner with staged opportunity funnel."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from src.scalp.models.scalp_candidate import ScalpCandidate
from src.scalp.services.coingecko_client import get_coingecko_client
from src.scalp.services.technical_indicator_service import TechnicalIndicatorService
from src.scalp.services.market_regime_classifier import MarketRegimeClassifier
from src.scalp.services.opportunity_score_engine import OpportunityScoreEngine
from src.services.bitget_mcp import fetch_candles, fetch_ticker

logger = logging.getLogger(__name__)


class MarketUniverseScanner:
    def __init__(self) -> None:
        self.coingecko = get_coingecko_client()

    def scan_universe(self, allowed_symbols: List[str] | None = None) -> Dict[str, Any]:
        """Run the quantitative staged opportunity funnel."""
        target_symbols = allowed_symbols or ["BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT", "PEPEUSDT", "XRPUSDT"]
        
        candidates: List[ScalpCandidate] = []
        funnel_counts = {
            "all_markets": len(target_symbols),
            "passed_liquidity": 0,
            "passed_technical": 0,
            "top_candidates": 0,
        }

        for sym in target_symbols:
            icon = self.coingecko.get_symbol_icon(sym)
            try:
                candles = fetch_candles(symbol=sym, category="USDT-FUTURES", interval="5m", lookback=100)
                ticker = fetch_ticker(symbol=sym, category="USDT-FUTURES")
            except Exception as exc:
                logger.warning(f"Fetch failed for {sym}: {exc}")
                candles = []
                ticker = {}

            indicators = TechnicalIndicatorService.compute_all_indicators(candles, ticker)
            regime = MarketRegimeClassifier.classify(indicators, symbol=sym, ticker=ticker)

            cand_data = {
                "symbol": sym,
                "volume_24h_usdt": float(ticker.get("quoteVolume", 60000000.0)),
                "bid_ask_spread_bps": 2.5 if "BTC" in sym else 4.0,
                "open_interest_delta_pct": 2.0,
            }

            score, score_comp = OpportunityScoreEngine.calculate_score(cand_data, indicators)

            # Liquidity check
            passed_liq = cand_data["volume_24h_usdt"] >= 5000000.0
            if passed_liq:
                funnel_counts["passed_liquidity"] += 1

            passed_tech = score >= 45.0
            if passed_tech:
                funnel_counts["passed_technical"] += 1

            cand = ScalpCandidate(
                symbol=sym,
                coin_name=sym.replace("USDT", ""),
                coin_icon=icon,
                price_usdt=indicators.get("close", 0.0),
                volume_24h_usdt=cand_data["volume_24h_usdt"],
                bid_ask_spread_bps=cand_data["bid_ask_spread_bps"],
                funding_rate=0.0001,
                opportunity_score=score,
                score_breakdown=score_comp,
                regime=regime,
                eligible_strategies=[
                    "ema_vwap_pullback_v1",
                    "breakout_retest_v1",
                    "liquidity_sweep_reversal_v1",
                    "momentum_continuation_v1",
                    "range_mean_reversion_v1",
                    "volume_expansion_v1",
                    "funding_oi_divergence_v1",
                ],
                funnel_stage="TOP_CANDIDATE" if (passed_liq and passed_tech) else "FILTERED",
                passed_filters=passed_liq and passed_tech,
            )
            candidates.append(cand)

        # Sort candidates by opportunity score
        candidates.sort(key=lambda c: c.opportunity_score, reverse=True)
        funnel_counts["top_candidates"] = len([c for c in candidates if c.passed_filters])

        return {
            "funnel_counts": funnel_counts,
            "candidates": [c.model_dump() for c in candidates],
            "top_candidate": candidates[0].model_dump() if candidates else None,
        }


_scanner_instance: MarketUniverseScanner | None = None


def get_market_scanner() -> MarketUniverseScanner:
    global _scanner_instance
    if _scanner_instance is None:
        _scanner_instance = MarketUniverseScanner()
    return _scanner_instance
