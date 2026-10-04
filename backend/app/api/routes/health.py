"""Health & readiness endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from app import __version__
from app.api.deps import ContainerDep
from app.db import dao

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok", "service": "nexus-backend", "version": __version__}


@router.get("/ready")
async def ready(container: ContainerDep) -> dict[str, object]:
    """Readiness probe: DB reachable, catalog loaded, vault state reported."""
    from sqlalchemy import text

    database_ok = True
    try:
        async with container.session_factory() as session:
            await session.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001 - readiness must not raise
        database_ok = False

    return {
        "status": "ready" if database_ok else "degraded",
        "database": "ok" if database_ok else "unreachable",
        "providers_registered": len(container.router.definitions),
        "vault": "unlocked" if container.vault.is_unlocked else "locked",
        "environment": container.settings.environment,
    }


@router.get("/stats")
async def stats(container: ContainerDep) -> dict[str, int]:
    """Aggregate platform counters for the dashboard."""
    return await dao.count_jobs(container.session_factory)
