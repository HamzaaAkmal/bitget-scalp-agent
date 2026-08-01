"""Built-in Bitget connector profiles."""

from __future__ import annotations

from src.trading.types import READ_CAPABILITIES, TradingProfile

BITGET_CAPABILITIES = READ_CAPABILITIES + (
    "symbols.search",
    "account.futures.read",
    "account.spot.read",
    "orders.place.requires_confirmation",
    "orders.cancel",
    "positions.close.requires_confirmation",
    "leverage.modify.requires_confirmation",
    "tpsl.modify.requires_confirmation",
)

BITGET_PROFILES: tuple[TradingProfile, ...] = (
    TradingProfile(
        id="bitget-live-mcp-readonly",
        connector="bitget",
        label="Bitget Live · Official MCP Read-Only",
        environment="live",
        transport="remote_mcp",
        capabilities=READ_CAPABILITIES + ("symbols.search", "account.futures.read", "account.spot.read"),
        readonly=True,
        config={"server": "bitget", "default_product_type": "USDT-FUTURES"},
        notes=(
            "Reads Bitget market/account state through the official @bitget-ai/bitget-agent-mcp package. "
            "No order placement is exposed by this profile."
        ),
    ),
    TradingProfile(
        id="bitget-live-mcp",
        connector="bitget",
        label="Bitget Live · Official MCP Trading",
        environment="live",
        transport="remote_mcp",
        capabilities=BITGET_CAPABILITIES,
        readonly=False,
        config={"server": "bitget", "default_product_type": "USDT-FUTURES"},
        notes=(
            "Executes Bitget spot/futures orders through official MCP only after a stored trade proposal "
            "has received explicit user confirmation. Withdrawal permissions are never required."
        ),
    ),
)

