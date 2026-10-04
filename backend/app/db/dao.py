"""Data-access helpers: all SQL lives here, services stay persistence-agnostic."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from sqlalchemy import delete, desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.db.models import (
    Base,
    ProviderKeyRecord,
    RepositoryRecord,
    SwarmEventRecord,
    SwarmJobRecord,
    UsageRecord,
)
from app.services.git_ingestion import RepositorySnapshot
from app.services.vault import SealedSecret


async def create_all(engine: AsyncEngine) -> None:
    """Create every table (idempotent)."""
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


# ── Repositories ────────────────────────────────────────────────────────────
async def create_repository(
    session_factory: async_sessionmaker[AsyncSession], url: str, name: str, depth: int
) -> RepositoryRecord:
    async with session_factory() as session:
        record = RepositoryRecord(url=url, name=name, depth=depth, status="queued")
        session.add(record)
        await session.commit()
        await session.refresh(record)
        return record


async def save_snapshot(
    session_factory: async_sessionmaker[AsyncSession], record_id: str, snapshot: RepositorySnapshot
) -> RepositoryRecord:
    values = {
        "status": "ready",
        "branch": snapshot.branch,
        "default_branch": snapshot.default_branch,
        "head_commit": snapshot.head_commit,
        "clone_path": snapshot.clone_path,
        "file_count": snapshot.file_count,
        "total_loc": snapshot.total_loc,
        "languages": snapshot.languages,
        "secret_findings": [f.to_dict() for f in snapshot.secret_findings],
        "dep_graph": snapshot.dep_graph,
        "error": None,
        "updated_at": datetime.now(timezone.utc),
    }
    async with session_factory() as session:
        await session.execute(
            update(RepositoryRecord).where(RepositoryRecord.id == record_id).values(**values)
        )
        await session.commit()
        result = await session.execute(
            select(RepositoryRecord).where(RepositoryRecord.id == record_id)
        )
        return result.scalar_one()


async def mark_repository(
    session_factory: async_sessionmaker[AsyncSession],
    record_id: str,
    *,
    status: str,
    error: str | None = None,
) -> None:
    async with session_factory() as session:
        await session.execute(
            update(RepositoryRecord)
            .where(RepositoryRecord.id == record_id)
            .values(status=status, error=error, updated_at=datetime.now(timezone.utc))
        )
        await session.commit()


async def get_repository(
    session_factory: async_sessionmaker[AsyncSession], record_id: str
) -> RepositoryRecord | None:
    async with session_factory() as session:
        result = await session.execute(
            select(RepositoryRecord).where(RepositoryRecord.id == record_id)
        )
        return result.scalar_one_or_none()


async def list_repositories(
    session_factory: async_sessionmaker[AsyncSession], limit: int = 100
) -> Sequence[RepositoryRecord]:
    async with session_factory() as session:
        result = await session.execute(
            select(RepositoryRecord).order_by(desc(RepositoryRecord.updated_at)).limit(limit)
        )
        return result.scalars().all()


async def delete_repository(session_factory: async_sessionmaker[AsyncSession], record_id: str) -> None:
    async with session_factory() as session:
        await session.execute(delete(RepositoryRecord).where(RepositoryRecord.id == record_id))
        await session.commit()


# ── Provider keys ───────────────────────────────────────────────────────────
async def create_provider_key(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    provider_id: str,
    label: str,
    sealed: SealedSecret,
    fingerprint: str,
) -> ProviderKeyRecord:
    async with session_factory() as session:
        # One active key per provider: supersede previous ones.
        await session.execute(
            delete(ProviderKeyRecord).where(
                ProviderKeyRecord.provider_id == provider_id,
                ProviderKeyRecord.status == "active",
            )
        )
        record = ProviderKeyRecord(
            provider_id=provider_id,
            label=label,
            ciphertext=sealed.ciphertext,
            nonce=sealed.nonce,
            salt=sealed.salt,
            kdf_algorithm=sealed.kdf_algorithm,
            kdf_iterations=sealed.kdf_iterations,
            fingerprint=fingerprint,
        )
        session.add(record)
        await session.commit()
        await session.refresh(record)
        return record


async def list_provider_keys(
    session_factory: async_sessionmaker[AsyncSession],
) -> Sequence[ProviderKeyRecord]:
    async with session_factory() as session:
        result = await session.execute(
            select(ProviderKeyRecord).order_by(desc(ProviderKeyRecord.created_at))
        )
        return result.scalars().all()


async def get_provider_key(
    session_factory: async_sessionmaker[AsyncSession], record_id: str
) -> ProviderKeyRecord | None:
    async with session_factory() as session:
        result = await session.execute(
            select(ProviderKeyRecord).where(ProviderKeyRecord.id == record_id)
        )
        return result.scalar_one_or_none()


async def update_provider_key_status(
    session_factory: async_sessionmaker[AsyncSession], record_id: str, status: str
) -> None:
    async with session_factory() as session:
        await session.execute(
            update(ProviderKeyRecord)
            .where(ProviderKeyRecord.id == record_id)
            .values(
                status=status,
                last_verified_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()


async def replace_sealed_material(
    session_factory: async_sessionmaker[AsyncSession],
    record_id: str,
    sealed: SealedSecret,
    *,
    fingerprint: str | None = None,
) -> None:
    """Overwrite the sealed ciphertext of a key record (rotation / re-seal)."""
    values: dict[str, Any] = {
        "ciphertext": sealed.ciphertext,
        "nonce": sealed.nonce,
        "salt": sealed.salt,
        "kdf_algorithm": sealed.kdf_algorithm,
        "kdf_iterations": sealed.kdf_iterations,
        "status": "active",
        "updated_at": datetime.now(timezone.utc),
    }
    if fingerprint is not None:
        values["fingerprint"] = fingerprint
    async with session_factory() as session:
        await session.execute(
            update(ProviderKeyRecord).where(ProviderKeyRecord.id == record_id).values(**values)
        )
        await session.commit()


async def delete_provider_key(
    session_factory: async_sessionmaker[AsyncSession], record_id: str
) -> None:
    async with session_factory() as session:
        await session.execute(delete(ProviderKeyRecord).where(ProviderKeyRecord.id == record_id))
        await session.commit()


# ── Swarm jobs ──────────────────────────────────────────────────────────────
async def create_swarm_job(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    repository_id: str,
    task: str,
    config: dict[str, Any],
    max_repair_iterations: int,
) -> SwarmJobRecord:
    async with session_factory() as session:
        record = SwarmJobRecord(
            repository_id=repository_id,
            task=task,
            status="queued",
            config=config,
            max_repair_iterations=max_repair_iterations,
        )
        session.add(record)
        await session.commit()
        await session.refresh(record)
        return record


async def update_swarm_job(
    session_factory: async_sessionmaker[AsyncSession], job_id: str, **values: Any
) -> None:
    if not values:
        return
    async with session_factory() as session:
        await session.execute(
            update(SwarmJobRecord).where(SwarmJobRecord.id == job_id).values(**values)
        )
        await session.commit()


async def get_swarm_job(
    session_factory: async_sessionmaker[AsyncSession], job_id: str
) -> SwarmJobRecord | None:
    async with session_factory() as session:
        result = await session.execute(select(SwarmJobRecord).where(SwarmJobRecord.id == job_id))
        return result.scalar_one_or_none()


async def list_swarm_jobs(
    session_factory: async_sessionmaker[AsyncSession], limit: int = 50
) -> Sequence[SwarmJobRecord]:
    async with session_factory() as session:
        result = await session.execute(
            select(SwarmJobRecord).order_by(desc(SwarmJobRecord.created_at)).limit(limit)
        )
        return result.scalars().all()


async def add_swarm_event(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    job_id: str,
    type_: str,
    agent: str | None,
    data: dict[str, Any],
) -> None:
    async with session_factory() as session:
        session.add(
            SwarmEventRecord(job_id=job_id, type=type_, agent=agent, data=data)
        )
        await session.commit()


async def list_swarm_events(
    session_factory: async_sessionmaker[AsyncSession],
    job_id: str,
    *,
    after_id: int = 0,
    limit: int = 1000,
) -> Sequence[SwarmEventRecord]:
    async with session_factory() as session:
        statement = (
            select(SwarmEventRecord)
            .where(SwarmEventRecord.job_id == job_id, SwarmEventRecord.id > after_id)
            .order_by(SwarmEventRecord.id)
            .limit(limit)
        )
        result = await session.execute(statement)
        return result.scalars().all()


# ── Usage telemetry ─────────────────────────────────────────────────────────
async def record_usage(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    job_id: str | None,
    provider_id: str,
    model: str,
    purpose: str,
    prompt_tokens: int,
    completion_tokens: int,
    latency_ms: float,
    ok: bool,
    error_code: str | None,
) -> None:
    async with session_factory() as session:
        session.add(
            UsageRecord(
                job_id=job_id,
                provider_id=provider_id,
                model=model,
                purpose=purpose,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=latency_ms,
                ok=ok,
                error_code=error_code,
            )
        )
        await session.commit()


async def usage_summary(
    session_factory: async_sessionmaker[AsyncSession], limit: int = 5000
) -> dict[str, Any]:
    async with session_factory() as session:
        rows = (
            await session.execute(
                select(
                    UsageRecord.provider_id,
                    UsageRecord.ok,
                    UsageRecord.prompt_tokens,
                    UsageRecord.completion_tokens,
                    UsageRecord.latency_ms,
                )
                .order_by(desc(UsageRecord.id))
                .limit(limit)
            )
        ).all()
    total = len(rows)
    if total == 0:
        return {
            "total_requests": 0,
            "ok_requests": 0,
            "failed_requests": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "avg_latency_ms": 0.0,
            "by_provider": {},
        }
    ok_rows = [r for r in rows if r.ok]
    by_provider: dict[str, dict[str, float]] = {}
    for row in rows:
        bucket = by_provider.setdefault(
            row.provider_id,
            {"requests": 0, "ok": 0, "prompt_tokens": 0, "completion_tokens": 0, "avg_latency_ms": 0.0},
        )
        bucket["requests"] = bucket["requests"] + 1
        bucket["ok"] = bucket["ok"] + (1 if row.ok else 0)
        bucket["prompt_tokens"] = bucket["prompt_tokens"] + row.prompt_tokens
        bucket["completion_tokens"] = bucket["completion_tokens"] + row.completion_tokens
        bucket["avg_latency_ms"] = (
            (bucket["avg_latency_ms"] * (bucket["requests"] - 1) + row.latency_ms)
            / bucket["requests"]
        )
    return {
        "total_requests": total,
        "ok_requests": len(ok_rows),
        "failed_requests": total - len(ok_rows),
        "prompt_tokens": sum(r.prompt_tokens for r in rows),
        "completion_tokens": sum(r.completion_tokens for r in rows),
        "avg_latency_ms": round(sum(r.latency_ms for r in rows) / total, 1),
        "by_provider": by_provider,
    }


async def count_jobs(session_factory: async_sessionmaker[AsyncSession]) -> dict[str, int]:
    async with session_factory() as session:
        total = (await session.execute(select(func.count(SwarmJobRecord.id)))).scalar_one()
        completed = (
            await session.execute(
                select(func.count(SwarmJobRecord.id)).where(SwarmJobRecord.status == "completed")
            )
        ).scalar_one()
        running = (
            await session.execute(
                select(func.count(SwarmJobRecord.id)).where(SwarmJobRecord.status.notin_(("completed", "failed", "cancelled")))
            )
        ).scalar_one()
        repos = (await session.execute(select(func.count(RepositoryRecord.id)))).scalar_one()
    return {
        "jobs": int(total),
        "completed_jobs": int(completed),
        "active_jobs": int(running),
        "repositories": int(repos),
    }


def workdir_for(record: RepositoryRecord) -> Path:
    """Repository working directory (clone path)."""
    return Path(record.clone_path) if record.clone_path else Path()
