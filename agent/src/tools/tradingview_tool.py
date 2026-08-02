"""Tool for rendering an interactive TradingView chart inside the chat."""

from __future__ import annotations

import json
from typing import Any

from src.agent.tools import BaseTool

class TradingViewChartTool(BaseTool):
    """Instruct the LLM how to output a TradingView Advanced Chart in its message."""

    name = "generate_tradingview_chart"
    description = (
        "Use this tool when you need to show an interactive TradingView chart to the user. "
        "It will provide you with a markdown snippet. You MUST include that exact snippet "
        "in your final message to the user for the chart to render properly."
    )
    parameters = {
        "type": "object",
        "properties": {
            "symbol": {
                "type": "string",
                "description": "The trading pair symbol (e.g., BTCUSDT, ETHUSDT)."
            },
            "interval": {
                "type": "string",
                "enum": ["1m", "3m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"],
                "description": "Chart timeframe/interval."
            },
            "category": {
                "type": "string",
                "enum": ["USDT-FUTURES", "SPOT"],
                "description": "Market category (default USDT-FUTURES).",
                "default": "USDT-FUTURES"
            }
        },
        "required": ["symbol", "interval"]
    }
    repeatable = True

    def execute(self, **kwargs: Any) -> str:
        symbol = kwargs.get("symbol", "BTCUSDT").upper().replace("-", "")
        interval = kwargs.get("interval", "15m").lower()
        category = kwargs.get("category", "USDT-FUTURES").upper()
        
        payload = {
            "symbol": symbol,
            "interval": interval,
            "category": category
        }
        
        snippet = f"\n```tradingview\n{json.dumps(payload, indent=2)}\n```\n"
        
        return (
            "Successfully generated TradingView chart block. "
            "To display the chart to the user, you MUST copy and paste the following snippet "
            f"exactly as it is into your message:\n\n{snippet}"
        )
