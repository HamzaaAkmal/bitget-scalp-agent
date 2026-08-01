# Vibe-Trading

Crypto-focused trading research workspace powered by official Bitget MCP market/execution workflows and Exa web research.

## Stack

- Frontend: React, TypeScript, Vite, Tailwind-style CSS, React Router, Lightweight Charts
- Backend: Python, FastAPI, Uvicorn
- Market data: Bitget via the official MCP server, with Coinbase public candles as fallback
- Research: Exa AI search and page reading
- Agent model: configurable OpenAI-compatible LLM provider

## Local Development

Backend:

```bash
.venv/bin/vibe-trading --port 8899
```

Frontend:

```bash
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5899
```

Open:

```text
http://127.0.0.1:5899
```

## Configuration

Local secrets belong in local `.env` files and are ignored by Git.

- `EXA_API_KEY` enables web and deep research.
- `BITGET_API_KEY`, `BITGET_SECRET_KEY`, and `BITGET_PASSPHRASE` enable private Bitget account reads and confirmed order execution through `@bitget-ai/bitget-agent-mcp`.
- Bitget public market data works without a Bitget API key; Coinbase is retained only as degraded public-data fallback.

## Notes

This project is for research and analysis. Trading signals and leveraged calculations are not financial advice.
