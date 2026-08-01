---
name: trade-journal
description: Analyze a user's trade journal (CSV/Excel broker export). Parses Tonghuashun, Eastmoney, Futu, and generic formats, produces a trading profile and 4 behavior diagnostics (disposition effect, overtrading, chasing, anchoring). Use the `analyze_trade_journal` tool.
category: tool
---
# Trade Journal Analysis

## Purpose

Users upload broker trade exports and get an honest, data-grounded portrait
of their own trading. Two layers are live:

- **Profile** — holding days, frequency, win rate, PnL ratio, cumulative PnL,
  max drawdown, top symbols, market/hourly distribution.
- **Behavior diagnostics** — 4 biases, each with severity (low/medium/high)
  and numeric evidence: disposition effect, overtrading, chasing momentum,
  anchoring.

Strategy extraction → backtest bridge lands in Phase 4c.

Supported formats (auto-detected):
- **Tonghuashun** — A-share CSV, typically GBK-encoded
- **Eastmoney** — A-share CSV, typically GBK-encoded
- **Futu** — HK/US CSV, UTF-8
- **Generic** — any CSV with columns like `datetime/symbol/side/qty/price`

## Usage

**Call the `analyze_trade_journal` tool directly. Never run Python from bash.**

```
analyze_trade_journal(file_path="uploads/xxx.csv")
analyze_trade_journal(file_path="uploads/xxx.csv", analysis_type="profile")
analyze_trade_journal(file_path="uploads/xxx.csv", filter_expr="2026-01 to 2026-03")
analyze_trade_journal(file_path="uploads/xxx.csv", filter_expr="symbol=600519.SH")
analyze_trade_journal(file_path="uploads/xxx.csv", filter_expr="market=china_a")
```

`analysis_type`:
- `full` (default) — profile + behavior (strategy still placeholder)
- `profile` — profile metrics only (fastest)
- `behavior` — 4 behavior diagnostics only
- `strategy` — Phase 4c placeholder

`filter_expr` (optional):
- Date range: `"YYYY-MM to YYYY-MM"` or `"YYYY-MM-DD to YYYY-MM-DD"`
- Symbol: `"symbol=600519.SH"` (exact match on qualified symbol)
- Market: `"market=china_a|us|hk|crypto"`

## Return shape (profile subset)

```json
{
  "status": "ok",
  "file": "xxx.csv",
  "format_detected": "tonghuashun",
  "total_records": 326,
  "date_range": "2026-01-06 ~ 2026-03-28",
  "symbols_count": 42,
  "market": "china_a",
  "profile": {
    "total_trades": 326,
    "total_roundtrips": 118,
    "avg_holding_days": 3.2,
    "trade_frequency_per_week": 4.1,
    "win_rate": 0.48,
    "profit_loss_ratio": 1.35,
    "total_pnl": 18240.55,
    "max_drawdown": -9820.10,
    "top_symbols": [{"symbol": "600519.SH", "trades": 14, "total_amount": 1.02e6}, ...],
    "market_distribution": {"china_a": 326},
    "hourly_distribution": {9: 52, 10: 84, ...},
    "roundtrips_sample": [{"symbol": "600519.SH", "buy_dt": "...", "sell_dt": "...", "pnl": 3400.1, "pnl_pct": 0.021, "hold_days": 2.5}, ...]
  }
}
```

Note: PnL uses FIFO lot matching; unmatched open positions are excluded from
win rate / PnL ratio (only closed round-trips count).

## Presenting results to the user

Produce a **single markdown report** in English. Lead with the
top-line numbers, then section-by-section. Keep it dense — this is retail
readers skimming on a phone.

### Report template

```
## Your Trading Profile - {date_range}

**Overview**
- Trades: {total_trades} ({total_roundtrips} complete round trips)
- Average holding period: {avg_holding_days} days
- Trading frequency: {trade_frequency_per_week} trades/week
- Win rate: {win_rate:.0%}
- Profit/loss ratio: {profit_loss_ratio}
- Cumulative PnL: {total_pnl}
- Max drawdown: {max_drawdown}

**Most-Traded Symbols** (top 5)
| Symbol | Trades | Turnover |
|------|------|--------|
| ... | ... | ... |

**Market Distribution**
{market_distribution}

**Trading Hours**
{hourly_distribution - highlight peak hours}

**Short Observation**
Write 1-2 data-based sentences. Mention overtrading, narrow symbol concentration, or time-of-day clustering if present.
```

