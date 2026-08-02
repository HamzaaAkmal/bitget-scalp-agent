"""Local market data tool backed by the shared loader layer."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from src.agent.tools import BaseTool
from src.market_data import DEFAULT_MAX_ROWS, fetch_market_data_json
from src.services.bitget_mcp import fetch_candles, normalize_category, normalize_interval, normalize_symbol

_CRYPTO_SYMBOL_RE = re.compile(r"^[A-Z0-9]{2,15}[-/](?:USD|USDT|USDC|BTC|ETH)$", re.I)


def _normalize_crypto_codes(codes: list[str]) -> list[str]:
    """Use the project crypto convention while accepting USD/USDT forms."""
    normalized: list[str] = []
    for code in codes:
        value = code.strip().upper().replace("/", "-")
        if value.endswith("-USD"):
            value = value.removesuffix("-USD") + "-USDT"
        normalized.append(value)
    return normalized


def _should_force_bitget(source: str, codes: list[str]) -> bool:
    if source not in {"auto", "yahoo", "yfinance"}:
        return False
    return bool(codes) and all(_CRYPTO_SYMBOL_RE.match(code.strip()) for code in codes)


def _all_crypto_codes(codes: list[str]) -> bool:
    return bool(codes) and all(_CRYPTO_SYMBOL_RE.match(code.strip()) for code in codes)


def _default_date_window(interval: str) -> tuple[str, str]:
    end = datetime.now(timezone.utc).date()
    normalized = interval.strip().lower()
    if normalized.endswith("m"):
        start = end - timedelta(days=3)
    elif normalized.endswith("h"):
        start = end - timedelta(days=30)
    else:
        start = end - timedelta(days=180)
    return start.isoformat(), end.isoformat()


class MarketDataTool(BaseTool):
    """Fetch normalized OHLCV data through repository loaders."""

    name = "get_market_data"
    description = (
        "Fetch normalized OHLCV crypto market data through Bitget. Use this "
        "for BTC-USDT, ETH-USDT, SOL-USDT, and other crypto price bars."
    )
    parameters = {
        "type": "object",
        "properties": {
            "codes": {
                "type": "array",
                "items": {"type": "string"},
                "description": 'Crypto symbols such as ["BTC-USDT"], ["ETH-USDT"], ["SOL-USDT"].',
            },
            "start_date": {
                "type": "string",
                "description": "Start date in YYYY-MM-DD format. Defaults to a recent lookback window when omitted.",
            },
            "end_date": {
                "type": "string",
                "description": "End date in YYYY-MM-DD format. Defaults to today when omitted.",
            },
            "source": {
                "type": "string",
                "enum": [
                    "auto",
                    "bitget",
                    "coinbase",
                    "local",
                ],
                "description": (
                    "Data source. 'auto' and 'bitget' both use Bitget for "
                    "crypto. 'coinbase' is a legacy public-data fallback. "
                    "'local' is only for user-provided crypto data."
                ),
                "default": "auto",
            },
            "interval": {
                "type": "string",
                "description": "Bar size, e.g. 1D, 1H, 4H, 30m.",
                "default": "1D",
            },
            "max_rows": {
                "type": "integer",
                "description": "Per-symbol row cap. Use 0 only when the full series is required.",
                "default": DEFAULT_MAX_ROWS,
            },
        },
        "required": ["codes"],
    }
    repeatable = True

    def execute(self, **kwargs: Any) -> str:
        codes = [str(code).strip() for code in kwargs["codes"]]
        source = str(kwargs.get("source", "auto")).strip().lower() or "auto"
        if not _all_crypto_codes(codes):
            return (
                '{"ok": false, "error": "get_market_data is configured for crypto only. '
                'Use symbols like BTC-USDT, ETH-USDT, or SOL-USDT."}'
            )
        interval = str(kwargs.get("interval", "1D") or "1D")
        default_start, default_end = _default_date_window(interval)
        start_date = str(kwargs.get("start_date") or default_start)
        end_date = str(kwargs.get("end_date") or default_end)
        if _should_force_bitget(source, codes) or source in {"auto", "bitget"}:
            return _bitget_market_data_json(
                codes=_normalize_crypto_codes(codes),
                interval=interval,
                max_rows=kwargs.get("max_rows", DEFAULT_MAX_ROWS),
            )
        return fetch_market_data_json(
            codes=codes,
            start_date=start_date,
            end_date=end_date,
            source=source,
            interval=interval,
            max_rows=kwargs.get("max_rows", DEFAULT_MAX_ROWS),
            include_provenance=True,
        )


def _bitget_market_data_json(*, codes: list[str], interval: str, max_rows: int) -> str:
    """Return a fetch_market_data-compatible JSON envelope from Bitget MCP."""
    interval = normalize_interval(interval)
    limit = DEFAULT_MAX_ROWS if max_rows is None else int(max_rows)
    if limit <= 0:
        limit = 500
    limit = max(20, min(limit, 1500))
    results: dict[str, Any] = {}
    provenance: dict[str, Any] = {}
    for code in codes:
        symbol = normalize_symbol(code)
        bars = fetch_candles(symbol=symbol, category=normalize_category("USDT-FUTURES"), interval=interval, lookback=limit)
        key = symbol.removesuffix("USDT") + "-USDT" if symbol.endswith("USDT") else symbol
        
        live_price = None
        try:
            from src.scalp.services.coingecko_client import get_coingecko_client
            cg = get_coingecko_client()
            cg_markets = cg.get_coins_markets(limit=250)
            cg_symbol = symbol.removesuffix("USDT").lower()
            for m in cg_markets:
                if m.get("symbol") == cg_symbol:
                    live_price = m.get("current_price")
                    break
        except Exception:
            pass
            
        if live_price is None:
            try:
                from src.services.bitget_mcp import fetch_ticker
                ticker = fetch_ticker(symbol=symbol)
                live_price = float(ticker.get("lastPr", ticker.get("last", 0)))
            except Exception:
                pass
                
        results[key] = {"data": bars}
        if live_price is not None:
            results[key]["current_live_price"] = live_price
            
        provenance[key] = {"source": "bitget", "requested_source": "bitget", "fallback_used": False}
    results["_provenance"] = provenance
    import json

    return json.dumps(results, ensure_ascii=False, indent=2, allow_nan=False)
