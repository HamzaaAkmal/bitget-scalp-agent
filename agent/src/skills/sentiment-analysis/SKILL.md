---
name: sentiment-analysis
description: Market sentiment analysis covering fear-and-greed indicators, put-call ratio, margin financing, northbound capital flows, and social-media sentiment.
category: analysis
---

# Market Sentiment Analysis

## Overview

Use measurable proxies to turn subjective market mood into a structured view. Sentiment indicators are usually contrarian signals, so always combine them with trend, valuation, liquidity, and macro context.

## Fear And Greed

### Crypto Fear And Greed Index

Score range: 0-100.

| Score | Sentiment State | Typical Historical Signal |
|------|------------------|---------------------------|
| 0-20 | Extreme fear | Potential bottom zone; contrarian accumulation candidate |
| 20-40 | Fear | Below-normal risk appetite |
| 40-60 | Neutral | Wait for other evidence |
| 60-80 | Greed | Elevated optimism |
| 80-100 | Extreme greed | Potential top zone; contrarian risk-reduction candidate |

Common inputs include volatility, market momentum, social-media sentiment, survey data, BTC dominance, and Google Trends interest.

### China A-Share Fear And Greed Proxy

China A-shares do not have one universal fear-and-greed index, so use a basket:

| Indicator | Source | Extreme Fear | Extreme Greed |
|-----------|--------|--------------|----------------|
| Shanghai turnover | Exchange data | <0.5% | >2.5% |
| Limit-up / limit-down count ratio | Market data | <0.3 | >5.0 |
| New brokerage account openings, weekly | Depository data | <200k | >1m |
| Margin balance change, monthly | Exchange data | net outflow >50bn CNY | net inflow >100bn CNY |
| ETF net subscriptions | Fund data | broad ETF buying | broad ETF redemptions |

## Put-Call Ratio

Put-call ratio is put option volume divided by call option volume. It is usually read as a contrarian indicator.

| PCR | Meaning | Contrarian Read |
|-----|---------|-----------------|
| >1.5 | Extremely bearish positioning | Bullish reversal risk |
| 1.0-1.5 | Bearish | Mildly bullish |
| 0.7-1.0 | Neutral | No clear signal |
| 0.5-0.7 | Bullish | Mildly bearish |
| <0.5 | Extremely bullish positioning | Bearish reversal risk |

Reference ranges differ by market:

| Market | Source | Normal Range | Extreme Range |
|--------|--------|--------------|---------------|
| US equities | CBOE/VIX options | 0.7-1.2 | <0.5 or >1.5 |
| China A-shares | SSE 50 ETF options | 0.5-1.5 | <0.3 or >2.0 |
| BTC | Deribit | 0.3-0.8 | <0.2 or >1.2 |

## Margin Financing

For China A-shares, margin financing shows leveraged long demand and securities lending shows short demand.

| Indicator | Bullish Signal | Bearish Signal |
|-----------|----------------|----------------|
| Margin balance | Rises after a bottoming period | Accelerates at highs |
| Net margin buying | Positive for 5 straight days | Negative for 5 straight days |
| Securities lending balance | Falls after a spike, suggesting short covering | Suddenly spikes |
| Margin / lending ratio | Rebounds from a low ratio | Reaches an extreme high ratio |

Historical context for China A-shares:

| Period | Approximate Margin Balance Context |
|--------|------------------------------------|
| 2015 bull-market top | 2.27tn CNY, extreme |
| 2018 bear-market low | 0.76tn CNY |
| 2020 normal range | 1.0-1.2tn CNY |
| 2024 normal range | 1.4-1.8tn CNY |

Rule of thumb: a monthly margin-balance rise above 10% is overheating risk; a monthly fall above 10% is panic risk.

## Northbound Capital Flows

Northbound capital refers to foreign buying of China A-shares through Stock Connect. Treat it as one input, not a standalone timing model.

| Indicator | Bullish Signal | Bearish Signal |
|-----------|----------------|----------------|
| One-day net inflow | >10bn CNY | <-10bn CNY |
| Consecutive inflow days | >10 days | >10 outflow days |
| Monthly net inflow | >50bn CNY | <-50bn CNY |
| Holding changes | Adds undervalued blue chips | Cuts cyclicals and theme stocks |

Since 2023, passive-flow effects, hedging trades, and disclosure changes can weaken the signal. Prefer weekly or monthly totals over a single-day print, and cross-check with margin balance and ETF flows.

## Social-Media Sentiment

Use social sentiment as a noisy heat gauge. Filter spam, repeated posts, marketing accounts, and coordinated campaigns.

| Metric | Calculation | Contrarian Signal |
|--------|-------------|-------------------|
| Heat index | Search or discussion volume vs 30-day average | Sudden spike can mean overheating |
| Bullish share | Bullish posts / total posts | >80% suggests crowd optimism |
| Newcomer index | New accounts in discussion / total accounts | >50% suggests retail crowding |
| Influencer consensus | Agreement across major accounts | One-sided bullish consensus is risky |

Typical cycle:

| Phase | Social Pattern |
|-------|----------------|
| Bottom | Little discussion, then early accumulation debate |
| Advance | Discussion rises and optimism spreads |
| Top | Broad public attention and extreme confidence |
| Decline | Debate turns into panic, then silence |

## Composite Sentiment Score

Suggested weighting:

| Component | Weight |
|-----------|--------|
| Fear-and-greed | 25% |
| Put-call ratio | 20% |
| Margin financing | 20% |
| Northbound capital | 20% |
| Social sentiment | 15% |

Normalize each component to 0-100:

| Score | State |
|-------|-------|
| 0-20 | Extreme fear |
| 20-40 | Fear |
| 40-60 | Neutral |
| 60-80 | Greed |
| 80-100 | Extreme greed |

## Output Format

```markdown
## Market Sentiment Analysis

### Sentiment Dashboard
| Indicator | Current Value | Percentile | Signal |
|-----------|---------------|------------|--------|
| Crypto fear-and-greed | 72 | 75% | Greed |
| China A-share turnover | 1.8% | 70% | Active |
| SSE 50 ETF PCR | 0.65 | 35% | Optimistic |
| Weekly margin-balance change | +28bn CNY | 80% | Leveraged buying accelerating |
| Weekly northbound net inflow | +12bn CNY | 60% | Mildly positive |

### Composite Sentiment Score: 68/100 (Greed)

### Interpretation
Current sentiment is greedy. Margin financing is rising and foreign flow is positive, but low PCR suggests limited hedging demand.

### Suggested Response
- Reduce position size toward 40-50% if price action confirms exhaustion.
- Avoid chasing fresh highs; wait for pullbacks.
- Consider protective hedges if volatility is cheap.

### Risk Notes
- Sentiment is a contrarian input, not a precise timing tool.
- Strong trends can keep sentiment extreme for a long time.
```

## Notes

1. Contrarian indicators are not precise timing tools.
2. Combine sentiment with trend and valuation.
3. Thresholds vary materially across China A-shares, US equities, and crypto.
4. Some sentiment data requires paid APIs.
5. Social-media sentiment is noisy and needs spam filtering.
6. Northbound-flow disclosure changes after 2023 reduce real-time transparency.
7. Margin-financing data is published with a lag.
