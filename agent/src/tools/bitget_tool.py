"""Agent-facing Bitget tools backed by the official Bitget MCP server."""

from __future__ import annotations

import json
from typing import Any

from src.agent.tools import BaseTool
from src.services.bitget_account import get_account_overview, get_connection_status
from src.services.bitget_execution import cancel_order, close_position, execute_confirmed_trade
from src.services.bitget_positions import get_open_orders, get_positions
from src.services.bitget_symbols import search_symbols
from src.services.risk_engine import build_risk_plan
from src.services.signal_engine import build_market_signal, parse_trade_intent
from src.services.trade_confirmation import create_trade_proposal


def _json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, allow_nan=False)


class BitgetStatusTool(BaseTool):
    """Check official Bitget MCP readiness."""

    name = "bitget_status"
    description = "Check whether the official Bitget MCP package is reachable and whether Bitget credentials are configured."
    parameters = {"type": "object", "properties": {}, "required": []}
    repeatable = True
    is_readonly = True

    def execute(self, **_: Any) -> str:
        try:
            return _json(get_connection_status())
        except Exception as exc:  # noqa: BLE001
            return _json({"status": "error", "error": str(exc)})


class BitgetSearchSymbolsTool(BaseTool):
    """Search Bitget supported symbols."""

    name = "bitget_search_symbols"
    description = "Resolve a crypto name/ticker into Bitget-supported symbols and categories, e.g. bitcoin -> BTCUSDT."
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Crypto name, ticker, or Bitget symbol."},
            "category": {
                "type": "string",
                "enum": ["SPOT", "USDT-FUTURES", "COIN-FUTURES", "USDC-FUTURES"],
                "description": "Optional Bitget product category.",
            },
            "limit": {"type": "integer", "default": 10},
        },
        "required": ["query"],
    }
    repeatable = True
    is_readonly = True

    def execute(self, **kwargs: Any) -> str:
        try:
            return _json(
                search_symbols(
                    str(kwargs.get("query") or ""),
                    category=str(kwargs.get("category") or "") or None,
                    limit=int(kwargs.get("limit") or 10),
                )
            )
        except Exception as exc:  # noqa: BLE001
            return _json({"status": "error", "error": str(exc)})


class BitgetAccountTool(BaseTool):
    """Read Bitget account overview through MCP."""

    name = "bitget_account"
    description = "Read Bitget account overview through official MCP. Requires Bitget API credentials for private account data."
    parameters = {
        "type": "object",
        "properties": {
            "category": {"type": "string", "description": "Optional category, e.g. USDT-FUTURES or SPOT."},
            "symbol": {"type": "string", "description": "Optional symbol, e.g. BTCUSDT."},
            "coin": {"type": "string", "description": "Optional coin filter, e.g. USDT."},
        },
        "required": [],
    }
    repeatable = True
    is_readonly = True

    def execute(self, **kwargs: Any) -> str:
        try:
            return _json(
                get_account_overview(
                    category=str(kwargs.get("category") or "") or None,
                    symbol=str(kwargs.get("symbol") or "") or None,
                    coin=str(kwargs.get("coin") or "") or None,
                )
            )
        except Exception as exc:  # noqa: BLE001
            return _json({"status": "error", "error": str(exc)})


class BitgetPositionsTool(BaseTool):
    """Read Bitget futures positions through MCP."""

    name = "bitget_positions"
    description = "Read current Bitget futures positions through official MCP."
    parameters = {
        "type": "object",
        "properties": {
            "category": {"type": "string", "default": "USDT-FUTURES"},
            "symbol": {"type": "string", "description": "Optional symbol filter."},
        },
        "required": [],
    }
    repeatable = True
    is_readonly = True

    def execute(self, **kwargs: Any) -> str:
        try:
            return _json(
                get_positions(
                    category=str(kwargs.get("category") or "USDT-FUTURES"),
                    symbol=str(kwargs.get("symbol") or "") or None,
                )
            )
        except Exception as exc:  # noqa: BLE001
            return _json({"status": "error", "error": str(exc)})


class BitgetOrdersTool(BaseTool):
    """Read Bitget open orders through MCP."""

    name = "bitget_orders"
    description = "Read Bitget open orders through official MCP."
    parameters = BitgetPositionsTool.parameters
    repeatable = True
    is_readonly = True

    def execute(self, **kwargs: Any) -> str:
        try:
            return _json(
                get_open_orders(
                    category=str(kwargs.get("category") or "USDT-FUTURES"),
                    symbol=str(kwargs.get("symbol") or "") or None,
                )
            )
        except Exception as exc:  # noqa: BLE001
            return _json({"status": "error", "error": str(exc)})


