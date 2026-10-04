"""Schemas for the GitHub Ingestion Engine."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

RepoStatus = Literal["queued", "cloning", "scanning", "parsing", "ready", "failed"]


class RepositoryIngestRequest(BaseModel):
    """Request payload for cloning / updating a repository."""

    url: HttpUrl
    branch: str | None = Field(default=None, description="Optional branch override.")
    depth: int = Field(default=1, ge=1, le=100, description="Shallow clone depth.")

    @field_validator("url")
    @classmethod
    def _validate_git_url(cls, value: HttpUrl) -> HttpUrl:
        if value.host is None:
            raise ValueError("Repository URL must include a host.")
        return value


class SecretFinding(BaseModel):
    """A single secret-scanner detection (always redacted)."""

    rule_id: str
    severity: Literal["critical", "high", "medium", "low"]
    file: str
    line: int
    preview: str


class DependencyNode(BaseModel):
    """A file node inside the AST dependency graph."""

    id: str
    path: str
    language: str
    loc: int
    imports: list[str] = Field(default_factory=list)
    symbols: list[str] = Field(default_factory=list)


class DependencyEdge(BaseModel):
    """A directed import edge between two files."""

    source: str
    target: str
    symbol: str | None = None


class DependencyGraph(BaseModel):
    """The repository-wide import graph produced by the AST parser."""

    nodes: list[DependencyNode] = Field(default_factory=list)
    edges: list[DependencyEdge] = Field(default_factory=list)
    external_packages: list[str] = Field(default_factory=list)


class RepositorySummary(BaseModel):
    """Repository record without heavyweight graph payloads."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    url: str
    name: str
    branch: str | None
    default_branch: str | None
    head_commit: str | None
    status: RepoStatus
    depth: int
    file_count: int
    total_loc: int
    languages: dict[str, int]
    secret_findings: list[dict[str, Any]]
    error: str | None
    created_at: datetime
    updated_at: datetime


class RepositoryDetail(RepositorySummary):
    """Full repository record including the dependency graph."""

    dep_graph: DependencyGraph | None = None


class IngestAccepted(BaseModel):
    """202 Accepted response for an asynchronous ingestion request."""

    id: str
    status: RepoStatus
    message: str
