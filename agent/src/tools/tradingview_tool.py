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

def extend_trendline(
    t1: pd.Timestamp, p1: float, t2: pd.Timestamp, p2: float, t_end: pd.Timestamp,
    lower_bound: float = 0.0, upper_bound: float = 1e9
) -> list[tuple[pd.Timestamp, float]]:
    """Extend a trendline segment straight across the chart, clamping Y values to visible price bounds."""
    try:
        dt1 = t1.timestamp()
        dt2 = t2.timestamp()
        dt_end = t_end.timestamp()
        if dt2 == dt1:
            return [(t1, p1), (t_end, p2)]
        slope = (p2 - p1) / (dt2 - dt1)
        p_end = p1 + slope * (dt_end - dt1)
        
        # Clamp p_end so lines never cross into volume panel or escape top
        if lower_bound > 0 and p_end < lower_bound:
            p_end = lower_bound
        if upper_bound > 0 and p_end > upper_bound:
            p_end = upper_bound
            
        return [(t1, p1), (t_end, float(p_end))]
    except Exception:
        return [(t1, p1), (t2, p2)]


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
            "auto_patterns": {
                "type": "boolean",
                "description": "If true, automatically detect and draw perfectly accurate technical patterns (support/resistance, trendlines) on the chart. Recommended.",
                "default": True
            },
            "pattern_name": {
                "type": "string",
                "description": "Optional specific pattern to draw: 'Head & Shoulders', 'Inverse Head & Shoulders', 'Double Top', 'Double Bottom', 'Ascending Triangle', 'Descending Triangle', 'Symmetrical Triangle', 'Bull Flag', 'Bear Flag', 'Bull Pennant', 'Bear Pennant', 'Rising Wedge', 'Falling Wedge', 'Cup & Handle', 'Rectangle'."
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
        
        granularity = interval.replace("h", "H").replace("d", "D")
        
        # Dynamic bar limit based on timeframe for bold, readable candle display
        interval_limits = {
            "1m": 60, "5m": 60, "15m": 60, "30m": 50,
            "1h": 50, "4h": 50, "1d": 45, "1w": 30
        }
        limit = kwargs.get("limit") or interval_limits.get(interval, 45)
        
        url = f"https://api.bitget.com/api/v2/mix/market/candles?symbol={symbol}&granularity={granularity}&limit={limit}&productType={category}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
        except Exception as e:
            return f"Failed to fetch market data from Bitget: {str(e)}"
            
        if data.get("code") != "00000" or not data.get("data"):
            return f"Error from Bitget API: {data.get('msg')}"
            
        candles = data["data"]
        df = pd.DataFrame(candles, columns=["timestamp", "open", "high", "low", "close", "base_vol", "quote_vol"])
        df["timestamp"] = pd.to_datetime(pd.to_numeric(df["timestamp"]), unit='ms')
        for col in ["open", "high", "low", "close", "base_vol"]:
            df[col] = pd.to_numeric(df[col])
            
        df = df.set_index("timestamp").sort_index()
        df = df.rename(columns={"base_vol": "volume"})
        
        # Add 3 padding bars to the right side so candles don't touch the right wall
        if len(df) >= 2:
            freq = df.index[-1] - df.index[-2]
            future_dates = [df.index[-1] + freq * i for i in range(1, 4)]
            pad_df = pd.DataFrame(index=future_dates, columns=df.columns).astype(df.dtypes)
            df_plot = pd.concat([df, pad_df])
        else:
            df_plot = df
        
        filename = f"{symbol}_{interval}_{int(time.time())}.png"
        filepath = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../frontend/public/charts", filename))
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        mc = mpf.make_marketcolors(
            up='#089981', down='#f23645',
            edge={'up': '#089981', 'down': '#f23645'},
            wick={'up': '#089981', 'down': '#f23645'},
            volume={'up': '#089981', 'down': '#f23645'},
            inherit=True
        )
        s = mpf.make_mpf_style(
            base_mpf_style='nightclouds',
            marketcolors=mc,
            facecolor='#131722',
            figcolor='#0b0e14',
            gridcolor='#2a2e39',
            gridstyle=':'
        )
        
        min_p = float(df["low"].min())
        max_p = float(df["high"].max())
        p_range = max_p - min_p if max_p > min_p else 1.0
        lower_bound = min_p - (p_range * 0.03)
        upper_bound = max_p + (p_range * 0.03)
        
        # High resolution Full HD (1920x1080) setup
        plot_kwargs = {
            'type': 'candle', 
            'style': s, 
            'volume': True, 
            'figsize': (16, 9),
            'ylim': (lower_bound, upper_bound),
            'mav': (9, 21),
            'returnfig': True
        }
        
        trendlines = kwargs.get("trendlines", [])
        hlines_input = kwargs.get("hlines", [])
        
        alines_list = []
        alines_colors = []
        hlines_list = []
        hlines_colors = []
        
        t_end = df_plot.index[-1]
        
        # User manual lines
        if trendlines:
            for tl in trendlines:
                try:
                    t1, t2 = pd.to_datetime(tl["start_time"]), pd.to_datetime(tl["end_time"])
                    p1, p2 = float(tl["start_price"]), float(tl["end_price"])
                    c = tl.get("color", "#29b6f6")
                    ext = extend_trendline(t1, p1, t2, p2, t_end)
                    alines_list.append(ext)
                    alines_colors.append(c)
                except Exception:
                    pass
                    
        if hlines_input:
            for hl in hlines_input:
                try:
                    hlines_list.append(float(hl["price"]))
                    hlines_colors.append(hl.get("color", "#ffb74d"))
                except Exception:
                    pass
                    
        # Auto technical analysis patterns overlay (15 Masterclass Patterns)
        target_pattern = kwargs.get("pattern_name")
        auto_patterns = kwargs.get("auto_patterns", True)
        
        detected_conf = None
        detected_pname = None
        
        if auto_patterns or target_pattern:
            try:
                from src.tools.pattern_tool import detect_all_15_patterns, support_resistance_zones, compute_atr
                
                # Render ATR-based Support/Resistance Zones (Shaded Rectangles)
                atr = compute_atr(df["high"], df["low"], df["close"])
                zones = support_resistance_zones(df["high"], df["low"], df["close"], atr, window=3)
                # Instead of standard hlines, we will draw shaded spans later on axlist[0]
                
                # Check for textbook 15-pattern matches
                patterns = detect_all_15_patterns(df, window=4)
                drawn_pattern = False
                
                if patterns:
                    for pat in patterns:
                        pname = pat.get("pattern_name", "")
                        if target_pattern and target_pattern.lower() not in pname.lower():
                            continue
                            
                        detected_conf = pat.get("confidence")
                        detected_pname = pname
                        
                        p_lines = pat.get("lines", [])
                        p_cols = pat.get("colors", ["#ff5252", "#00e676"])
                        
                        # 1. Render explicit lines (e.g. Wedges, Triangles, Channels)
                        for line_spec, col in zip(p_lines, p_cols):
                            if isinstance(line_spec, tuple) and len(line_spec) == 2 and line_spec[0] == "hline":
                                hlines_list.append(float(line_spec[1]))
                                hlines_colors.append(col)
                            elif isinstance(line_spec, tuple) and len(line_spec) == 4:
                                t1, p1, t2, p2 = line_spec
                                ext = extend_trendline(t1, p1, t2, p2, t_end, lower_bound, upper_bound)
                                alines_list.append(ext)
                                alines_colors.append(col)
                                
                        # 2. Render connected points (e.g. Head & Shoulders, Double Tops)
                        p_points = pat.get("points", [])
                        if p_points:
                            alines_list.append(p_points)
                            alines_colors.append(pat.get("color", "#ff00ff"))
                            
                        # 3. Render Neckline
                        neckline = pat.get("neckline")
                        if neckline is not None:
                            hlines_list.append(float(neckline))
                            hlines_colors.append("#ffb74d") # Orange neckline
                            
                        drawn_pattern = True
                        break # Draw the primary pattern
                        
                if target_pattern and not drawn_pattern:
                    pass
                elif not drawn_pattern:
                    pass # We skip generic lines now to rely entirely on strictly validated zones and patterns
                    # Smart AI Trendline Fitting (Default Resistance & Support)
                    pv = find_peaks_valleys(df["close"], window=4)
                    peaks = pv.get("peaks", [])
                    valleys = pv.get("valleys", [])
                    values = df["close"].values
                    n = len(df)
                    
                    # 1. Upper Resistance Line (Red) - Highest early peak -> highest late peak
                    if len(peaks) >= 2:
                        early_peaks = [p for p in peaks if p < n * 0.65]
                        late_peaks = [p for p in peaks if p >= n * 0.35]
                        
                        if early_peaks and late_peaks:
                            p1_idx = max(early_peaks, key=lambda i: values[i])
                            late_candidates = [p for p in late_peaks if p > p1_idx]
                            p2_idx = late_candidates[0] if late_candidates else late_peaks[-1]
                            
                            if p1_idx != p2_idx:
                                t1, p1 = df_plot.index[p1_idx], float(values[p1_idx])
                                t2, p2 = df_plot.index[p2_idx], float(values[p2_idx])
                                ext_res = extend_trendline(t1, p1, t2, p2, t_end, lower_bound, upper_bound)
                                alines_list.append(ext_res)
                                alines_colors.append('#ff5252')
                                
                    # 2. Lower Support Line (Green) - Flat horizontal or ascending support
                    if len(valleys) >= 2:
                        early_valleys = [v for v in valleys if v < n * 0.65]
                        late_valleys = [v for v in valleys if v >= n * 0.35]
                        
                        if early_valleys and late_valleys:
                            v1_idx = min(early_valleys, key=lambda i: values[i])
                            late_v_candidates = [v for v in late_valleys if v > v1_idx]
                            v2_idx = late_v_candidates[0] if late_v_candidates else late_valleys[-1]
                            
                            t1, p1 = df_plot.index[v1_idx], float(values[v1_idx])
                            t2, p2 = df_plot.index[v2_idx], float(values[v2_idx])
                            
                            min_v = float(min(values[valleys]))
                            if abs(p1 - p2) / p1 < 0.04 or abs(p2 - min_v) / min_v < 0.025:
                                alines_list.append([(t1, min_v), (t_end, min_v)])
                                alines_colors.append('#00e676')
                            else:
                                ext_sup = extend_trendline(t1, p1, t2, p2, t_end, lower_bound, upper_bound)
                                alines_list.append(ext_sup)
                                alines_colors.append('#00e676')

            except Exception:
                pass

        # Filter hlines to visible candle price range to keep layout tight and clean
        filtered_hlines = []
        filtered_colors = []
        for hl_val, hl_col in zip(hlines_list, hlines_colors):
            try:
                val = float(hl_val)
                if lower_bound <= val <= upper_bound:
                    filtered_hlines.append(val)
                    filtered_colors.append(hl_col)
            except Exception:
                pass

        if alines_list:
            plot_kwargs['alines'] = dict(alines=alines_list, colors=alines_colors, linewidths=1.5)
        if filtered_hlines:
            plot_kwargs['hlines'] = dict(hlines=filtered_hlines, colors=filtered_colors, linestyle='dashed', linewidths=1.2)
        
        try:
            fig, axlist = mpf.plot(df_plot, **plot_kwargs)
            ax = axlist[0]
            
            # Draw shaded ATR Support/Resistance Zones
            if auto_patterns and 'zones' in locals():
                for z in zones.get("resistance", []):
                    ax.axhspan(z["bottom"], z["top"], color='#ff5252', alpha=0.15, lw=0)
                for z in zones.get("support", []):
                    ax.axhspan(z["bottom"], z["top"], color='#00e676', alpha=0.15, lw=0)
                    
            # Annotate Pattern Confidence
            if detected_conf and detected_pname:
                score_str = f"{detected_conf:.0f}% CONFIDENCE"
                ax.text(0.02, 0.95, f"{detected_pname}\n{score_str}", 
                        transform=ax.transAxes, color='#ffd700', fontsize=12, fontweight='bold',
                        bbox=dict(facecolor='#000000', alpha=0.6, edgecolor='none', pad=5))
            
            # Clean centered title outside plot area
            fig.suptitle(
                f"{symbol} ({interval})  —  Real-Time Technical Analysis",
                color='#ffffff',
                fontsize=18,
                fontweight='bold',
                y=0.96
            )
            # Give proper margins on all 4 sides so right side graph & labels are 100% complete
            fig.subplots_adjust(left=0.06, right=0.94, top=0.90, bottom=0.10)
            
            fig.savefig(filepath, dpi=200, facecolor='#0b0e14', edgecolor='none')
            import matplotlib.pyplot as plt
            plt.close(fig)
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
