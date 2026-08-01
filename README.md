# Vibe-Trading

Crypto-focused trading research workspace powered by Coinbase market data and Exa web research.

## Stack

- Frontend: React, TypeScript, Vite, Tailwind-style CSS, React Router, Lightweight Charts
- Backend: Python, FastAPI, Uvicorn
- Market data: Coinbase Exchange public crypto candles
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
- Coinbase market data works without an API key.

## Notes

This project is for research and analysis. Trading signals and leveraged calculations are not financial advice.
