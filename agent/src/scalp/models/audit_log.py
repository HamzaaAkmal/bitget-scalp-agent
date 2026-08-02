"""Audit logging model."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class AuditRecord(BaseModel):
    audit_id: str
    session_id: str
    timestamp: str
    action_type: str  # POLICY_PARSE, SESSION_START, ORDER_PLACE, ORDER_VERIFY, POSITION_CLOSE, EMERGENCY_STOP, RISK_VETO
    actor: str        # USER, RISK_ENGINE, AGENT, SYSTEM
    request_data: dict[str, Any] = Field(default_factory=dict)
    response_data: dict[str, Any] = Field(default_factory=dict)
    verification_status: str = "VERIFIED"
    error_message: str | None = None
