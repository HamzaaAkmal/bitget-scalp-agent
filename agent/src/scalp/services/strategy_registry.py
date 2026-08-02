"""Strategy template registry."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from src.scalp.strategies import (
    ema_vwap_pullback,
    breakout_retest,
    liquidity_sweep_reversal,
    momentum_continuation,
    range_mean_reversion,
    volume_expansion,
    funding_oi_divergence,
)

logger = logging.getLogger(__name__)

STRATEGY_MODULES = [
    ema_vwap_pullback,
    breakout_retest,
    liquidity_sweep_reversal,
    momentum_continuation,
    range_mean_reversion,
    volume_expansion,
    funding_oi_divergence,
]


class StrategyRegistry:
    def __init__(self) -> None:
        self._strategies: Dict[str, Any] = {}
        self._init_registry()

    def _init_registry(self) -> None:
        for mod in STRATEGY_MODULES:
            sid = getattr(mod, "STRATEGY_ID")
            self._strategies[sid] = {
                "id": sid,
                "name": getattr(mod, "STRATEGY_NAME"),
                "version": getattr(mod, "STRATEGY_VERSION"),
                "eligible_regimes": getattr(mod, "ELIGIBLE_REGIMES", []),
                "module": mod,
            }

    def list_strategies(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": meta["id"],
                "name": meta["name"],
                "version": meta["version"],
                "eligible_regimes": [r.value if hasattr(r, "value") else str(r) for r in meta["eligible_regimes"]],
            }
            for meta in self._strategies.values()
        ]

    def get_strategy(self, strategy_id: str) -> Dict[str, Any] | None:
        return self._strategies.get(strategy_id)


_registry_instance: StrategyRegistry | None = None


def get_strategy_registry() -> StrategyRegistry:
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = StrategyRegistry()
    return _registry_instance
