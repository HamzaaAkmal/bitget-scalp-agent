"""Read-only crypto symbol search backed by Coinbase products."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

import requests

from src.agent.tools import BaseTool

logger = logging.getLogger(__name__)

_COINBASE_PRODUCTS_URL = "https://api.exchange.coinbase.com/products"
_COINBASE_TIMEOUT = 10

# Hard caps so a broad query cannot bloat the envelope.
_MAX_LIMIT = 25
_DEFAULT_LIMIT = 10

_CRYPTO_ALIASES: Dict[str, Dict[str, str]] = {
    "bitcoin": {"symbol": "BTC-USDT", "name": "Bitcoin", "base": "BTC"},
    "btc": {"symbol": "BTC-USDT", "name": "Bitcoin", "base": "BTC"},
    "btc-usd": {"symbol": "BTC-USDT", "name": "Bitcoin", "base": "BTC"},
    "btcusd": {"symbol": "BTC-USDT", "name": "Bitcoin", "base": "BTC"},
    "btc-usdt": {"symbol": "BTC-USDT", "name": "Bitcoin", "base": "BTC"},
    "btcusdt": {"symbol": "BTC-USDT", "name": "Bitcoin", "base": "BTC"},
    "ethereum": {"symbol": "ETH-USDT", "name": "Ethereum", "base": "ETH"},
    "ether": {"symbol": "ETH-USDT", "name": "Ethereum", "base": "ETH"},
    "eth": {"symbol": "ETH-USDT", "name": "Ethereum", "base": "ETH"},
    "solana": {"symbol": "SOL-USDT", "name": "Solana", "base": "SOL"},
    "sol": {"symbol": "SOL-USDT", "name": "Solana", "base": "SOL"},
    "xrp": {"symbol": "XRP-USDT", "name": "XRP", "base": "XRP"},
    "dogecoin": {"symbol": "DOGE-USDT", "name": "Dogecoin", "base": "DOGE"},
    "doge": {"symbol": "DOGE-USDT", "name": "Dogecoin", "base": "DOGE"},
}


class SymbolSearchTool(BaseTool):
    """Resolve a crypto name or ticker fragment to Coinbase symbols."""

    name = "search_symbol"
    description = (
        "Resolve a crypto name or ticker fragment to Coinbase-backed trading "
        "symbols in the project's crypto convention, e.g. BTC-USDT. Use this "
        "before calling get_market_data or technical_indicators. Example: "
        'search_symbol(query="bitcoin", limit=5).'
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "Free-text crypto name or ticker fragment to resolve, e.g. "
                    "'bitcoin', 'btc', 'ethereum', 'sol'."
                ),
            },
            "limit": {
                "type": "integer",
                "description": (
                    f"Maximum number of merged candidates to return "
                    f"(1-{_MAX_LIMIT}). Defaults to {_DEFAULT_LIMIT}."
                ),
                "default": _DEFAULT_LIMIT,
            },
        },
        "required": ["query"],
    }
    repeatable = True

    def execute(self, **kwargs: Any) -> str:
        """Search crypto aliases first, then Coinbase products.

        Args:
            **kwargs: ``query`` (str, required free-text name/ticker) and
                ``limit`` (int, optional; clamped to ``1.._MAX_LIMIT``).

        Returns:
            A JSON envelope string with Coinbase crypto candidates.
        """
        query = str(kwargs.get("query") or "").strip()
        if not query:
            return _error("'query' is required and must be a non-empty string")

        limit = _clamp_limit(kwargs.get("limit", _DEFAULT_LIMIT))

        crypto_hit = _search_crypto_alias(query)
        if crypto_hit is not None:
            return json.dumps(
                {
                    "ok": True,
                    "market": "crypto",
                    "source": "symbol_search",
                    "data": {
                        "query": query,
                        "count": 1,
                        "candidates": [crypto_hit],
                        "sources": {"coinbase": "ok"},
                    },
                },
                ensure_ascii=False,
            )

        merged, status = _search_coinbase_products(query, limit)

        return json.dumps(
            {
                "ok": True,
                "market": "crypto",
                "source": "symbol_search",
                "data": {
                    "query": query,
                    "count": len(merged),
                    "candidates": merged,
                    "sources": {"coinbase": status},
                },
            },
            ensure_ascii=False,
        )


def _clamp_limit(value: Any) -> int:
    """Coerce a requested count into the supported ``1.._MAX_LIMIT`` range."""
    try:
        n = int(value)
    except (TypeError, ValueError, OverflowError):
        return _DEFAULT_LIMIT
    return max(1, min(n, _MAX_LIMIT))


def _search_crypto_alias(query: str) -> Optional[Dict[str, Any]]:
    """Resolve common crypto names to Coinbase-backed project symbols."""
    normalized = "".join(ch for ch in query.strip().casefold() if ch.isalnum())
    if not normalized:
        return None
    for key, item in _CRYPTO_ALIASES.items():
        key_norm = "".join(ch for ch in key.casefold() if ch.isalnum())
        if normalized == key_norm:
            return {
                "symbol": item["symbol"],
                "name": item["name"],
                "market": "crypto",
                "type": "cryptocurrency",
                "exchange": "coinbase",
                "source": "coinbase",
                "quote_currency": "USDT",
                "coinbase_product_id": f"{item['base']}-USD",
            }
    return None


def _search_coinbase_products(query: str, limit: int) -> tuple[List[Dict[str, Any]], str]:
    """Query Coinbase public products and normalize matching USD pairs."""
    normalized = "".join(ch for ch in query.strip().casefold() if ch.isalnum())
    if not normalized:
        return [], "empty query"
    try:
        response = requests.get(
            _COINBASE_PRODUCTS_URL,
            headers={"User-Agent": "Vibe-Trading/0.1"},
            timeout=_COINBASE_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:  # noqa: BLE001 - one source failing is non-fatal
        logger.warning("coinbase product search failed for %r: %s", query, exc)
        return [], f"coinbase product search failed: {exc}"
    if not isinstance(payload, list):
        return [], "coinbase returned unexpected product payload"

    candidates: list[dict[str, Any]] = []
    for row in payload:
        if not isinstance(row, dict):
            continue
        product_id = str(row.get("id") or "")
        base = str(row.get("base_currency") or "")
        quote = str(row.get("quote_currency") or "")
        status = str(row.get("status") or "")
        display_name = str(row.get("display_name") or product_id)
        if quote.upper() != "USD" or status.lower() not in {"online", ""}:
            continue
        haystack = "".join(
            ch
            for ch in f"{product_id} {base} {display_name}".casefold()
            if ch.isalnum()
        )
        if normalized not in haystack:
            continue
        candidates.append(
            {
                "symbol": f"{base.upper()}-USDT",
                "name": display_name,
                "market": "crypto",
                "type": "cryptocurrency",
                "exchange": "coinbase",
                "source": "coinbase",
                "quote_currency": "USDT",
                "coinbase_product_id": product_id.upper(),
            }
        )
    return _merge_candidates(candidates)[:limit], "ok"


def _eastmoney_candidate(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Map one Eastmoney suggest row to a normalized candidate, or ``None``.

    Eastmoney rows carry ``QuoteID`` (``<market>.<code>``), ``Code``, ``Name``,
    ``MktNum`` and ``SecurityTypeName``. A row whose market we cannot map to a
    project suffix is dropped rather than emitted with a wrong symbol.

    Args:
        row: One ``QuotationCodeTable.Data`` element.

    Returns:
        A candidate dict, or ``None`` when the row is unusable.
    """
    quote_id = row.get("QuoteID")
    market = ""
    code = str(row.get("Code") or "").strip()
    if isinstance(quote_id, str) and "." in quote_id:
        market, _, qid_code = quote_id.partition(".")
        code = code or qid_code.strip()
    else:
        market = str(row.get("MktNum") or "").strip()
    suffix = _EASTMONEY_SUFFIX_BY_MARKET.get(market)
    if not suffix or not code:
        return None

    symbol = _format_symbol(code, suffix)
    if symbol is None:
        return None
    name = str(row.get("Name") or "").strip() or None
    sec_type = str(row.get("SecurityTypeName") or "").strip() or None
    return {
        "symbol": symbol,
        "name": name,
        "market": _MARKET_BY_SUFFIX.get(suffix, suffix.lower()),
        "type": sec_type,
        "source": "eastmoney",
    }


