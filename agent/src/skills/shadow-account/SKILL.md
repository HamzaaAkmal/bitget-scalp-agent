---
name: shadow-account
description: "Shadow Account - extract a user's profitable trading pattern into 3-5 plain-English rules, run multi-market backtests across China A-shares/HK/US/crypto, attribute the delta, and render an 8-section PDF report."
category: analysis
---

# Shadow Account

## When To Trigger

Load this skill when the user asks to extract their strategy, train a shadow account, backtest their own trading style, estimate how much they are leaving on the table, or identify their profitable pattern.

**Prerequisite**: the user has uploaded a broker trade journal and `analyze_trade_journal` has already run. If not, run the trade journal analysis first.

## Workflow

1. `extract_shadow_strategy(journal_path=...)`
   - Returns `shadow_id` plus 3-5 plain-English rules.
   - Ask the user to confirm whether the rules look like their actual behavior. If they say no, increase `min_support` and run extraction again.
2. `run_shadow_backtest(shadow_id=..., journal_path=...)`
   - Returns per-market metrics, `delta_pnl`, and attribution breakdown.
   - Runs the four-market set by default: `china_a`, `hk`, `us`, and `crypto`.
3. `render_shadow_report(shadow_id=...)`
   - Generates HTML and PDF. If WeasyPrint fails, it falls back to HTML-only.
   - Returns `html_path`, `pdf_path`, and `delta_pnl`.
4. Optional: `scan_shadow_signals(shadow_id=...)`
   - Lists instruments currently inside the shadow entry window for research use only.

## Output Interpretation

### Rule Cards

Each rule includes `rule_id`, `human_text`, `support_count`, `coverage_rate`, and `holding_days_range`. Rules are not guaranteed-profit formulas. They describe common traits from the user's profitable trades.

### Backtest Matrix

- `per_market`: Sharpe, annual return, and max drawdown by market.
- `combined`: pooled performance across markets.
- `equity_curve`: net value time series for PDF Section 3.

### Delta Attribution

All values are signed; positive values mean the shadow account outperformed the real account.

- `noise_trades_pnl`: real-trade PnL from trades that matched none of the extracted rules.
- `early_exit_pnl`: opportunity cost from winning trades closed before the rule's lower holding-period bound.
- `late_exit_pnl`: amplified loss from losing trades held beyond the rule's upper holding-period bound.
- `overtrading_pnl`: real-trade PnL from activity above the rule frequency.
- `missed_signals_pnl`: residual value, computed as `shadow_pnl - real_pnl - the four attribution buckets above`.

### Counterfactual Top 5

Sort by `|impact|` and list the five highest-impact trades the user should have taken but missed, or should not have taken but did. Include concrete dates and reasons.

## Dialogue Templates

**Confirm Rules**

> I extracted these rules from your {profitable_roundtrips} profitable round trips: {rules}. Do these look like your actual trading style?

**Show Delta**

> Shadow PnL **{shadow_pnl:+.0f}** / your real PnL **{real_pnl:+.0f}** / delta **{delta_pnl:+.0f}**. Of that, **{noise_trades_pnl:+.0f}** came from trades that did not match any of your profitable rules.

**Current Scan**

> Instruments currently inside your shadow entry window: {symbols}. **Research only. This is not a buy recommendation.**

## Rule Translation Prompt Template

When `extract_shadow_strategy` receives an `llm_translator` callable, use it to turn structured entry conditions into a concise English rule:

```text
[Context] A retail trader had {N} profitable round trips matching one condition set:
  market = {market}
  entry_hour between {hour_min} and {hour_max}
  holding period {hold_lo}-{hold_hi} days
[Task] Write one plain-English trading habit rule in 20 words or fewer. Avoid jargon.
[Output] Return exactly one rule line with no explanation.
```

Without `llm_translator`, use the f-string template in `extractor._translate_rule`.

## Guardrails

- **No live orders**: these tools never connect to any order placement channel. They only produce research output.
- **No copying other traders**: Shadow Account models the user's own behavior, not public or community strategies.
- **No fabricated samples**: if profitable round trips are fewer than 5, raise an error instead of inventing rules.
