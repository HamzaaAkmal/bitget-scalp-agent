"""CoinGlass Liquidation Heatmap tool for AI agent."""

from __future__ import annotations

import json
from typing import Any
from src.agent.tools import BaseTool


class CoinGlassHeatmapTool(BaseTool):
    """Tool for generating CoinGlass Liquidation Heatmap visual widget."""

    name = "get_liquidation_heatmap"
    description = (
        "Get live CoinGlass Crypto Futures Liquidation Heatmap visualization for a target coin/symbol "
        "(e.g., BTC, ETH, SOL, DOGE, XRP). Use this when the user asks to see liquidations, "
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
        pair = f"{clean_symbol}/USDT Futures"
        embed_url = f"https://www.coinglass.com/pro/futures/LiquidationHeatMap?symbol={clean_symbol}"

        return json.dumps(
            {
                "status": "success",
                "symbol": clean_symbol,
                "pair": pair,
                "embed_url": embed_url,
                "markdown_widget": f"Here is the live CoinGlass Liquidation Heatmap for **{pair}**:\n\n```coinglass-heatmap\nsymbol={clean_symbol}\n```",
                "summary": f"Fetched live CoinGlass Liquidation Heatmap for {pair}. Displaying live leverage liquidity clusters & liquidation intensity levels.",
            },
            ensure_ascii=False,
        )
