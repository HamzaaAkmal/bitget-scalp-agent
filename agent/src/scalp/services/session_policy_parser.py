"""Natural-language session policy parser and warning generator."""

from __future__ import annotations

import logging
import re
from typing import Any
from pydantic import BaseModel

from src.scalp.models.session_policy import (
    SessionPolicy,
    AutonomyMode,
    TargetClassification,
    PolicyWarning,
    create_default_policy,
)
from src.providers.llm import build_llm

logger = logging.getLogger(__name__)


def parse_session_mission(user_mission: str) -> SessionPolicy:
    """Convert natural-language prompt into a validated SessionPolicy."""
    text = (user_mission or "").strip()
    if not text:
        return create_default_policy()

    policy = create_default_policy()
    lower = text.casefold()

    # Regex extraction fallback / fast path
    # 1. Autonomy mode
    autonomy = AutonomyMode.GUARDED_AUTOPILOT
    if "copilot" in lower or "ask before" in lower or "confirm before" in lower:
        autonomy = AutonomyMode.COPILOT
    elif "full" in lower or "fully autonomous" in lower:
        autonomy = AutonomyMode.FULL_AUTONOMOUS
    policy.autonomy_mode = autonomy

    # 2. Capital
    cap_match = re.search(r"\b(?:use|allocate|capital|with|starting)\s*\$?\s*(\d+(?:\.\d+)?)\s*(?:usdt|usd|dollars?)?\b", lower)
    if cap_match:
        try:
            policy.allocated_capital = max(1.0, float(cap_match.group(1)))
        except ValueError:
            pass

    # 3. Target profit / final balance
    target_match = re.search(r"\b(?:earning|earn|target|profit|make|reach)\s*\$?\s*(\d+(?:\.\d+)?)\s*(?:usdt|usd)?\b", lower)
    if target_match:
        try:
            policy.target_profit = max(0.5, float(target_match.group(1)))
        except ValueError:
            pass

    turn_match = re.search(r"\bturn\s*\$?\s*(\d+(?:\.\d+)?)\s*into\s*\$?\s*(\d+(?:\.\d+)?)\b", lower)
    if turn_match:
        try:
            alloc = float(turn_match.group(1))
            final_bal = float(turn_match.group(2))
            policy.allocated_capital = alloc
            policy.target_final_balance = final_bal
            policy.target_profit = max(0.1, final_bal - alloc)
        except ValueError:
            pass
    else:
        policy.target_final_balance = policy.allocated_capital + policy.target_profit

    # 4. Stop loss (max session loss)
    loss_match = re.search(r"\b(?:losing|lose|stop after losing|max loss|stop loss)\s*\$?\s*(\d+(?:\.\d+)?)\s*(?:usdt|usd)?\b", lower)
    if loss_match:
        try:
            policy.maximum_session_loss = max(0.5, float(loss_match.group(1)))
        except ValueError:
            pass

    # 5. Risk per trade
    risk_match = re.search(r"\brisk\s*(?:no more than|max)?\s*\$?\s*(\d+(?:\.\d+)?)\s*(?:usdt|usd)?\s*per trade\b", lower)
    if risk_match:
        try:
            policy.risk_per_trade_usdt = max(0.1, float(risk_match.group(1)))
            policy.risk_per_trade_percent = round((policy.risk_per_trade_usdt / policy.allocated_capital) * 100, 2)
        except ValueError:
            pass

    # 6. Duration
    dur_match = re.search(r"\b(\d+)\s*(?:hours?|hrs?|h)\b", lower)
    if dur_match:
        try:
            policy.maximum_duration_minutes = min(1440, max(15, int(dur_match.group(1)) * 60))
        except ValueError:
            pass

    # 7. Leverage
    lev_match = re.search(r"\b(\d{1,2})\s*x\b", lower)
    if lev_match:
        try:
            policy.maximum_leverage = min(5, max(1, int(lev_match.group(1))))
        except ValueError:
            pass

    # 8. Margin mode
    if "cross" in lower:
        policy.margin_mode = "cross"
    else:
        policy.margin_mode = "isolated"

    # 9. Symbols
    symbols = []
    for sym in ["BTC", "ETH", "SOL", "DOGE", "PEPE", "XRP", "ADA", "AVAX", "LINK", "SUI"]:
        if sym in text.upper():
            symbols.append(f"{sym}USDT")
    if symbols:
        policy.allowed_symbols = list(set(symbols))

    # Evaluate target classification & warnings
    target_ratio = policy.target_profit / policy.allocated_capital
    if target_ratio <= 0.15:
        policy.target_classification = TargetClassification.CONSERVATIVE
    elif target_ratio <= 0.35:
        policy.target_classification = TargetClassification.MODERATE
    elif target_ratio <= 1.0:
        policy.target_classification = TargetClassification.AGGRESSIVE
    else:
        policy.target_classification = TargetClassification.EXTREMELY_AGGRESSIVE

    warnings: list[PolicyWarning] = []

    if target_ratio >= 1.0:
        warnings.append(
            PolicyWarning(
                level="critical",
                code="EXTREME_PROFIT_TARGET",
                message=f"Targeting +{target_ratio * 100:.0f}% profit ({policy.target_profit} USDT on {policy.allocated_capital} USDT capital) in a single short session is extremely high-risk and statistically improbable under strict risk limits.",
                impact="The deterministic risk engine will NEVER weaken stop-loss or leverage limits to chase an aggressive target.",
            )
        )
    elif target_ratio >= 0.5:
        warnings.append(
            PolicyWarning(
                level="warning",
                code="AGGRESSIVE_PROFIT_TARGET",
                message=f"Targeting +{target_ratio * 100:.0f}% profit requires multi-trade compound edge. Risk engine will halt trading if max loss limit ({policy.maximum_session_loss} USDT) is hit first.",
                impact="Session may timeout or stop at max loss before reaching target profit.",
            )
        )

    if policy.maximum_session_loss >= policy.allocated_capital * 0.5:
        warnings.append(
            PolicyWarning(
                level="warning",
                code="HIGH_SESSION_DRAWDOWN_LIMIT",
                message=f"Session loss limit ({policy.maximum_session_loss} USDT) allows for >50% drawdown of allocated capital.",
                impact="Consider reducing session loss limit to preserve capital.",
            )
        )

    policy.warnings = warnings
    return policy