Guidance:
- If `win_rate < 0.4` AND `profit_loss_ratio < 1.0` → explicit warning: losing
  on both win rate and payoff. Ask whether they want behavior diagnostics
  (Phase 4b) or a cooling-off reality check.
- If `avg_holding_days < 1` AND `trade_frequency_per_week > 15` → flag
  intraday-heavy pattern, note that minute-level backtest would be better.
- If `symbols_count <= 3` → concentration risk; ask if they want a sector-
  diversification check.

## Follow-up dialogue

After the initial report, users typically ask:
- **Time-slice**: "How did March perform?" -> re-call with `filter_expr="2026-03-01 to 2026-03-31"`.
- **Symbol deep-dive**: "How much did I make on 600519.SH?" -> `filter_expr="symbol=600519.SH"`.
- **Market split**: "Split HK and US trades" -> two calls, `market=hk` and `market=us`.
- **Hypothetical** ("What if I used a strict -5% stop loss?") -> Phase 4b feature; for now tell the
  user this is on the roadmap.

Do NOT re-upload — the file path is still valid for subsequent tool calls
in the same session.

## Error handling

- `File not found` / `Unsupported extension` — ask user to re-upload.
- `Unrecognized trade journal format` — share the detected columns back to
  the user and ask them to rename the key columns to: `datetime, symbol,
  side, quantity, price, amount, fee` (generic fallback).
- `No trade records parsed` — likely empty file or header-only; ask user to
  confirm the export contains actual fills.

## Behavior diagnostics (shape)

Under `result["behavior"]`:

```json
{
  "disposition_effect": {
    "severity": "high",
    "ratio_loss_to_win_hold": 1.69,
    "avg_winner_hold_days": 7.4,
    "avg_loser_hold_days": 12.5,
    "evidence": "Losing roundtrips held 12.5d vs winning 7.4d (ratio 1.69). Classic disposition pattern."
  },
  "overtrading": {
    "severity": "high",
    "busy_day_avg_pnl": -2632,
    "quiet_day_avg_pnl": 759,
    "evidence": "On busy days (≥3 trades) avg PnL -2632; on quiet days (≤1) avg PnL +759. High activity hurts returns."
  },
  "chasing_momentum": {
    "severity": "medium",
    "chase_ratio": 0.5,
    "buys_evaluated": 4,
    "evidence": "2/4 buys (50%) came after a >3% price run-up in the same symbol. Some chasing tendency."
  },
  "anchoring": {
    "severity": "high",
    "anchored_symbol_ratio": 0.83,
    "symbols_evaluated": 6,
    "anchored_symbols": [...],
    "evidence": "5/6 frequently-traded symbols stayed in a narrow price band (CV<5%). Strong anchoring."
  }
}
```

### Detection logic (for user-facing explanation)

| Bias | Metric | Medium | High |
|------|--------|--------|------|
| **Disposition effect** | avg_loser_hold / avg_winner_hold | ≥ 1.2 | ≥ 1.5 |
| **Overtrading** | (quiet − busy) / \|quiet\| day-PnL gap | ≥ 0.3 | ≥ 1.0 |
| **Chasing** | fraction of buys after 3-trade rolling +3% move | ≥ 40% | ≥ 60% |
| **Anchoring** | fraction of ≥5-trade symbols with price CV < 5% | ≥ 33% | ≥ 66% |

### Report section

```
## Behavior Diagnostics

| Bias | Severity | Core Evidence |
|------|----------|----------|
| Disposition effect | {high/medium/low} | {evidence} |
| Overtrading | {...} | {...} |
| Chasing momentum | {...} | {...} |
| Anchoring | {...} | {...} |

**Improvement Suggestions** (generate from detected high/medium items):
- Disposition effect high -> hard-code a stop loss, such as -8%, and avoid taking winners too early.
- Overtrading high -> set a hard daily trade-count limit.
- Chasing momentum high -> buy pullbacks instead of fresh highs; avoid chasing after a same-day move above X%.
- Anchoring high -> widen the acceptable price band instead of fixating on one mental price.
```

## Phase 4c preview (not yet implemented)

Strategy extraction → SignalEngine code gen → auto-backtest lands in Phase 4c.
When the user asks for it, respond honestly and offer the behavior diagnostics
instead (they're live).
