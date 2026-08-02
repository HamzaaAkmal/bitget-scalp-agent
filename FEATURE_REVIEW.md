# Vibe-Trading Feature Review

Date: 2026-08-01

## Idea Rating

**8.5 / 10**

The idea is strong because it turns Vibe-Trading from a crypto research app into a full AI-assisted Bitget trading workspace. The best part is the confirmation-gated proposal flow: the agent can research, analyze, size, and prepare a trade, but execution still requires explicit user approval.

It is not a 10 yet because live trading needs a deeper operational layer: private websocket monitoring, stronger exchange-precision validation, richer audit logs, paper-trading controls, and more automated tests around MCP responses and order rejection scenarios.

## Current Features

### AI research and agent runtime

- The backend uses FastAPI and the existing local Vibe-Trading runtime.
- The agent has OpenAI-compatible LLM configuration and Exa research support.
- Tool discovery is automatic through `agent/src/tools/__init__.py`.
- The agent prompt now directs crypto trading work through Bitget proposal tools before execution.
- Existing backtest, swarm, research, settings, uploads, reports, and connector architecture remain in place.

### Official Bitget MCP integration

- Bitget is integrated through the official MCP package `@bitget-ai/bitget-agent-mcp`.
- MCP bootstrapping lives in `agent/src/services/bitget_mcp.py`.
- Safe allowed tools are limited to market/account/order/position/config style operations.
- Raw, withdrawal, deposit, transfer, subaccount, and repayment style actions are deliberately not part of the app allowlist.
- Bitget credentials are read server-side from environment sources and are never exposed to the browser.
- Preflight now checks Bitget MCP availability.

### Bitget backend APIs

The new route module `agent/src/api/bitget_routes.py` exposes:

- `GET /bitget/status`
- `GET /bitget/symbols/search`
- `GET /bitget/market/candles`
- `GET /bitget/account`
- `GET /bitget/positions`
- `GET /bitget/orders`
- `POST /bitget/trade-proposals`
- `POST /bitget/trade-proposals/{proposal_id}/execute`
- `POST /bitget/orders/cancel`
- `POST /bitget/positions/close`

The legacy `/market/crypto/candles` route is now Bitget-first and only falls back to Coinbase public candles if Bitget MCP market data fails.

### Symbol search

- `agent/src/services/bitget_symbols.py` resolves names like `bitcoin`, `eth`, `sol`, `DOGE`, `PEPE`, and direct Bitget symbols like `BTCUSDT`.
- It uses Bitget instrument metadata and aliases.
- It returns ambiguity when multiple markets match, so the agent can ask the user whether they want spot or futures.
- The old static symbol assumption has been replaced for the live crypto path.

### Natural-language trade proposals

The proposal flow is split into small services:

- `signal_engine.py` parses user intent: symbol, side, timeframe, spot/futures, leverage, margin mode, risk style, and strategy style.
- `risk_engine.py` calculates entry, stop loss, take profit, leverage, position size, notional, and warnings.
- `trade_confirmation.py` persists proposal records with expiration.
- `bitget_execution.py` executes only confirmed proposals through MCP.

The agent-facing tools are in `agent/src/tools/bitget_tool.py`:

- `bitget_status`
- `bitget_search_symbols`
- `bitget_account`
- `bitget_positions`
- `bitget_orders`
- `bitget_prepare_trade`
- `bitget_execute_trade`
- `bitget_cancel_order`
- `bitget_close_position`

### Confirmation and execution safety

- `bitget_prepare_trade` never places an order.
- `bitget_execute_trade` requires a stored `proposal_id` and explicit confirmation text.
- WAIT proposals cannot be executed.
- Futures execution sets leverage before order placement when needed.
- Market order placement is routed through the official Bitget MCP `order` tool.
- Futures order arguments include TP and SL fields when available.
- Cancel and close-position operations are available, with close requiring confirmation.

### Frontend crypto trading screen

`frontend/src/pages/CryptoMarket.tsx` is now a Bitget-centered trading surface:

- Futures/spot category switch.
- Bitget symbol input.
- Timeframes: `1m`, `3m`, `5m`, `15m`, `30m`, `1H`, `4H`, `1D`, `1W`.
- Bitget historical candles through the backend.
- Public Bitget websocket ticker updates.
- Lightweight Charts candlestick view.
- Indicator panes for EMA, VWAP, volume, RSI, and MACD.
- Trade proposal textarea.
- Proposal card with direction, confidence, entry, stop loss, take profit, leverage, margin, reasoning, and warnings.
- Confirmation dialog before execution.
- Account, position, and open-order snapshot panels.

