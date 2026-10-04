"""Application container + FastAPI dependency providers.

The container is built once during the lifespan startup and stashed on
``app.state.container``; route handlers resolve it through these providers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Annotated

from fastapi import Depends, Request

from app.core.config import Settings
from app.db.dao import record_usage
from app.db.session import AsyncEngine, async_sessionmaker
from app.services.event_bus import EventBus
from app.services.git_ingestion import GitIngestionService
from app.services.llm_client import OpenAICompatibleClient
from app.services.provider_router import ProviderRouter
from app.services.vault import KeyVault
from app.swarm.orchestrator import SwarmOrchestrator


@dataclass
class Container:
    """Wires every long-lived service together."""

    settings: Settings
    engine: AsyncEngine
    session_factory: async_sessionmaker
    vault: KeyVault
    bus: EventBus
    llm_client: OpenAICompatibleClient
    router: ProviderRouter
    git_service: GitIngestionService
    orchestrator: SwarmOrchestrator
    _closing: bool = field(default=False, repr=False)

    @property
    def closing(self) -> bool:
        return self._closing


def get_container(request: Request) -> Container:
    """FastAPI dependency: resolve the application container."""
    container: Container | None = getattr(request.app.state, "container", None)
    if container is None:  # pragma: no cover - only during misconfigured startup
        raise RuntimeError("Application container is not initialized.")
    return container


def get_settings_dep(container: Annotated[Container, Depends(get_container)]) -> Settings:
    """FastAPI dependency: settings."""
    return container.settings


ContainerDep = Annotated[Container, Depends(get_container)]
SettingsDep = Annotated[Settings, Depends(get_settings_dep)]


def make_usage_sink(session_factory: async_sessionmaker):
    """Async callback persisting router telemetry into the usage table."""

    async def _sink(
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
        await record_usage(
            session_factory,
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

    return _sink
