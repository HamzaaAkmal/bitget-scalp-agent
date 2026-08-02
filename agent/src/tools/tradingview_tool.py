"""Tool for generating a static chart screenshot for analysis."""

from __future__ import annotations

import json
import time
import urllib.request
import os
from typing import Any
import matplotlib
matplotlib.use('Agg')
import pandas as pd
import mplfinance as mpf

from src.agent.tools import BaseTool

class TradingViewChartTool(BaseTool):
    """Generate a static chart screenshot for the user."""

    name = "generate_tradingview_chart"
    description = (
        "Generate a static candlestick chart screenshot for a symbol. "
        "You can optionally supply 'trendlines' and 'hlines' to draw technical patterns "
        "(e.g., Wedges, Channels, Support/Resistance) directly on the chart. "
        "Use this tool when you need to show the exact chart you analyzed to the user. "
        "It returns a markdown snippet that you MUST include in your message."
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
                "enum": ["1m", "5m", "15m", "30m", "1h", "4h", "1d"],
                "description": "Chart timeframe/interval."
            },
            "category": {
                "type": "string",
                "enum": ["USDT-FUTURES", "SPOT"],
                "description": "Market category (default USDT-FUTURES).",
                "default": "USDT-FUTURES"
            },
            "trendlines": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "start_time": {"type": "string", "description": "YYYY-MM-DD HH:MM:SS"},
                        "end_time": {"type": "string", "description": "YYYY-MM-DD HH:MM:SS"},
                        "start_price": {"type": "number"},
                        "end_price": {"type": "number"},
                        "color": {"type": "string", "description": "e.g., 'r', 'g', 'b', 'yellow'"}
                    }
                },
                "description": "Draw arbitrary trend lines (e.g. for Wedges, Flags, Necklines)."
            },
            "hlines": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "price": {"type": "number"},
                        "color": {"type": "string"}
                    }
                },
                "description": "Draw horizontal lines (e.g. for Support/Resistance)."
            }
        },
        "required": ["symbol", "interval"]
    }
    repeatable = True

    def execute(self, **kwargs: Any) -> str:
        symbol = kwargs.get("symbol", "BTCUSDT").upper().replace("-", "")
        interval = kwargs.get("interval", "15m").lower()
        category = kwargs.get("category", "USDT-FUTURES").upper()
        
        # Bitget API expects granularity as 1m, 5m, 15m, 30m, 1H, 4H, 1D
        granularity = interval.replace("h", "H").replace("d", "D")
        
        url = f"https://api.bitget.com/api/v2/mix/market/candles?symbol={symbol}&granularity={granularity}&limit=100&productType={category}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
        except Exception as e:
            return f"Failed to fetch market data from Bitget: {str(e)}"
            
        if data.get("code") != "00000" or not data.get("data"):
            return f"Error from Bitget API: {data.get('msg')}"
            
        candles = data["data"]
        # Bitget candles format: [ts, open, high, low, close, base_vol, quote_vol]
        df = pd.DataFrame(candles, columns=["timestamp", "open", "high", "low", "close", "base_vol", "quote_vol"])
        df["timestamp"] = pd.to_datetime(pd.to_numeric(df["timestamp"]), unit='ms')
        for col in ["open", "high", "low", "close", "base_vol"]:
            df[col] = pd.to_numeric(df[col])
            
        df = df.set_index("timestamp").sort_index()
        
        # Rename base_vol to volume for mplfinance
        df = df.rename(columns={"base_vol": "volume"})
        
        # Generate chart
        filename = f"{symbol}_{interval}_{int(time.time())}.png"
        # The tool script is in agent/src/tools/
        # Root is agent/../../ -> Vibe-Trading
        filepath = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../frontend/public/charts", filename))
        
        # Make sure directory exists
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        mc = mpf.make_marketcolors(up='#00b061', down='#f23645', inherit=True)
        s = mpf.make_mpf_style(base_mpf_style='nightclouds', marketcolors=mc)
        
        plot_kwargs = {
            'type': 'candle', 
            'style': s, 
            'volume': True, 
            'savefig': filepath, 
            'title': f"{symbol} ({interval})"
        }
        
        trendlines = kwargs.get("trendlines", [])
        if trendlines:
            alines_list = []
            alines_colors = []
            for tl in trendlines:
                try:
                    t1, t2 = pd.to_datetime(tl["start_time"]), pd.to_datetime(tl["end_time"])
                    p1, p2 = float(tl["start_price"]), float(tl["end_price"])
                    c = tl.get("color", "w")
                    alines_list.append([(t1, p1), (t2, p2)])
                    alines_colors.append(c)
                except Exception:
                    pass
            if alines_list:
                plot_kwargs['alines'] = dict(alines=alines_list, colors=alines_colors, linewidths=2)
                
        hlines_input = kwargs.get("hlines", [])
        if hlines_input:
            hlines_list = []
            hlines_colors = []
            for hl in hlines_input:
                try:
                    hlines_list.append(float(hl["price"]))
                    hlines_colors.append(hl.get("color", "w"))
                except Exception:
                    pass
            if hlines_list:
                plot_kwargs['hlines'] = dict(hlines=hlines_list, colors=hlines_colors, linestyle='dashed')
        
        # Always plot standard MAs for context if requested or default
        plot_kwargs['mav'] = (9, 21)
        
        try:
            mpf.plot(df, **plot_kwargs)
        except Exception as e:
            return f"Failed to generate chart image: {str(e)}"
            
        snippet = f"\n![{symbol} Chart](/charts/{filename})\n"
        
        return (
            "Successfully generated static chart screenshot with your technical patterns. "
            f"The image is saved at {filepath}. "
            "To display the chart to the user, you MUST copy and paste the following snippet "
            f"exactly as it is into your message:\n\n{snippet}\n\n"
            "IMPORTANT NEXT STEP: You MUST now use the `analyze_image` tool to visually review "
            f"this generated chart ({filepath}), analyze the technical patterns you drew, "
            "and incorporate those insights into your final text message."
        )
