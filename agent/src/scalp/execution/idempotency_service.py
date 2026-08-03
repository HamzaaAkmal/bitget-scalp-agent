"""Idempotency service to prevent duplicate order executions and redundant close requests."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from src.scalp.services.duckdb_store import get_duckdb_store

logger = logging.getLogger(__name__)


class IdempotencyService:
    def __init__(self) -> None:
        self.store = get_duckdb_store()
        self._memory_keys: Dict[str, Dict[str, Any]] = {}

    def get_idempotent_response(self, key: str) -> Optional[Dict[str, Any]]:
        if key in self._memory_keys:
            return self._memory_keys[key]
        cached = self.store.get_idempotency(key)
        if cached:
            self._memory_keys[key] = cached
            return cached
        return None

    def record_idempotent_response(self, key: str, req_type: str, response: Dict[str, Any]) -> Dict[str, Any]:
        now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self._memory_keys[key] = response
        self.store.save_idempotency(key, req_type, response, now_str)
        return response


_idempotency_service_instance: IdempotencyService | None = None


def get_idempotency_service() -> IdempotencyService:
    global _idempotency_service_instance
    if _idempotency_service_instance is None:
        _idempotency_service_instance = IdempotencyService()
    return _idempotency_service_instance
