"""Curated read/write classification for official Bitget MCP verbs."""

from __future__ import annotations

from src.live.classification import ToolClass

BITGET_TOOL_CLASS: dict[str, ToolClass] = {
    "discover": ToolClass.READ,
    "market": ToolClass.READ,
    "account_overview": ToolClass.READ,
    "order": ToolClass.WRITE,
    "position": ToolClass.WRITE,
    "strategy_order": ToolClass.WRITE,
    "account_config": ToolClass.WRITE,
}