def _format_symbol(code: str, suffix: str) -> Optional[str]:
    """Render a bare code + suffix into the project symbol convention.

    HK codes are zero-padded to five digits to match the loader/secid scheme.

    Args:
        code: Bare instrument code (e.g. ``"600519"``, ``"700"``, ``"AAPL"``).
        suffix: One of ``SH``/``SZ``/``BJ``/``HK``/``US``.

    Returns:
        The formatted symbol (``"600519.SH"``, ``"00700.HK"``, ``"AAPL.US"``),
        or ``None`` when the code is empty.
    """
    code = code.strip().upper()
    if not code:
        return None
    if suffix == "HK":
        return f"{code.zfill(5)}.HK"
    return f"{code}.{suffix}"


def _search_yahoo(query: str) -> tuple[List[Dict[str, Any]], str]:
    """Query Yahoo's search endpoint and normalize the quote candidates.

    Args:
        query: Free-text name or ticker fragment.

    Returns:
        ``(candidates, status)`` where ``status`` is ``"ok"`` on success or a
        short error string when the source failed (candidates is then empty).
    """
    try:
        quotes = yahoo_client.search(query)
    except Exception as exc:  # noqa: BLE001 - one source failing is non-fatal
        logger.warning("yahoo search failed for %r: %s", query, exc)
        return [], f"yahoo search failed: {exc}"

    candidates: List[Dict[str, Any]] = []
    for quote in quotes[:_PER_SOURCE_CAP]:
        candidate = _yahoo_candidate(quote)
        if candidate is not None:
            candidates.append(candidate)
    return candidates, "ok"


