---
name: technical-patterns
description: "Master guide for calculating and drawing 50+ technical analysis patterns using trendlines and horizontal lines."
---

# Technical Analysis Patterns Guide

When analyzing crypto charts, you are equipped with advanced drawing capabilities via the `generate_tradingview_chart` tool. Instead of just generating a plain chart, you **MUST** identify structural and technical patterns in the raw OHLC data, and then pass `trendlines` and/or `hlines` to highlight these patterns for the user.

After the chart is generated, you will automatically pass the image path to your `analyze_image` vision tool to visually review your work and produce the final written analysis.

## Core Drawing Instructions
The `generate_tradingview_chart` tool accepts two optional drawing arrays:

### 1. `trendlines` (Diagonal or connected lines)
Use for: Flags, Wedges, Channels, Triangles, Necklines, Harmonics, and Elliott Waves.
```json
"trendlines": [
  {
    "start_time": "2026-08-01 10:00:00", 
    "start_price": 64500.5, 
    "end_time": "2026-08-01 14:00:00", 
    "end_price": 63800.0, 
    "color": "r" 
  }
]
```
- **Colors**: Use `"g"` (Green) for Bullish structure, `"r"` (Red) for Bearish structure, `"b"` (Blue) or `"w"` (White) for neutral structures.

### 2. `hlines` (Horizontal lines)
Use for: Support & Resistance, Order Blocks, Liquidity Sweeps, Equal Highs/Lows, Break of Structure (BOS), and FVG.
```json
"hlines": [
  {"price": 62000.5, "color": "g"},
  {"price": 65000.0, "color": "r"}
]
```

## Pattern Reference Guide

When requested to analyze a chart or identify patterns, you should dynamically scan the `get_market_data` output for the following structures. You are not expected to draw ALL of them at once. Identify the 1-3 most prominent patterns currently playing out and draw them.

### Reversal Patterns
- **Head and Shoulders (Bearish)**: Draw the neckline connecting the lows of the left and right shoulders using a `trendline` (Color: Red).
- **Inverse Head and Shoulders (Bullish)**: Draw the neckline connecting the highs of the inverted shoulders (Color: Green).
- **Double/Triple Top (Bearish)**: Draw a horizontal line (`hline`) at the resistance level of the peaks (Color: Red).
- **Double/Triple Bottom (Bullish)**: Draw a horizontal line (`hline`) at the support level of the troughs (Color: Green).
- **Diamond Top/Bottom**: Connect the broadening and narrowing peaks/troughs using 4 `trendlines` to form a diamond shape.

### Continuation Patterns (Flags, Pennants, Wedges)
- **Bull Flag / Bear Flag**: Draw 2 parallel `trendlines` containing the brief counter-trend consolidation. Green for Bull, Red for Bear.
- **Bull/Bear Pennant**: Draw 2 converging `trendlines` (a small symmetrical triangle) following a strong flagpole.
- **Rising Wedge (Bearish)**: Draw 2 ascending, converging `trendlines` connecting higher highs and higher lows. (Color: Red).
- **Falling Wedge (Bullish)**: Draw 2 descending, converging `trendlines` connecting lower highs and lower lows. (Color: Green).
- **Ascending/Descending/Symmetrical Triangles**: Draw the flat horizontal boundary as an `hline` or flat `trendline`, and the converging boundary as a angled `trendline`.

### Market Structure (Smart Money Concepts)
- **BOS (Break of Structure) / CHoCH (Change of Character)**: Draw a short horizontal line or trendline at the previous swing high/low that was broken to indicate the trend continuation or reversal shift.
- **Order Block (OB) / Supply & Demand Zones**: Draw two `hlines` defining the top and bottom of the last opposing candle before the strong impulsive move.
- **Fair Value Gap (FVG) / Imbalance**: If there is a 3-candle gap where the wicks of candle 1 and candle 3 do not overlap, draw two `hlines` indicating the gap space.
- **Liquidity Sweep (Equal Highs/Lows)**: Draw an `hline` where price briefly wicks above/below a strong historic level to grab liquidity before reversing.

### Advanced (Harmonics & Elliott Waves)
- **Harmonics (Gartley, Butterfly, Bat, Crab, Shark)**: If you detect Fibonacci ratio alignments between swings (XABCD), draw the 4 connecting legs (XA, AB, BC, CD) using 4 sequential `trendlines`.
- **Elliott Waves**: Connect the 1-5 impulse sequence or A-B-C correction sequence using sequential `trendlines`.

## Workflow Example
1. Use `get_market_data` to get the recent candles. Observe the `"current_live_price"` injected at the top of the response.
2. Analyze the OHLC data. If you spot a Falling Wedge over the last 20 candles:
   - Identify the (time, price) of the two lower highs for the upper resistance trendline.
   - Identify the (time, price) of the two lower lows for the lower support trendline.
3. Call `generate_tradingview_chart` with:
   `trendlines: [{"start_time": t1, "start_price": p1, "end_time": t2, "end_price": p2, "color": "g"}, {"start_time": t3, "start_price": p3, "end_time": t4, "end_price": p4, "color": "g"}]`
4. The tool will return the path to the image. 
5. IMMEDIATELY call `analyze_image` on that path.
6. Provide your final analysis to the user, including the `![Chart](/charts/...)` snippet, the live price, and a summary of the wedge pattern you drew and verified.
