"""Official Bitget MCP client helpers.

The official Bitget server is a stdio MCP package distributed as
``@bitget-ai/bitget-agent-mcp``. This module keeps all process/bootstrap
details in one place so routes, trading connector reads, and agent tools call
the same execution layer.
"""

from __future__ import annotations

import json
import os
import threading
import time as _time
from pathlib import Path
from typing import Any

from src.config.loader import load_agent_config
from src.config.schema import MCPServerConfig
from src.tools.mcp import MCPServerAdapter


# ---------------------------------------------------------------------------
# In-memory TTL cache for MCP call results
# ---------------------------------------------------------------------------
# The official Bitget MCP runs as a stdio subprocess (``npx -y @bitget-ai/...``).
# Each ``call_bitget_tool`` invocation starts a new Node process, so caching the
# results for a short window avoids repeated cold starts and makes the Markets tab
# feel instantaneous on repeated loads.

class _TTLCache:
    """Thread-safe in-memory cache with per-key TTL."""

    def __init__(self, default_ttl: float = 30.0) -> None:
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()
        self._default_ttl = default_ttl

    def get(self, key: str) -> Any | None:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if _time.monotonic() > expires_at:
                del self._store[key]
                return None
            return value

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        with self._lock:
            self._store[key] = (_time.monotonic() + (ttl or self._default_ttl), value)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


_market_cache = _TTLCache(default_ttl=30.0)

BITGET_SERVER_NAME = "bitget"
BITGET_MCP_PACKAGE = "@bitget-ai/bitget-agent-mcp"
BITGET_MCP_COMMAND = "npx"
BITGET_MCP_ARGS = ("-y", BITGET_MCP_PACKAGE)
BITGET_SAFE_TOOLS = (
    "discover",
    "market",
    "account_overview",
    "account_config",
    "order",
    "position",
    "strategy_order",
)
BITGET_PUBLIC_TOOLS = ("discover", "market")
BITGET_ENV_KEYS = (
    "BITGET_API_KEY",
    "BITGET_SECRET_KEY",
    "BITGET_PASSPHRASE",
    "BITGET_API_BASE_URL",
    "BITGET_TIMEOUT_MS",
    "BITGET_MAX_RETRIES",
)
SECRET_PLACEHOLDERS = {
    "",
    "your_bitget_api_key",
    "your_bitget_secret_key",
    "your_bitget_passphrase",
}
DEFAULT_PRODUCT_TYPE = "USDT-FUTURES"
DEFAULT_MARGIN_MODE = "isolated"

_AGENT_DIR = Path(__file__).resolve().parents[2]
_USER_ENV = Path.home() / ".vibe-trading" / ".env"
_LEGACY_ENV = _AGENT_DIR / ".env"


def bitget_mcp_seed_config(*, read_only: bool = False, paper_trading: bool | None = None) -> dict[str, Any]:
    """Return a copy-pasteable ``mcpServers.bitget`` seed."""
    return default_bitget_mcp_config(read_only=read_only, paper_trading=paper_trading).model_dump(
        by_alias=True,
        exclude_defaults=True,
    )


def default_bitget_mcp_config(*, read_only: bool = False, paper_trading: bool | None = None) -> MCPServerConfig:
    """Build the built-in official Bitget MCP stdio configuration."""
    args = list(BITGET_MCP_ARGS)
    if read_only:
        args.append("--read-only")
    elif _paper_trading_enabled() if paper_trading is None else paper_trading:
        args.append("--paper-trading")
    return MCPServerConfig(
        command=BITGET_MCP_COMMAND,
        args=args,
        env=_bitget_process_env(),
        enabled_tools=list(BITGET_SAFE_TOOLS),
        tool_timeout=30.0,
        init_timeout=30.0,
    )


def call_bitget_tool(
    remote_name: str,
    arguments: dict[str, Any] | None = None,
    *,
    read_only: bool = False,
) -> dict[str, Any]:
    """Call one safe official Bitget MCP tool and normalize the adapter envelope."""
    remote = str(remote_name or "").strip()
    if remote not in BITGET_SAFE_TOOLS:
        return {
            "status": "error",
            "server": BITGET_SERVER_NAME,
            "remote_tool": remote,
            "error": f"Bitget MCP tool '{remote}' is not allowed by Vibe-Trading",
        }
    if read_only and remote not in BITGET_PUBLIC_TOOLS and remote not in {"account_overview", "order", "position", "strategy_order"}:
        return {
            "status": "error",
            "server": BITGET_SERVER_NAME,
            "remote_tool": remote,
            "error": f"Bitget MCP tool '{remote}' is not available through the read-only path",
        }

    server = _configured_or_default_config(read_only=read_only)
    enabled = list(getattr(server, "enabled_tools", None) or [])
    if "*" not in enabled and remote not in enabled:
        return {
            "status": "error",
            "server": BITGET_SERVER_NAME,
            "remote_tool": remote,
            "error": f"Bitget MCP tool '{remote}' is not enabled",
            "enabled_tools": enabled,
        }

    adapter = MCPServerAdapter(BITGET_SERVER_NAME, server)
    return adapter.call_tool(remote, dict(arguments or {}))


