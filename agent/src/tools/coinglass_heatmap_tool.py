"""CoinGlass Liquidation Heatmap tool for AI agent."""

from __future__ import annotations

from typing import Any
from src.agent.tools import BaseTool


class CoinGlassHeatmapTool(BaseTool):
    """Tool for generating CoinGlass Liquidation Heatmap visual widget."""

    name = "get_liquidation_heatmap"
    description = (
        "Get the live interactive CoinGlass Liquidation Heatmap widget for a cryptocurrency symbol "
        "(e.g., BTC, ETH, SOL, DOGE). Use this tool when the user asks to see live liquidations, "
        "liquidation heatmap, or leverage clusters."
    )
    parameters = {
        "type": "object",
        "properties": {
            "symbol": {
                "type": "string",
                "description": "Cryptocurrency symbol (e.g., BTC, ETH, SOL, BTCUSDT).",
            },
        },
        "required": ["symbol"],
    }
    repeatable = True
    is_readonly = True

    def execute(self, symbol: str, **kwargs: Any) -> str:
        clean_symbol = symbol.strip().upper().replace("USDT", "") or "BTC"
        snippet = f"![{clean_symbol} Liquidation Heatmap](https://www.coinglass.com/pro/futures/LiquidationHeatMap?symbol={clean_symbol})"

        return (
            f"Successfully fetched live CoinGlass Liquidation Heatmap for {clean_symbol}/USDT Futures.\n"
            "To display the interactive heatmap widget to the user, you MUST copy and paste the following markdown snippet "
            f"exactly as it is into your response message:\n\n{snippet}\n"
        )
