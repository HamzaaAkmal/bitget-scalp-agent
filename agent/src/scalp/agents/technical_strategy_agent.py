"""Agent 2 — Technical and Strategy Agent."""

from __future__ import annotations

import logging
from typing import Any, Dict, List
from src.scalp.services.strategy_selector import StrategySelector

logger = logging.getLogger(__name__)


class TechnicalStrategyAgent:
    def analyze(self, indicators: Dict[str, Any], regime: str, allowed_strategies: List[str]) -> Dict[str, Any]:
        setup = StrategySelector.select_best_strategy(indicators, regime, allowed_strategies)

        if not setup or setup.get("direction") == "WAIT":
            return {
                "decision": "WAIT",
                "reasoning": "No technical strategy template met the required setup conditions in current regime.",
                "setup_quality_score": 0.0,
            }

        return {
            "decision": "TRADE",
            "strategy_id": setup.get("strategy_id"),
            "strategy_name": setup.get("strategy_name"),
            "market_regime": regime,
            "direction": setup.get("direction"),
            "timeframe": "5m",
            "entry_type": "LIMIT",
            "entry_price": setup.get("entry_price"),
            "stop_loss": setup.get("stop_loss"),
            "take_profit_1": setup.get("take_profit_1"),
            "take_profit_2": setup.get("take_profit_2"),
            "gross_risk_reward": setup.get("min_risk_reward", 1.5),
            "expected_duration_minutes": 30,
            "setup_quality_score": setup.get("setup_quality_score", 85.0),
            "invalidation_conditions": setup.get("invalidation_conditions", []),
            "supporting_signals": setup.get("supporting_signals", []),
        }