def call_market(arguments: dict[str, Any], *, cache_ttl: float | None = None) -> dict[str, Any]:
    """Call the Bitget MCP public ``market`` verb with optional caching."""
    if cache_ttl is not None and cache_ttl > 0:
        cache_key = f"market:{json.dumps(arguments, sort_keys=True)}"
        cached = _market_cache.get(cache_key)
        if cached is not None:
            return cached
        result = call_bitget_tool("market", arguments, read_only=True)
        if str(result.get("status", "")).lower() == "ok":
            _market_cache.set(cache_key, result, ttl=cache_ttl)
        return result
    return call_bitget_tool("market", arguments, read_only=True)


def extract_bitget_payload(result: dict[str, Any]) -> dict[str, Any]:
    """Extract the structured Bitget payload or raise a readable error."""
    if str(result.get("status", "")).lower() != "ok":
        raise RuntimeError(str(result.get("error") or "Bitget MCP call failed"))
    payload = result.get("structured_content") or result.get("data")
    if isinstance(payload, dict):
        if payload.get("ok") is False:
            raise RuntimeError(str(payload.get("msg") or payload.get("message") or "Bitget rejected the request"))
        return payload
    text = result.get("text")
    if isinstance(text, str) and text.strip():
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Bitget MCP returned non-JSON text: {text[:120]}") from exc
        if isinstance(parsed, dict):
            return parsed
    raise RuntimeError("Bitget MCP returned an unexpected payload")


def fetch_candles(
    *,
    symbol: str,
    category: str = DEFAULT_PRODUCT_TYPE,
    interval: str = "5m",
    lookback: int = 300,
) -> list[dict[str, Any]]:
    """Fetch recent Bitget candles through the official MCP server.

    Results are cached for 30 seconds to avoid repeated MCP subprocess spawns.
    """
    category = normalize_category(category)
    symbol = normalize_symbol(symbol)
    interval = normalize_interval(interval)
    limit = max(20, min(int(lookback), 1500))
    result = call_market(
        {
            "action": "candles",
            "category": category,
            "symbol": symbol,
            "interval": interval,
            "limit": str(limit),
            "view": "summary",
        },
        cache_ttl=30.0,
    )
    payload = extract_bitget_payload(result)
    rows = payload.get("data")
    if not isinstance(rows, list):
        raise RuntimeError(f"No Bitget candle data for {symbol}")
    return [_normalize_candle_row(row) for row in rows if _normalize_candle_row(row) is not None][-limit:]


