"""SQLAlchemy 2.0 ORM models (typed, async-friendly)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    """Declarative base for all models."""


class RepositoryRecord(Base):
    """A GitHub repository ingested by the GitHub Ingestion Engine."""

    __tablename__ = "repositories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    branch: Mapped[str | None] = mapped_column(String(512), nullable=True)
    default_branch: Mapped[str | None] = mapped_column(String(512), nullable=True)
    head_commit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), default="queued", nullable=False, index=True
    )
    clone_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    depth: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    file_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_loc: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    languages: Mapped[dict[str, int]] = mapped_column(JSON, default=dict)
    secret_findings: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    dep_graph: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    jobs: Mapped[list["SwarmJobRecord"]] = relationship(
        back_populates="repository", cascade="all, delete-orphan"
    )


class ProviderKeyRecord(Base):
    """An AES-256-GCM sealed provider API key inside the Key Vault."""

    __tablename__ = "provider_keys"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    provider_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    ciphertext: Mapped[bytes] = mapped_column(nullable=False)
    nonce: Mapped[bytes] = mapped_column(nullable=False)
    salt: Mapped[bytes] = mapped_column(nullable=False)
    kdf_algorithm: Mapped[str] = mapped_column(String(16), default="pbkdf2")
    kdf_iterations: Mapped[int] = mapped_column(Integer, default=100_000)
    fingerprint: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="active", nullable=False)
    last_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class SwarmJobRecord(Base):
    """A multi-agent swarm execution job with its self-healing loop state."""

    __tablename__ = "swarm_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    repository_id: Mapped[str] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    current_agent: Mapped[str | None] = mapped_column(String(32), nullable=True)
    repair_iteration: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_repair_iterations: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    config: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    plan: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    architecture: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    review: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    validation: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    edits: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    token_usage: Mapped[dict[str, int]] = mapped_column(
        JSON, default=lambda: {"prompt_tokens": 0, "completion_tokens": 0, "requests": 0}
    )
    diff: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    repository: Mapped[RepositoryRecord] = relationship(back_populates="jobs")
    events: Mapped[list["SwarmEventRecord"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )


class SwarmEventRecord(Base):
    """Append-only event log streamed to clients via SSE / WebSocket."""

    __tablename__ = "swarm_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(
        ForeignKey("swarm_jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(48), nullable=False)
    agent: Mapped[str | None] = mapped_column(String(32), nullable=True)
    data: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )

    job: Mapped[SwarmJobRecord] = relationship(back_populates="events")


class UsageRecord(Base):
    """Per-request provider usage telemetry (latency, tokens, spend)."""

    __tablename__ = "usage_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    provider_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    purpose: Mapped[str] = mapped_column(String(48), default="chat", nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    ok: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )
