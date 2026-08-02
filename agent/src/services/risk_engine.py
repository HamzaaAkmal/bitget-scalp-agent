"""Bitget trade risk planning helpers."""

from __future__ import annotations

import math
import os
from typing import Any

from src.services.bitget_mcp import default_margin_mode, normalize_category


def build_risk_plan(intent: dict[str, Any], signal: dict[str, Any]) -> dict[str, Any]:
    """Convert a signal into a bounded trade proposal risk plan."""
    direction = str(signal.get("direction") or "WAIT").upper()
    entry = _finite_float(signal.get("entry"))
    category = normalize_category(intent.get("category"))
    if direction == "WAIT" or entry is None or entry <= 0:
        return {
            "direction": "WAIT",
            "entry": entry,
            "stop_loss": None,
            "take_profit": None,
            "risk_reward": None,
            "suggested_leverage": 1,
            "suggested_margin_usdt": None,
            "suggested_notional_usdt": None,
            "suggested_qty": None,
            "warnings": ["No executable trade is suggested while direction is WAIT."],
        }

    max_leverage = _env_int("MAX_LEVERAGE", 10)
    default_leverage = _env_int("DEFAULT_LEVERAGE", 3)
    requested_leverage = intent.get("leverage")
    leverage = int(requested_leverage or default_leverage)
    leverage = 1 if category == "SPOT" else max(1, min(leverage, max_leverage))

    stop_ratio = _env_float("DEFAULT_STOP_LOSS_RATIO", 1.0) / 100.0
    take_profit_ratio = _env_float("DEFAULT_TAKE_PROFIT_RATIO", 2.0) / 100.0
    if direction == "BUY":
        stop_loss = entry * (1 - stop_ratio)
        take_profit = entry * (1 + take_profit_ratio)
    else:
        stop_loss = entry * (1 + stop_ratio)
        take_profit = entry * (1 - take_profit_ratio)

    margin = _finite_float(intent.get("margin_usdt"))
    if margin is None:
        margin = _env_float("DEFAULT_TRADE_MARGIN_USDT", 25.0)
    margin = max(0.0, margin)
    notional = margin * leverage
    qty = notional / entry if entry else None
    precision = _quantity_precision(signal.get("symbol"))
    if qty is not None:
        qty = _round_qty(qty, precision)

    risk = abs(entry - stop_loss)
    reward = abs(take_profit - entry)
    warnings: list[str] = []
    if requested_leverage and int(requested_leverage) > max_leverage:
        warnings.append(f"Requested leverage was capped at {max_leverage}x.")
    if category != "SPOT" and leverage > 5:
        warnings.append("High leverage increases liquidation risk; keep margin small and stops firm.")

    price_prec = _price_precision(signal.get("symbol"))

    return {
        "direction": direction,
        "entry": _round_price(entry, price_prec),
        "stop_loss": _round_price(stop_loss, price_prec),
        "take_profit": _round_price(take_profit, price_prec),
        "risk_reward": round(reward / risk, 2) if risk else None,
        "expected_duration": _expected_duration(str(intent.get("timeframe") or "15m")),
        "suggested_leverage": leverage,
        "suggested_margin_usdt": round(margin, 4),
        "suggested_notional_usdt": round(notional, 4),
        "suggested_qty": qty,
        "margin_mode": str(intent.get("margin_mode") or default_margin_mode()),
        "max_risk_per_trade_percent": _env_float("MAX_RISK_PER_TRADE_PERCENT", 1.0),
        "max_daily_loss_percent": _env_float("MAX_DAILY_LOSS_PERCENT", 3.0),
        "warnings": warnings,
    }


def _expected_duration(timeframe: str) -> str:
    tf = timeframe.upper()
    if tf in {"1M", "3M", "5M"}:
        return "minutes to a few hours"
    if tf in {"15M", "30M", "1H"}:
        return "several hours"
    if tf == "4H":
        return "one to three days"
    return "multi-day"


def _quantity_precision(symbol_info: Any) -> int:
    if isinstance(symbol_info, dict):
        raw = symbol_info.get("quantity_precision")
        if raw is not None:
            try:
                return max(0, min(12, int(raw)))
            except (TypeError, ValueError):
                pass
    return 6


def _price_precision(symbol_info: Any) -> int:
    if isinstance(symbol_info, dict):
        raw = symbol_info.get("price_precision")
        if raw is not None:
            try:
                return max(0, min(12, int(raw)))
            except (TypeError, ValueError):
                pass
    return 2


def _round_qty(value: float, precision: int) -> float:
    if not math.isfinite(value) or value <= 0:
        return 0.0
    return round(value, precision)


def _round_price(value: float, precision: int | None = None) -> float:
    if not math.isfinite(value) or value <= 0:
        return 0.0
    if precision is not None:
        return round(value, precision)
    if value >= 100:
        return round(value, 2)
    if value >= 1:
        return round(value, 4)
    return round(value, 8)


def _finite_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _env_float(key: str, default: float) -> float:
    try:
        return float(os.environ.get(key, "") or default)
    except ValueError:
        return default


def _env_int(key: str, default: int) -> int:
    try:
        return int(float(os.environ.get(key, "") or default))
    except ValueError:
        return default