class BitgetPrepareTradeTool(BaseTool):
    """Create a Bitget trade proposal without placing an order."""

    name = "bitget_prepare_trade"
    description = (
        "Parse a natural-language crypto trade request, resolve the Bitget symbol, "
        "compute a technical signal and risk plan, and create a trade proposal. "
        "This never places an order; ask the user to confirm before bitget_execute_trade."
    )
    parameters = {
        "type": "object",
        "properties": {
            "prompt": {"type": "string", "description": "The user's full natural-language trade request."},
            "symbol": {"type": "string", "description": "Optional explicit symbol override."},
            "category": {"type": "string", "description": "Optional SPOT or USDT-FUTURES override."},
        },
        "required": ["prompt"],
    }
    repeatable = False
    is_readonly = True

    def execute(self, **kwargs: Any) -> str:
        try:
            prompt = str(kwargs.get("prompt") or "")
            intent = parse_trade_intent(
                prompt,
                category_hint=str(kwargs.get("category") or "") or None,
                symbol_hint=str(kwargs.get("symbol") or "") or None,
            )
            if intent.needs_clarification:
                return _json({"status": "needs_clarification", "message": intent.needs_clarification, "intent": intent.to_dict()})
            signal = build_market_signal(intent)
            if signal.get("status") != "ok":
                return _json({"status": signal.get("status", "error"), "signal": signal, "intent": intent.to_dict()})
            risk = build_risk_plan(intent.to_dict(), signal)
            proposal = create_trade_proposal(prompt=prompt, intent=intent.to_dict(), signal=signal, risk=risk)
            return _json(
                {
                    "status": "ok",
                    "intent": intent.to_dict(),
                    "proposal": proposal,
                    "question": "Would you like me to execute this trade?",
                }
            )
        except Exception as exc:  # noqa: BLE001
            return _json({"status": "error", "error": str(exc)})


class BitgetExecuteTradeTool(BaseTool):
    """Execute a previously confirmed Bitget trade proposal."""

    name = "bitget_execute_trade"
    description = (
        "Execute a stored Bitget trade proposal through official MCP after the user has explicitly confirmed. "
        "Requires proposal_id from bitget_prepare_trade and confirmation_text copied from the user's affirmative reply."
    )
    parameters = {
        "type": "object",
        "properties": {
            "proposal_id": {"type": "string"},
            "confirmation_text": {"type": "string", "description": "User's explicit affirmative confirmation text."},
            "dry_run": {"type": "boolean", "default": False},
        },
        "required": ["proposal_id", "confirmation_text"],
    }
    repeatable = False
    is_readonly = False

    def execute(self, **kwargs: Any) -> str:
        try:
            return _json(
                execute_confirmed_trade(
                    str(kwargs.get("proposal_id") or ""),
                    confirmation_text=str(kwargs.get("confirmation_text") or ""),
                    dry_run=bool(kwargs.get("dry_run", False)),
                )
            )
        except Exception as exc:  # noqa: BLE001
            return _json({"status": "error", "error": str(exc)})


class BitgetCancelOrderTool(BaseTool):
    """Cancel a Bitget order through MCP."""

    name = "bitget_cancel_order"
    description = "Cancel one Bitget order by order id through official MCP. Cancelling is risk-reducing but still logged by the MCP response."
    parameters = {
        "type": "object",
        "properties": {
            "order_id": {"type": "string"},
            "category": {"type": "string", "default": "USDT-FUTURES"},
            "symbol": {"type": "string"},
        },
        "required": ["order_id"],
    }
    repeatable = False
    is_readonly = False

    def execute(self, **kwargs: Any) -> str:
        try:
            return _json(
                cancel_order(
                    order_id=str(kwargs.get("order_id") or ""),
                    category=str(kwargs.get("category") or "USDT-FUTURES"),
                    symbol=str(kwargs.get("symbol") or "") or None,
                )
            )
        except Exception as exc:  # noqa: BLE001
            return _json({"status": "error", "error": str(exc)})


class BitgetClosePositionTool(BaseTool):
    """Close one Bitget futures position after explicit confirmation."""

    name = "bitget_close_position"
    description = "Close one Bitget futures position at market through official MCP. Requires explicit user confirmation text."
    parameters = {
        "type": "object",
        "properties": {
            "symbol": {"type": "string"},
            "category": {"type": "string", "default": "USDT-FUTURES"},
            "pos_side": {"type": "string", "enum": ["long", "short"]},
            "confirmation_text": {"type": "string"},
            "dry_run": {"type": "boolean", "default": False},
        },
        "required": ["symbol", "confirmation_text"],
    }
    repeatable = False
    is_readonly = False

    def execute(self, **kwargs: Any) -> str:
        try:
            return _json(
                close_position(
                    category=str(kwargs.get("category") or "USDT-FUTURES"),
                    symbol=str(kwargs.get("symbol") or ""),
                    pos_side=str(kwargs.get("pos_side") or "") or None,
                    confirmation_text=str(kwargs.get("confirmation_text") or ""),
                    dry_run=bool(kwargs.get("dry_run", False)),
                )
            )
        except Exception as exc:  # noqa: BLE001
            return _json({"status": "error", "error": str(exc)})

