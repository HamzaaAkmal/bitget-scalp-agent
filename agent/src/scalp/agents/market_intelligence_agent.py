"""Agent 1 — Market Intelligence Agent."""

from __future__ import annotations

import logging
from typing import Any, Dict

from src.scalp.services.coingecko_client import get_coingecko_client
from src.scalp.services.exa_deep_research import get_exa_research_service

logger = logging.getLogger(__name__)


class MarketIntelligenceAgent:
    def __init__(self) -> None:
        self.coingecko = get_coingecko_client()
        self.exa = get_exa_research_service()

    def analyze(self, symbol: str, coin_name: str = "") -> Dict[str, Any]:
        icon = self.coingecko.get_symbol_icon(symbol)
        research = self.exa.validate_candidate_events(symbol, coin_name)

        veto = research.get("event_veto", False)
        recommendation = "REJECT" if veto else "CONTINUE"

        return {
            "symbol": symbol,
            "coin_name": coin_name or symbol.replace("USDT", ""),
            "coin_icon": icon,
            "research_summary": research.get("research_summary", ""),
            "bullish_catalysts": research.get("bullish_catalysts", []),
            "bearish_catalysts": research.get("bearish_catalysts", []),
            "critical_risks": research.get("critical_risks", []),
            "source_count": len(research.get("sources", [])),
            "source_quality_score": 85.0,
            "freshness_score": 90.0,
            "research_confidence": research.get("confidence", 85.0),
            "event_veto": veto,
            "recommended_action": recommendation,
        }
