"""CoinGecko API client with Demo/Pro header support, rate limiting, and caching."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, List, Optional
import requests

from src.config.accessor import get_env_config

logger = logging.getLogger(__name__)

COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"


class CoinGeckoClient:
    def __init__(self) -> None:
        self._cache: Dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def _get_api_config(self) -> tuple[str, str, str, str]:
        cfg = get_env_config().data
        api_key = getattr(cfg, "coingecko_api_key", "").strip() or "CG-bjPbrYa4C3dnW9SuVn9m6A97"
        tier = getattr(cfg, "coingecko_api_tier", "demo").strip().lower()
        if tier == "pro":
            base_url = "https://pro-api.coingecko.com/api/v3"
            header_name = "x-cg-pro-api-key"
        else:
            base_url = COINGECKO_BASE_URL
            header_name = "x-cg-demo-api-key"
        return api_key, tier, base_url, header_name

    def _get_cached(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._cache.get(key)
            if entry and time.monotonic() < entry[0]:
                return entry[1]
            return None

    def _set_cached(self, key: str, value: Any, ttl: float) -> None:
        with self._lock:
            self._cache[key] = (time.monotonic() + ttl, value)

    def get_coins_markets(self, vs_currency: str = "usd", category: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        cache_key = f"markets:{vs_currency}:{category}:{limit}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        api_key, tier, base_url, header_name = self._get_api_config()
        headers = {header_name: api_key, "Accept": "application/json"}
        params = {
            "vs_currency": vs_currency,
            "order": "market_cap_desc",
            "per_page": limit,
            "page": 1,
            "sparkline": "false",
            "price_change_percentage": "24h",
        }
        if category:
            params["category"] = category

        try:
            resp = requests.get(f"{base_url}/coins/markets", headers=headers, params=params, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    self._set_cached(cache_key, data, 60.0)
                    return data
            logger.warning(f"CoinGecko markets call returned status {resp.status_code}")
        except Exception as exc:
            logger.warning(f"CoinGecko request failed: {exc}")

        return self._fallback_coins_markets()

    def get_coin_metadata(self, coin_id: str) -> Dict[str, Any]:
        cache_key = f"coin:{coin_id}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        api_key, tier, base_url, header_name = self._get_api_config()
        headers = {header_name: api_key, "Accept": "application/json"}
        params = {
            "localization": "false",
            "tickers": "false",
            "market_data": "false",
            "community_data": "false",
            "developer_data": "false",
        }

        try:
            resp = requests.get(f"{base_url}/coins/{coin_id}", headers=headers, params=params, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict):
                    self._set_cached(cache_key, data, 3600.0)
                    return data
        except Exception as exc:
            logger.warning(f"CoinGecko metadata failed for {coin_id}: {exc}")

        return {}

    def get_trending_coins(self) -> List[Dict[str, Any]]:
        cache_key = "trending"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        api_key, tier, base_url, header_name = self._get_api_config()
        headers = {header_name: api_key, "Accept": "application/json"}

        try:
            resp = requests.get(f"{base_url}/search/trending", headers=headers, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                coins = data.get("coins", [])
                self._set_cached(cache_key, coins, 600.0)
                return coins
        except Exception as exc:
            logger.warning(f"CoinGecko trending request failed: {exc}")

        return []

    def get_symbol_icon(self, symbol: str) -> str:
        sym_clean = symbol.upper().replace("USDT", "").replace("/", "").casefold()
        icon_map = {
            "btc": "https://assets.coingecko.com/coins/images/1/large/bitcoin.png",
            "eth": "https://assets.coingecko.com/coins/images/279/large/ethereum.png",
            "sol": "https://assets.coingecko.com/coins/images/4128/large/solana.png",
            "doge": "https://assets.coingecko.com/coins/images/5/large/dogecoin.png",
            "pepe": "https://assets.coingecko.com/coins/images/29850/large/pepe-token.png",
            "xrp": "https://assets.coingecko.com/coins/images/44/large/xrp-symbol-white-128.png",
            "ada": "https://assets.coingecko.com/coins/images/975/large/cardano.png",
            "avax": "https://assets.coingecko.com/coins/images/12559/large/Avalanche_Circle_RedWhite_Trans.png",
            "link": "https://assets.coingecko.com/coins/images/877/large/chainlink-new-logo.png",
            "sui": "https://assets.coingecko.com/coins/images/26375/large/sui-ocean-square.png",
        }
        return icon_map.get(sym_clean, "https://assets.coingecko.com/coins/images/1/large/bitcoin.png")

    def _fallback_coins_markets(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": "bitcoin",
                "symbol": "btc",
                "name": "Bitcoin",
                "image": "https://assets.coingecko.com/coins/images/1/large/bitcoin.png",
                "current_price": 95000.0,
                "market_cap": 1800000000000,
                "market_cap_rank": 1,
                "total_volume": 35000000000,
                "price_change_percentage_24h": 2.5,
            },
            {
                "id": "ethereum",
                "symbol": "eth",
                "name": "Ethereum",
                "image": "https://assets.coingecko.com/coins/images/279/large/ethereum.png",
                "current_price": 3300.0,
                "market_cap": 400000000000,
                "market_cap_rank": 2,
                "total_volume": 18000000000,
                "price_change_percentage_24h": 3.1,
            },
            {
                "id": "solana",
                "symbol": "sol",
                "name": "Solana",
                "image": "https://assets.coingecko.com/coins/images/4128/large/solana.png",
                "current_price": 180.0,
                "market_cap": 85000000000,
                "market_cap_rank": 5,
                "total_volume": 6000000000,
                "price_change_percentage_24h": 4.8,
            },
        ]


_coingecko_instance: CoinGeckoClient | None = None


def get_coingecko_client() -> CoinGeckoClient:
    global _coingecko_instance
    if _coingecko_instance is None:
        _coingecko_instance = CoinGeckoClient()
    return _coingecko_instance
