---
name: fundamental-filter
description: Fundamental factor screening — filter crypto assets by Market Cap, FDV, Volume, and TVL. Replaces legacy equity providers with CoinGecko and Bitget data.
category: flow
---
# Crypto Fundamental Factor Screening

## Purpose

Filter crypto assets using fundamental network data (Market Cap, FDV, Volume/MCap ratio) to build momentum or value signals for backtesting. Exclusively uses Bitget and CoinGecko as data providers.

## Market Support

| Market | Data Source | Supported Metrics |
|--------|-----------|------------------|
| Crypto | CoinGecko / Bitget | market_cap, fully_diluted_valuation, total_volume, circ_supply |

## Signal Logic

### Large Cap Filter (Default)

1. Market Cap > $1B
2. 24h Volume > $100M
3. All conditions met → long (1), otherwise → flat (0)

### High Velocity Filter (Optional)

1. Volume / Market Cap ratio > 0.1
2. Market Cap > $100M
3. FDV / Market Cap < 2.0 (Low inflation)

## Usage

### config.json

```json
{
  "source": "bitget",
  "codes": ["BTC-USDT", "ETH-USDT", "SOL-USDT"],
  "start_date": "2023-01-01",
  "end_date": "2024-12-31",
  "extra_fields": ["market_cap", "volume"],
  "initial_cash": 1000000,
  "commission": 0.001
}
```

### Python Strategy (`strategy.py`)

```python
import pandas as pd
from backtest.engines.base import BaseStrategy

class CryptoFundamentalStrategy(BaseStrategy):
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df["signal"] = 0
        df.loc[df["close"] > df["close"].rolling(20).mean(), "signal"] = 1
        return df
```
