"""Bitget symbol metadata search and resolution."""

from __future__ import annotations

import time
from typing import Any

from src.services.bitget_mcp import fetch_instruments, normalize_category, normalize_symbol

_CACHE_TTL_SECONDS = 900
_MAX_LIMIT = 25
_DEFAULT_LIMIT = 10
_CACHE: dict[str, tuple[float, list[dict[str, Any]]]] = {}

_ALIASES = {
    "bitcoin": "BTC",
    "btc": "BTC",
    "ethereum": "ETH",
    "ether": "ETH",
    "eth": "ETH",
    "solana": "SOL",
    "sol": "SOL",
    "dogecoin": "DOGE",
    "doge": "DOGE",
    "ripple": "XRP",
    "xrp": "XRP",
    "pepe": "PEPE",
}


def format_bitget_price(symbol: str, price: float | str | None) -> str:
    """Format price according to Bitget tick size requirements."""
    if price is None or price == "":
        return ""
    try:
        val = float(price)
    except (TypeError, ValueError):
        return str(price)
    if val <= 0:
        return ""
    clean = str(symbol or "").upper()
    if "BTC" in clean:
        return f"{val:.1f}"
    elif "ETH" in clean or "SOL" in clean or "DOGE" in clean or "XRP" in clean:
        return f"{val:.2f}" if val >= 1.0 else f"{val:.4f}"
    elif "PEPE" in clean or val < 0.001:
        return f"{val:.8f}"
    elif val >= 1000:
        return f"{val:.1f}"
    elif val >= 1:
        return f"{val:.2f}"
    else:
        return f"{val:.4f}"


def format_bitget_qty(symbol: str, qty: float | str | None) -> str:
    """Format quantity according to Bitget contract size precision."""
    if qty is None or qty == "":
        return ""
    try:
        val = float(qty)
    except (TypeError, ValueError):
        return str(qty)
    if val <= 0:
        return ""
    clean = str(symbol or "").upper()
    if "BTC" in clean:
        return f"{max(0.001, round(val, 3)):.3f}"
    elif "ETH" in clean:
        return f"{max(0.01, round(val, 2)):.2f}"
    elif "SOL" in clean or "DOGE" in clean or "XRP" in clean:
        return f"{max(0.1, round(val, 1)):.1f}"
    else:
        return f"{max(0.1, round(val, 2)):.2f}"


def search_symbols(query: str, *, category: str | None = None, limit: int = _DEFAULT_LIMIT) -> dict[str, Any]:
    """Search Bitget-supported symbols by name, base coin, or symbol."""
    raw_query = str(query or "").strip()
    if not raw_query:
        return {"status": "error", "error": "query is required", "candidates": []}

    limit = max(1, min(int(limit or _DEFAULT_LIMIT), _MAX_LIMIT))
    categories = [normalize_category(category)] if category else ["SPOT", "USDT-FUTURES"]
    token = _alias_token(raw_query)
    compact = _compact(token)
    wanted_symbol = normalize_symbol(token)

    candidates: list[dict[str, Any]] = []
    errors: dict[str, str] = {}
    for item_category in categories:
        try:
            instruments = _instruments_for_category(item_category)
        except Exception as exc:  # noqa: BLE001 - one category failing is non-fatal
            errors[item_category] = str(exc)
            continue
        for row in instruments:
            candidate = _candidate_from_instrument(row, item_category)
            if candidate is None:
                continue
            score = _score_candidate(candidate, compact, wanted_symbol)
            if score <= 0:
                continue
            candidate["_score"] = score
            candidates.append(candidate)

    candidates.sort(key=lambda item: (-int(item.get("_score", 0)), item.get("category", ""), item.get("symbol", "")))
    trimmed = [{key: value for key, value in item.items() if key != "_score"} for item in candidates[:limit]]
    return {
        "status": "ok",
        "query": raw_query,
        "count": len(trimmed),
        "candidates": trimmed,
        "sources": {"bitget_mcp": "ok" if trimmed else (errors or "no matches")},
    }


def resolve_symbol(query: str, *, category: str | None = None) -> dict[str, Any]:
    """Resolve a query to one Bitget symbol or return ambiguity details."""
    result = search_symbols(query, category=category, limit=_MAX_LIMIT)
    if result.get("status") != "ok":
        return result
    candidates = list(result.get("candidates") or [])
    if not candidates:
        return {"status": "not_found", "query": query, "candidates": []}

    exact = [
        row
        for row in candidates
        if _compact(str(row.get("symbol") or "")) == _compact(normalize_symbol(_alias_token(query)))
        or _compact(str(row.get("base_coin") or "")) == _compact(_alias_token(query))
    ]
    if category and exact:
        return {"status": "ok", "query": query, "symbol": exact[0], "candidates": exact[:5]}
    if len(exact) == 1:
        return {"status": "ok", "query": query, "symbol": exact[0], "candidates": exact}
    if exact:
        return {
            "status": "ambiguous",
            "query": query,
            "message": "Multiple Bitget markets match. Ask the user to choose spot or futures.",
            "candidates": exact[:8],
        }
    if len(candidates) == 1:
        return {"status": "ok", "query": query, "symbol": candidates[0], "candidates": candidates}
    return {
        "status": "ambiguous",
        "query": query,
        "message": "Multiple Bitget symbols match. Ask the user to choose one.",
        "candidates": candidates[:8],
    }


def _instruments_for_category(category: str) -> list[dict[str, Any]]:
    now = time.time()
    cached = _CACHE.get(category)
    if cached and now - cached[0] < _CACHE_TTL_SECONDS:
        return cached[1]
    rows = fetch_instruments(category)
    normalized = [row for row in rows if str(row.get("status") or "").lower() in {"", "online"}]
    _CACHE[category] = (now, normalized)
    return normalized


def _candidate_from_instrument(row: dict[str, Any], category: str) -> dict[str, Any] | None:
    symbol = str(row.get("symbol") or "").strip().upper()
    base = str(row.get("baseCoin") or "").strip().upper()
    quote = str(row.get("quoteCoin") or "").strip().upper()
    if not symbol or not base:
        return None
    return {
        "symbol": symbol,
        "category": category,
        "base_coin": base,
        "quote_coin": quote,
        "market": "crypto",
        "exchange": "bitget",
        "source": "bitget_mcp",
        "type": row.get("type") or row.get("symbolType") or "spot",
        "status": row.get("status") or "online",
        "price_precision": _int_or_none(row.get("pricePrecision")),
        "quantity_precision": _int_or_none(row.get("quantityPrecision")),
        "min_order_qty": row.get("minOrderQty"),
        "min_order_amount": row.get("minOrderAmount"),
        "max_leverage": _int_or_none(row.get("maxLeverage")),
    }


def _score_candidate(candidate: dict[str, Any], compact_query: str, wanted_symbol: str) -> int:
    symbol = str(candidate.get("symbol") or "")
    base = str(candidate.get("base_coin") or "")
    compact_symbol = _compact(symbol)
    compact_base = _compact(base)
    if compact_symbol == _compact(wanted_symbol):
        return 100
    if compact_base == compact_query:
        return 90
    if compact_symbol.startswith(compact_query):
        return 70
    if compact_base.startswith(compact_query):
        return 65
    if compact_query in compact_symbol:
        return 45
    return 0


def _alias_token(query: str) -> str:
    compact = _compact(query)
    return _ALIASES.get(compact, query.strip().upper())


def _compact(value: str) -> str:
    return "".join(ch for ch in str(value or "").casefold() if ch.isalnum())


def _int_or_none(value: Any) -> int | None:
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return None