### Trading connector profile

- `bitget-live-mcp-readonly` is now the default connector profile.
- Generic connector reads for quote/history/account/positions/orders can route to Bitget MCP.
- Generic connector order placement remains unsupported for remote MCP profiles, which is good: Bitget execution should go through the proposal and confirmation flow.

### Configuration and security

- `agent/.env.example` now includes Bitget credentials, environment, product type, margin mode, and risk defaults.
- `agent/src/config/env_schema.py` has a `BitgetConfig`.
- `agent/src/config/schema.py` includes a safe Bitget MCP server seed.
- CSP report-only settings include Bitget public API and websocket endpoints.
- API keys remain server-side.

## How It Works

### Market chart flow

1. User opens the crypto market page.
2. Frontend calls `/bitget/market/candles`.
3. Backend normalizes the symbol, category, and interval.
4. Backend calls the official Bitget MCP `market` tool.
5. Candle rows are normalized and returned to the frontend.
6. Frontend renders candles and computes EMA, VWAP, volume, RSI, and MACD locally.
7. Frontend opens the Bitget public websocket and updates the latest candle with ticker ticks.

### AI trade proposal flow

1. User types a natural-language request.
2. Frontend posts it to `/bitget/trade-proposals`.
3. `parse_trade_intent` extracts trading intent.
4. `resolve_symbol` maps the user text to a Bitget symbol.
5. `build_market_signal` fetches Bitget candles and computes a compact technical signal.
6. `build_risk_plan` calculates risk, leverage, TP, SL, size, and warnings.
7. `create_trade_proposal` stores the proposal locally with an expiration.
8. Frontend shows a proposal card and asks for confirmation.
9. If confirmed, frontend posts to `/bitget/trade-proposals/{proposal_id}/execute`.
10. Backend checks the confirmation text, rejects expired or WAIT proposals, then calls Bitget MCP to set leverage and place the order.

### Agent tool flow

1. The model uses `bitget_search_symbols` if the symbol is unclear.
2. The model uses `bitget_prepare_trade` for any actionable trade request.
3. The model presents the proposal and asks: "Would you like me to execute this trade?"
4. Only after a clear affirmative response should the model call `bitget_execute_trade`.
5. For account state, the model can use `bitget_account`, `bitget_positions`, and `bitget_orders`.

## Best Features To Add Next

### 1. Typed confirmation for live execution

The frontend currently uses a confirmation dialog and sends a fixed affirmative phrase after the user clicks execute. For live trading, require the user to type something like:

```text
confirm BTCUSDT buy 3x
```

This would reduce accidental clicks and make the confirmation record stronger.

### 2. Private websocket position monitor

Add private Bitget websocket support for:

- Real-time PnL.
- Margin ratio.
- Liquidation price.
- Funding.
- Fill status.
- TP/SL trigger status.
- Position size changes.

The current UI refreshes private state periodically. That is fine for a first version, but live trading needs event-driven updates.

### 3. Exchange precision and minimum-order validation

Before execution, validate:

- Quantity precision.
- Price precision.
- Minimum order size.
- Minimum notional.
- Maximum leverage per instrument.
- Supported margin mode.

Some metadata is already available from instrument search, but the final execution path should enforce it directly before calling MCP order placement.

### 4. Trade audit timeline

Add a durable timeline for every proposal:

- Prompt.
- Parsed intent.
- Symbol resolution.
- Signal values.
- Risk plan.
- User confirmation.
- MCP request.
- MCP response.
- Order id.
- Fill events.
- Errors.

This should be visible in the UI and stored outside browser local storage.

### 5. Bitget backtest loader

The live chart path is Bitget-first, but the historical backtest engine still has Coinbase as the default crypto loader. Add a Bitget historical loader so strategy research and live execution use the same exchange data.

### 6. Paper-trading mode switch

Expose a clear UI/runtime switch:

- Public data only.
- Paper trading or demo mode.
- Live trading.

The backend already knows about Bitget env defaults, but the user should see the current mode before any execution action.

### 7. Strategy presets

Add strategy modes that change signal and risk behavior:

- Scalping.
- Intraday trend.
- Mean reversion.
- Breakout.
- Conservative swing.
- High-risk momentum.

The current parser detects basic `scalp`, `swing`, `aggressive`, and `conservative` words, but the strategy behavior is still lightweight.

### 8. Confidence calibration

The current confidence score is useful as a first-pass indicator score, but it is not statistically calibrated. Improve it with:

