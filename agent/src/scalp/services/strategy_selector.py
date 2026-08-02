"""Strategy selector matching market candidate + regime to strategy templates."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from src.scalp.services.strategy_registry import get_strategy_registry

logger = logging.getLogger(__name__)


class StrategySelector:
    @staticmethod
    def select_best_strategy(indicators: Dict[str, Any], regime: str, allowed_strategy_ids: List[str]) -> Optional[Dict[str, Any]]:
        registry = get_strategy_registry()
        best_setup: Optional[Dict[str, Any]] = None
        best_score = 0.0

        for strat_meta in registry.list_strategies():
            sid = strat_meta["id"]
            if allowed_strategy_ids and sid not in allowed_strategy_ids:
                continue

            strat_entry = registry.get_strategy(sid)
            if not strat_entry:
                continue

            mod = strat_entry["module"]
            result = mod.analyze(indicators, regime)

            if result and result.get("direction") in ("LONG", "SHORT"):
                score = float(result.get("setup_quality_score", 0.0))
                if score > best_score:
                    best_score = score
                    best_setup = result

        return best_setup
