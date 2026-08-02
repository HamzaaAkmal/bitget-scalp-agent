"""Agent event and timeline models."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class AgentEvent(BaseModel):
    event_id: str
    session_id: str
    timestamp: str
    agent_name: str  # Market Intelligence Agent, Technical & Strategy Agent, Risk & Critic Agent, Execution & Monitoring Agent
    event_type: str  # SCAN, RESEARCH, STRATEGY, RISK_CHECK, PROPOSAL, EXECUTION, POSITION_UPDATE, EXIT, EVALUATION
    summary: str
    details: dict[str, Any] = Field(default_factory=dict)
    decision: str | None = None
    confidence_score: float | None = None
