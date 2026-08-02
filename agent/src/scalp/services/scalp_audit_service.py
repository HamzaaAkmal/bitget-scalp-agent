"""Audit logging service for tracking all session and exchange operations."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict
from src.scalp.services.duckdb_store import get_duckdb_store

logger = logging.getLogger(__name__)


class ScalpAuditService:
    def __init__(self) -> None:
        self.store = get_duckdb_store()

    def record_audit(self, session_id: str, action_type: str, actor: str, data: Dict[str, Any]) -> None:
        audit_id = f"aud_{int(time.time() * 1000)}"
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        try:
            self.store.save_audit(
                audit_id=audit_id,
                session_id=session_id,
                action_type=action_type,
                actor=actor,
                data=data,
                timestamp=timestamp,
            )
        except Exception as exc:
            logger.warning(f"Audit log failed: {exc}")


_audit_service_instance: ScalpAuditService | None = None


def get_audit_service() -> ScalpAuditService:
    global _audit_service_instance
    if _audit_service_instance is None:
        _audit_service_instance = ScalpAuditService()
    return _audit_service_instance