- Historical hit-rate by setup type.
- Volatility-adjusted scoring.
- Regime detection.
- Multi-timeframe confirmation.
- News/catalyst score from Exa.

### 9. Better order management UI

Add explicit UI actions for:

- Cancel order.
- Close position.
- Move stop loss.
- Move take profit.
- Reduce position.
- Flip direction.
- Duplicate proposal with adjusted size.

The backend has cancel and close primitives, but the page does not yet expose a full order-management workflow.

### 10. MCP mocking test suite

Add tests with mocked MCP responses for:

- Unknown symbol.
- Ambiguous symbol.
- MCP unavailable.
- Invalid leverage.
- Insufficient balance.
- Order rejection.
- Partial fills.
- Expired proposal.
- WAIT proposal execution rejection.
- Confirmation text rejection.

## Features To Remove Or De-emphasize

### Remove Coinbase from the live trading mental model

Coinbase should stay only as a degraded public-data fallback or legacy backtest source. The live chart, AI prompts, and execution flow should consistently speak Bitget.

### Remove static symbol examples from the trading UI

The datalist is useful as a quick hint, but it still includes a tiny fixed set. Replace it with real `/bitget/symbols/search` autocomplete.

### De-emphasize generic connector order placement for Bitget

Keep Bitget order execution inside the proposal-confirmation workflow. Generic `place_order` for Bitget remote MCP should stay unsupported unless it can reuse the exact same confirmation, risk, and audit pipeline.

### Reduce overloaded crypto page complexity over time

`CryptoMarket.tsx` now handles charting, websocket updates, indicators, account snapshots, proposals, execution, and data table rendering. It works, but it should eventually be split into smaller components:

- `BitgetChart`
- `IndicatorPanes`
- `TradeProposalPanel`
- `AccountSnapshotPanel`
- `PositionsPanel`
- `OrdersPanel`
- `SymbolSelector`

### Revisit legacy crypto backtest wording

Some backtest examples still correctly mention Coinbase because the current loader is Coinbase-backed. Once Bitget backtest loading exists, update those examples to Bitget too.

## Features To Improve

### Route registration

`register_bitget_routes` retrieves `require_auth` from the host module through `sys.modules`, matching the current route pattern. A cleaner future direction is a shared API dependency module so route modules do not need to inspect loaded modules.

### MCP process performance

If each MCP call starts a fresh `npx` process, latency can become noticeable. Consider a persistent MCP adapter or connection pool, especially for chart refreshes, account polling, and symbol search.

### Metadata caching

Instrument metadata should be cached with a clear TTL. This improves symbol search and precision validation without repeatedly calling MCP.

### Risk engine realism

Current risk planning is a good first layer. Improve it with:

- Fees.
- Funding.
- Spread.
- Slippage.
- Liquidation estimate.
- Existing exposure.
- Daily loss limits.
- Max correlated exposure.

### User-facing error handling

Add clearer frontend states for:

- Bitget MCP unavailable.
- Credentials missing.
- Public-only mode.
- Private read rejected.
- Exchange maintenance.
- Rate limit.
- Order rejected.
- Proposal expired.

### Security posture

Keep withdrawal permissions out of scope. Also consider:

- Showing credential status without field names that could imply a secret value exists.
- A live-trading kill switch.
- Per-session execution limits.
- Optional typed confirmation for every live action.
- An execution cooldown after failed orders.

## Suggested Roadmap

### Phase 1: Safety polish

- Typed confirmation.
- Proposal audit log.
- Better execution error display.
- Instrument precision validation.
- Dry-run toggle in the UI.

### Phase 2: Monitoring

- Private websocket positions.
- Live PnL cards.
- Fill timeline.
- Funding and liquidation data.
- Alerts for TP, SL, liquidation proximity, and order rejection.

### Phase 3: Research quality

- Multi-timeframe analysis.
- Exa catalyst score.
- Confidence calibration.
- Strategy presets.
- Bitget backtest loader.

### Phase 4: Advanced trading management

- Modify TP/SL.
- Partial close.
- Position scaling.
- Trailing stop proposals.
- Risk dashboard.
- Portfolio-level exposure controls.

## Final Recommendation

Keep building this idea. The current code has the right direction: Bitget is the execution layer, research remains modular, and order placement is gated behind proposals and confirmation. The next big unlock is operational trust: typed confirmation, audit timelines, real-time private monitoring, exchange-rule validation, and a robust mocked MCP test suite.

With those additions, this can move from an impressive AI trading prototype into a serious local trading cockpit.
