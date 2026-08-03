"""Background NewsRiskCache for non-blocking news and event risk management out of the trade hot path."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from src.scalp.services.duckdb_store import get_duckdb_store

logger = logging.getLogger(__name__)


class NewsRiskCache:
    def __init__(self, default_ttl_seconds: int = 300) -> None:
        self.default_ttl = default_ttl_seconds
        self._memory_cache: Dict[str, Dict[str, Any]] = {}
        self.store = get_duckdb_store()

    def get_news_risk(self, symbol: str, policy_mode: str = "guarded") -> Dict[str, Any]:
        """Instant non-blocking lookup for news risk and veto status."""
        now_ts = time.time()
        
        # 1. Check memory cache
        cached = self._memory_cache.get(symbol)
        if not cached:
            # 2. Check DB store
            cached = self.store.get_news_risk(symbol)
            if cached:
                self._memory_cache[symbol] = cached

        if cached:
            exp_str = cached.get("expires_at", "")
            try:
                import calendar
                exp_ts = calendar.timegm(time.strptime(exp_str, "%Y-%m-%dT%H:%M:%SZ")) if exp_str else 0
                is_stale = now_ts > exp_ts
            except Exception:
                is_stale = False

            if not is_stale:
                return cached
            else:
                logger.info(f"News risk cache stale for {symbol}.")
                if policy_mode == "guarded":
                    return {
                        "symbol": symbol,
                        "veto_active": True,
                        "risk_status": "STALE_CACHE_REJECT",
                        "reasons": ["News risk cache is stale in guarded mode."],
                        "confidence": 0.0,
                        "sources": [],
                        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "expires_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now_ts + self.default_ttl)),
                    }

        # Safe default if no cache exists
        return {
            "symbol": symbol,
            "veto_active": False,
            "risk_status": "CLEAR",
            "reasons": ["No critical news risk detected."],
            "confidence": 1.0,
            "sources": [],
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "expires_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now_ts + self.default_ttl)),
        }

    def update_news_risk(
        self,
        symbol: str,
        veto_active: bool,
        risk_status: str,
        reasons: List[str],
        confidence: float,
        sources: List[str],
        ttl_seconds: int | None = None,
    ) -> Dict[str, Any]:
        ttl = ttl_seconds or self.default_ttl
        now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        exp_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + ttl))

        record = {
            "symbol": symbol,
            "veto_active": veto_active,
            "risk_status": risk_status,
            "reasons": reasons,
            "confidence": confidence,
            "sources": sources,
            "created_at": now_str,
            "expires_at": exp_str,
        }

        self._memory_cache[symbol] = record
        self.store.save_news_risk(
            symbol=symbol,
            veto_active=veto_active,
            risk_status=risk_status,
            reasons=reasons,
            confidence=confidence,
            sources=sources,
            created_at=now_str,
            expires_at=exp_str,
        )
        return record


_news_risk_cache_instance: NewsRiskCache | None = None


def get_news_risk_cache() -> NewsRiskCache:
    global _news_risk_cache_instance
    if _news_risk_cache_instance is None:
        _news_risk_cache_instance = NewsRiskCache()
    return _news_risk_cache_instance
