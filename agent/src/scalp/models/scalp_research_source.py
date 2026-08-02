"""Research source models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ResearchSource(BaseModel):
    title: str
    publisher: str
    url: str
    publication_time: str = ""
    event_time: str = ""
    summary: str
    credibility_score: float = Field(default=80.0, ge=0.0, le=100.0)
    relevance_score: float = Field(default=80.0, ge=0.0, le=100.0)
    freshness_score: float = Field(default=80.0, ge=0.0, le=100.0)
    confirmed_status: bool = True
