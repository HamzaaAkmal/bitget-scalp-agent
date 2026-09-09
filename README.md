# bitget-scalp-agent

An AI agent that researches, proposes and executes short-timeframe trades on
**Bitget perpetual futures** — with a human confirmation gate in front of every
live order.

Built on [HKUDS/Vibe-Trading](https://github.com/HKUDS/Vibe-Trading) (MIT). This
fork adds the Bitget MCP integration, the scalping engine, and the trading
frontend; the backtesting, swarm and research runtime come from upstream.

> Research and analysis tooling. Nothing here is financial advice, and leveraged
> perpetual futures can lose more than your margin. See [Risk](#risk).

## What it does

The agent works a full loop: pull market data, research the setup, size the
position, critique the risk, then stop and ask you before anything is sent to
the exchange.

```
market data ──▶ strategies ──▶ risk critic ──▶ proposal ──▶ YOU CONFIRM ──▶ Bitget
  (MCP)          (7 engines)                    (btg_…)      (explicit)      (MCP)
```

Execution is not something the model can reach on its own. `bitget_execute_trade`
rejects any call that does not carry a `btg_`-prefixed proposal id created by
`bitget_prepare_trade`, and it additionally requires explicit confirmation text.
Proposals expire, and `WAIT` proposals can never be executed.

## Scalping engine

Seven strategies score candidates independently:

| Strategy | Reads |
| --- | --- |
| `momentum_continuation` | Trend persistence after an impulse |
| `breakout_retest` | Break of structure, then retest |
| `ema_vwap_pullback` | Pullback into EMA/VWAP confluence |
| `range_mean_reversion` | Fade the edges of a defined range |
| `liquidity_sweep_reversal` | Stop-hunt wick, then reversal |
| `volume_expansion` | Volume surge against prior baseline |
| `funding_oi_divergence` | Funding rate vs open-interest disagreement |

Four agents supervise a session: `market_intelligence_agent` for context and
news risk, `technical_strategy_agent` for setups, `risk_critic_agent` to argue
against the trade, and `execution_monitoring_agent` to watch open positions.

## Requirements

- Python 3.11–3.13 (3.14 is blocked: `llvmlite` has no cp314 wheel)
- Node.js, for the frontend and the `npx`-launched Bitget MCP server
- A Bitget account with API credentials, for live account reads and execution

Public Bitget market data works without credentials; Coinbase remains a degraded
public-data fallback.

## Setup

```bash
pip install -e .
cd frontend && npm install && cd ..
cp agent/.env.example agent/.env      # then fill it in
```

Run both servers:

```bash
./start.sh
```

Or separately:

```bash
vibe-trading --port 8899                                   # backend
cd frontend && npm run dev -- --host 127.0.0.1 --port 5899  # frontend
```

Open `http://127.0.0.1:5899`.

## Configuration

Secrets live in `agent/.env`, which is gitignored. Every default is defined in
`agent/src/config/env_schema.py`.

| Variable | Purpose |
| --- | --- |
| `LANGCHAIN_PROVIDER`, `LANGCHAIN_MODEL_NAME` | Which LLM drives the agent |
| `OPENROUTER_API_KEY` | Recommended multi-model gateway |
| `BITGET_API_KEY`, `BITGET_SECRET_KEY`, `BITGET_PASSPHRASE` | Private account reads and order execution |
| `EXA_API_KEY` | Web and deep research |

OpenAI, Anthropic, DeepSeek, Requesty and OpenAI-Codex providers are supported
too — uncomment the matching block in `.env.example`.

Bitget is reached through the official MCP package
[`@bitget-ai/bitget-agent-mcp`](https://www.npmjs.com/package/@bitget-ai/bitget-agent-mcp),
launched as an `npx` stdio subprocess. It can be seeded read-only or in
paper-trading mode.

## HTTP API

Bitget, under `/bitget`:

| Route | Purpose |
| --- | --- |
| `GET /status`, `/account`, `/positions`, `/orders`, `/fills` | Account and market state |
| `GET /symbols/search`, `/market/candles` | Instrument and candle data |
| `GET /risk-dashboard`, `/alerts` | Exposure and warnings |
| `POST /trade-proposals` | Create a proposal |
| `POST /trade-proposals/{id}/execute` | Execute a confirmed proposal |
| `POST /positions/close`, `/partial-close`, `/scale` | Position management |
| `POST /orders/cancel`, `/strategy-orders/tpsl` | Orders and TP/SL |

Scalp sessions, under `/scalp/sessions`:

| Route | Purpose |
| --- | --- |
| `POST /parse` | Turn a natural-language brief into a session policy |
| `POST /`, `GET /`, `GET /history` | Create and list sessions |
| `POST /{id}/start`, `/pause`, `/resume`, `/stop` | Session lifecycle |
| `POST /stop-all` | Halt everything |
| `GET /{id}`, `/{id}/logs`, `/{id}/events` | Inspect a running session |

## Agent tools

The LLM sees seventeen Bitget tools, split by risk. Reads — `bitget_status`,
`bitget_account`, `bitget_positions`, `bitget_orders`, `bitget_fills`,
`bitget_strategy_orders`, `bitget_search_symbols`, `bitget_risk_dashboard`,
`bitget_alerts`. Writes — `bitget_prepare_trade`, `bitget_execute_trade`,
`bitget_cancel_order`, `bitget_close_position`, `bitget_partial_close`,
`bitget_scale_position`, `bitget_modify_tpsl`, `bitget_trailing_stop_proposal`.

Only `bitget_prepare_trade` can mint a proposal, and only `bitget_execute_trade`
can spend one.

## Risk

Real money moves through this when Bitget credentials are set. Before going live:

- Start in paper-trading or read-only MCP mode.
- Keep the backend bound to loopback; it holds credentials and needs no exposure.
- Treat the confirmation gate as the last line of defence, not the only one —
  set exchange-side limits too.
- Session logs and the PnL ledger are local; back them up if you need an audit trail.

Live trading still lacks a deeper operational layer — private websocket
monitoring, stricter exchange-precision validation, and automated tests around
MCP rejection paths. See `FEATURE_REVIEW.md`.

## Credits

Upstream: [HKUDS/Vibe-Trading](https://github.com/HKUDS/Vibe-Trading) —
docs at [vibetrading.wiki](https://vibetrading.wiki/). Market data and execution
via the official Bitget MCP server. Research via [Exa](https://exa.ai).

## License

MIT. See [LICENSE](LICENSE) — copyright is held by HKUDS for the original
project and by Hamza Akmal for the additions in this fork.