def _yahoo_candidate(quote: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Map one Yahoo search quote to a normalized candidate, or ``None``.

    Yahoo carries US tickers bare and HK tickers as ``0700.HK``. We translate
    those into the project convention (``AAPL.US`` / ``00700.HK``) and leave
    other instruments (crypto, indices, FX) on their native Yahoo symbol.

    Args:
        quote: One element of Yahoo search's ``quotes`` list.

    Returns:
        A candidate dict, or ``None`` when the quote has no symbol.
    """
    raw_symbol = str(quote.get("symbol") or "").strip()
    if not raw_symbol:
        return None
    symbol, market = _from_yahoo_symbol(raw_symbol, quote)
    name = (
        str(quote.get("shortname") or quote.get("longname") or "").strip() or None
    )
    return {
        "symbol": symbol,
        "name": name,
        "market": market,
        "type": str(quote.get("quoteType") or "").strip().lower() or None,
        "exchange": str(quote.get("exchange") or "").strip() or None,
        "source": "yahoo",
    }


def _from_yahoo_symbol(raw_symbol: str, quote: Dict[str, Any]) -> tuple[str, str]:
    """Translate a Yahoo symbol into the project convention + market label.

    Args:
        raw_symbol: The Yahoo-side symbol (e.g. ``AAPL``, ``0700.HK``, ``BTC-USD``).
        quote: The full Yahoo quote, used to distinguish a bare US equity from a
            crypto/index instrument via ``quoteType``.

    Returns:
        ``(symbol, market)`` in the project convention.
    """
    upper = raw_symbol.upper()
    if upper.endswith(".HK"):
        base = raw_symbol[: -len(".HK")].lstrip("0") or "0"
        return f"{base.zfill(5)}.HK", "hk"
    quote_type = str(quote.get("quoteType") or "").strip().upper()
    if quote_type == "EQUITY" and "." not in raw_symbol and "-" not in raw_symbol:
        return f"{upper}.US", "us"
    # Crypto, indices, FX, ETFs on non-HK exchanges: keep Yahoo's native symbol.
    return raw_symbol, "global"


def _merge_candidates(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """De-duplicate candidates by symbol, preserving first-seen order.

    When two sources resolve the same symbol the first hit wins and the second
    source name is appended to a ``also_from`` list so provenance is not lost.

    Args:
        candidates: Raw candidates from every source, in fan-out order.

    Returns:
        A de-duplicated candidate list (immutable inputs are copied, not mutated).
    """
    by_symbol: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    for candidate in candidates:
        symbol = candidate.get("symbol")
        if not symbol:
            continue
        if symbol not in by_symbol:
            by_symbol[symbol] = dict(candidate)
            order.append(symbol)
            continue
        existing = by_symbol[symbol]
        other = candidate.get("source")
        if other and other != existing.get("source"):
            also = list(existing.get("also_from") or [])
            if other not in also:
                also.append(other)
            merged = dict(existing)
            merged["also_from"] = also
            # Backfill a missing name from the duplicate hit.
            if not merged.get("name") and candidate.get("name"):
                merged["name"] = candidate["name"]
            by_symbol[symbol] = merged
    return [by_symbol[sym] for sym in order]


def _enrich_us_cik(
    candidates: List[Dict[str, Any]],
) -> tuple[List[Dict[str, Any]], str]:
    """Return new candidates with a SEC CIK attached to U.S.-equity rows.

    Only ``.US`` equity symbols are looked up; the SEC table maps bare tickers
    to a zero-padded 10-digit CIK. A lookup failure stops further lookups and is
    reported via the status; resolved CIKs found before it still apply.

    Args:
        candidates: Merged candidate rows (left unmodified).

    Returns:
        ``(new_candidates, status)`` where ``status`` is :data:`_NO_US` when no
        U.S. equity was present, ``"ok"`` on a clean pass, or a short error
        string when a SEC lookup failed.
    """
    has_us = any(
        isinstance(c.get("symbol"), str) and c["symbol"].upper().endswith(".US")
        for c in candidates
    )
    if not has_us:
        return candidates, _NO_US

    status = "ok"
    out: List[Dict[str, Any]] = []
    for candidate in candidates:
        symbol = candidate.get("symbol")
        if status == "ok" and isinstance(symbol, str) and symbol.upper().endswith(".US"):
            ticker = symbol[: -len(".US")]
            try:
                cik = sec_edgar_client.cik_for(ticker)
            except Exception as exc:  # noqa: BLE001 - enrichment failure is non-fatal
                logger.warning("sec cik_for failed for %s: %s", ticker, exc)
                status = f"sec lookup failed: {exc}"
                out.append(candidate)
                continue
            if cik:
                out.append({**candidate, "cik": cik})
                continue
        out.append(candidate)
    return out, status


def _error(message: str) -> str:
    """Render a failure envelope as a JSON string."""
    return json.dumps({"ok": False, "error": message}, ensure_ascii=False)
