"""Tool for fetching crypto market data and trends via CoinGecko."""

from __future__ import annotations

import json
from typing import Any

from src.agent.tools import BaseTool
from src.scalp.services.coingecko_client import get_coingecko_client

class CoinGeckoTool(BaseTool):
    """Fetch cryptocurrency market data, trends, and prices using CoinGecko."""

    name = "coingecko_market_data"
    description = (
        "Fetch real-time cryptocurrency market data, trends, and metadata using CoinGecko. "
        "Use this for general market analysis, fetching trending coins, or getting specific coin data."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["trending", "markets", "metadata"],
                "description": "The action to perform: 'trending' for top trending coins, 'markets' for top coins by market cap, 'metadata' for specific coin info."
            },
            "limit": {
                "type": "integer",
                "description": "Number of results to return for 'markets' action (max 100). Default 10.",
                "default": 10
            },
            "coin_id": {
                "type": "string",
                "description": "The CoinGecko coin ID (e.g., 'bitcoin') required for 'metadata' action."
            }
        },
        "required": ["action"]
    }
    repeatable = True

    def execute(self, **kwargs: Any) -> str:
        client = get_coingecko_client()
        action = kwargs.get("action")
        
        try:
            if action == "trending":
                data = client.get_trending_coins()
            elif action == "markets":
                limit = int(kwargs.get("limit", 10))
                data = client.get_coins_markets(limit=limit)
            elif action == "metadata":
                coin_id = kwargs.get("coin_id")
                if not coin_id:
                    return json.dumps({"error": "coin_id is required for metadata action."})
                data = client.get_coin_metadata(coin_id)
            else:
                return json.dumps({"error": f"Unknown action: {action}"})
                
            return json.dumps(data, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)})
