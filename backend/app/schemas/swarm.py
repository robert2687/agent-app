"""Schemas for the Multi-Agent Orchestration Swarm."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

JobStatus = Literal[
    "queued",
    "running",
    "planning",
    "architecting",
    "coding",
    "reviewing",
    "validating",
    "patching",
    "completed",
    "failed",
    "cancelled",
]

AgentRole = Literal["planner", "architect", "coder", "reviewer", "patcher", "validator"]


class SwarmLaunchRequest(BaseModel):
    """Launch a multi-agent swarm job against an ingested repository."""

    repository_id: str = Field(min_length=1)
    task: str = Field(min_length=16, max_length=8000)
    preferred_model: str | None = Field(
        default=None, description="Model hint, e.g. qwen-max or nvidia/nemotron-4-340b-instruct."
    )
    preferred_provider_id: str | None = Field(default=None)
    max_repair_iterations: int = Field(default=3, ge=0, le=10)
    validation_enabled: bool = Field(
        default=True, description="Run lint + tests and trigger the self-healing loop."
    )

    @field_validator("task")
    @classmethod
    def _task_not_trivial(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Task must not be empty.")
        return value.strip()


class SwarmJobSummary(BaseModel):
    """Job record without the event log."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    repository_id: str
    task: str
    status: JobStatus
    current_agent: str | None
    repair_iteration: int
    max_repair_iterations: int
    config: dict[str, Any]
    token_usage: dict[str, int]
    error: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class SwarmJobDetail(SwarmJobSummary):
    """Full job record including agent artifacts and the final diff."""

    plan: dict[str, Any] | None
    architecture: dict[str, Any] | None
    review: dict[str, Any] | None
    validation: dict[str, Any] | None
    edits: list[dict[str, Any]]
    diff: str | None
    repository_name: str | None = None


class SwarmEventOut(BaseModel):
    """A single streamed swarm event."""

    id: int | None = None
    type: str
    agent: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None


class DiffFile(BaseModel):
    """One parsed file of a unified diff, for side-by-side rendering."""

    path: str
    additions: int
    deletions: int
    is_binary: bool = False
    is_new: bool = False
    is_deleted: bool = False
    hunks: list[dict[str, Any]] = Field(default_factory=list)


class DiffSummary(BaseModel):
    """Structured diff payload for the frontend viewer."""

    job_id: str
    files: list[DiffFile] = Field(default_factory=list)
    additions: int = 0
    deletions: int = 0
    raw: str = ""
