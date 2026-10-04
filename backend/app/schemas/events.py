"""Schemas for realtime events (SSE / WebSocket envelopes)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

RepositoryEventType = Literal[
    "repo.update", "repo.completed", "repo.failed", "repo.error"
]


class RepositoryEvent(BaseModel):
    """Event published on the ``repo:{id}`` topic during ingestion."""

    type: RepositoryEventType
    repository_id: str
    status: str
    data: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None


class SwarmStreamEvent(BaseModel):
    """Event published on the ``job:{id}`` topic during swarm execution."""

    type: str
    job_id: str
    agent: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    seq: int | None = None
    created_at: datetime | None = None