def fetch_candles_history(
    *,
    symbol: str,
    category: str = DEFAULT_PRODUCT_TYPE,
    interval: str = "5m",
    start_ms: int,
    end_ms: int,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Fetch Bitget historical candles for a bounded millisecond range."""
    category = normalize_category(category)
    symbol = normalize_symbol(symbol)
    interval = normalize_interval(interval)
    page_limit = max(20, min(int(limit), 1500))
    result = call_market(
        {
            "action": "candlesHistory",
            "category": category,
            "symbol": symbol,
            "interval": interval,
            "startTime": str(int(start_ms)),
            "endTime": str(int(end_ms)),
            "limit": str(page_limit),
            "view": "summary",
        }
    )
    payload = extract_bitget_payload(result)
    rows = payload.get("data")
    if not isinstance(rows, list):
        raise RuntimeError(f"No Bitget historical candle data for {symbol}")
    normalized = [_normalize_candle_row(row) for row in rows if _normalize_candle_row(row) is not None]
    return [row for row in normalized if row is not None]


def fetch_ticker(*, symbol: str, category: str = DEFAULT_PRODUCT_TYPE) -> dict[str, Any]:
    """Fetch a Bitget ticker snapshot through MCP (cached for 15s)."""
    result = call_market(
        {
            "action": "tickers",
            "category": normalize_category(category),
            "symbol": normalize_symbol(symbol),
            "view": "summary",
        },
        cache_ttl=15.0,
    )
    payload = extract_bitget_payload(result)
    rows = payload.get("data")
    if isinstance(rows, list) and rows:
        first = rows[0]
        return first if isinstance(first, dict) else {}
    return {}


def fetch_instruments(category: str = DEFAULT_PRODUCT_TYPE) -> list[dict[str, Any]]:
    """Fetch Bitget instrument metadata through MCP."""
    result = call_market({"action": "instruments", "category": normalize_category(category), "view": "summary"})
    payload = extract_bitget_payload(result)
    rows = payload.get("data")
    if not isinstance(rows, list):
        raise RuntimeError(f"No Bitget instrument data for {category}")
    return [row for row in rows if isinstance(row, dict)]


def bitget_connection_status() -> dict[str, Any]:
    """Return local Bitget MCP/configuration status without exposing secrets."""
    env = _merged_env_values()
    credentials = {
        "api_key": _is_real_secret(env.get("BITGET_API_KEY", "")),
        "secret_key": _is_real_secret(env.get("BITGET_SECRET_KEY", "")),
        "passphrase": _is_real_secret(env.get("BITGET_PASSPHRASE", "")),
    }
    configured = all(credentials.values())
    try:
        result = call_bitget_tool("discover", {}, read_only=True)
        available = str(result.get("status", "")).lower() == "ok"
        error = None if available else str(result.get("error") or "Bitget MCP discover failed")
    except Exception as exc:  # noqa: BLE001 - status endpoint must be best-effort
        available = False
        error = str(exc)
    return {
        "status": "ok" if available else "error",
        "server": BITGET_SERVER_NAME,
        "mcp_package": BITGET_MCP_PACKAGE,
        "mcp_available": available,
        "credentials_configured": configured,
        "credential_fields": credentials,
        "environment": bitget_environment(),
        "default_product_type": default_product_type(),
        "default_margin_mode": default_margin_mode(),
        "error": error,
    }


def normalize_symbol(symbol: str) -> str:
    """Normalize a UI/agent symbol into Bitget's ``BTCUSDT`` form."""
    value = str(symbol or "").strip().upper().replace("/", "").replace("-", "")
    if value.endswith("USD") and not value.endswith("USDT"):
        value = f"{value[:-3]}USDT"
    
    known_quotes = ("USDT", "USDC", "BTC", "ETH", "BGB", "EUR")
    if value and not any(value.endswith(q) for q in known_quotes):
        value = f"{value}USDT"
        
    return value


def normalize_category(category: str | None) -> str:
    """Normalize product category aliases into Bitget UTA category names."""
    value = str(category or default_product_type()).strip().upper().replace("_", "-")
    aliases = {
        "FUTURES": "USDT-FUTURES",
        "PERP": "USDT-FUTURES",
        "PERPS": "USDT-FUTURES",
        "USDT": "USDT-FUTURES",
        "SPOT": "SPOT",
        "MARGIN": "MARGIN",
        "COIN-FUTURES": "COIN-FUTURES",
        "USDC-FUTURES": "USDC-FUTURES",
        "USDT-FUTURES": "USDT-FUTURES",
    }
    return aliases.get(value, DEFAULT_PRODUCT_TYPE)


def normalize_interval(interval: str) -> str:
    """Normalize timeframe aliases into Bitget MCP interval tokens."""
    value = str(interval or "15m").strip()
    aliases = {
        "1h": "1H",
        "60m": "1H",
        "4h": "4H",
        "1d": "1D",
        "1day": "1D",
        "1w": "1W",
        "1week": "1W",
        "weekly": "1W",
        "15min": "15m",
        "5min": "5m",
        "3min": "3m",
        "1min": "1m",
    }
    return aliases.get(value.casefold(), value)


def bitget_environment() -> str:
    return (_merged_env_values().get("BITGET_ENV") or "production").strip().lower() or "production"


def default_product_type() -> str:
    return normalize_category(_merged_env_values().get("BITGET_DEFAULT_PRODUCT_TYPE") or DEFAULT_PRODUCT_TYPE)


def default_margin_mode() -> str:
    value = (_merged_env_values().get("BITGET_DEFAULT_MARGIN_MODE") or DEFAULT_MARGIN_MODE).strip().lower()
    return "cross" if value.startswith("cross") else "isolated"


def _configured_or_default_config(*, read_only: bool) -> MCPServerConfig:
    config = load_agent_config()
    server = (config.mcp_servers or {}).get(BITGET_SERVER_NAME)
    if server is not None:
        return server
    return default_bitget_mcp_config(read_only=read_only)


def _normalize_candle_row(row: Any) -> dict[str, Any] | None:
    if not isinstance(row, (list, tuple)) or len(row) < 6:
        return None
    try:
        return {
            "time": str(row[0]),
            "open": float(row[1]),
            "high": float(row[2]),
            "low": float(row[3]),
            "close": float(row[4]),
            "volume": float(row[5]),
            "turnover": float(row[6]) if len(row) > 6 and row[6] not in (None, "") else None,
        }
    except (TypeError, ValueError):
        return None


def _paper_trading_enabled() -> bool:
    return bitget_environment() in {"paper", "demo", "sandbox", "testnet"}


def _bitget_process_env() -> dict[str, str]:
    values = _merged_env_values()
    env = {key: values[key] for key in BITGET_ENV_KEYS if values.get(key)}
    return env


def _merged_env_values() -> dict[str, str]:
    values: dict[str, str] = {}
    for path in (_LEGACY_ENV, _USER_ENV):
        values.update(_read_dotenv(path))
    values.update({key: value for key, value in os.environ.items() if key.startswith("BITGET_")})
    return values


def _read_dotenv(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    result: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return result
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key.lower().startswith("export "):
            key = key[7:].strip()
        if key.startswith("BITGET_"):
            result[key] = _strip_dotenv_value(value)
    return result


def _strip_dotenv_value(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1].strip()
    if " #" in value:
        value = value.split(" #", 1)[0].rstrip()
    return value.strip()


def _is_real_secret(value: str) -> bool:
    return value.strip() not in SECRET_PLACEHOLDERS
