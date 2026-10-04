"""Nexus AI Swarm Platform — FastAPI application factory.

Lifespan responsibilities
-------------------------
1. Configure structured logging.
2. Create the async database engine + tables.
3. Initialize the AES-256-GCM key vault (auto-unlock when a master key is set).
4. Load the provider catalog and bind sealed keys from the database.
5. Wire the event bus, provider router, git ingestion service and orchestrator.
6. Serve the built frontend from ``frontend/dist`` when present (single-container mode).
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api.deps import Container, make_usage_sink
from app.api.routes import health, providers, repositories, swarm, vault
from app.core.config import Settings, get_settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging, get_logger
from app.db import dao
from app.db.session import (
    create_engine,
    create_session_factory,
    resolve_clone_root,
)
from app.services.event_bus import EventBus
from app.services.git_ingestion import GitIngestionService
from app.services.llm_client import OpenAICompatibleClient
from app.services.provider_router import ProviderRouter
from app.services.vault import KeyVault, SealedSecret
from app.swarm.orchestrator import SwarmOrchestrator

logger = get_logger("nexus.main")


async def _bind_sealed_keys(container: Container) -> None:
    """Load persisted provider keys and attach them to the router."""
    if not container.vault.is_unlocked:
        logger.info("Vault locked at startup; provider keys load on unlock.")
        return
    records = await dao.list_provider_keys(container.session_factory)
    bound = 0
    for record in records:
        if record.status != "active":
            continue
        definition = container.router.definitions.get(record.provider_id)
        if definition is None:
            continue
        sealed = SealedSecret(
            ciphertext=record.ciphertext,
            nonce=record.nonce,
            salt=record.salt,
            kdf_algorithm=record.kdf_algorithm,
            kdf_iterations=record.kdf_iterations,
        )
        try:
            container.vault.open(sealed, aad=f"{definition.provider_id}:{record.id}")
        except Exception:  # noqa: BLE001 - stale record under a new passphrase
            logger.warning(
                "Skipping unverifiable key record",
                extra={"record_id": record.id, "provider": record.provider_id},
            )
            continue
        await container.router.attach_key(
            provider_id=record.provider_id,
            record_id=record.id,
            sealed=sealed,
            fingerprint=record.fingerprint,
            status=record.status,
            label=record.label,
        )
        bound += 1
    logger.info("Provider keys bound", extra={"count": bound})


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application startup/shutdown lifecycle."""
    settings: Settings = get_settings()
    configure_logging(debug=settings.debug)

    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    await dao.create_all(engine)

    vault = KeyVault(settings)
    if settings.vault_master_key and settings.vault_auto_unlock:
        try:
            vault.unlock(settings.vault_master_key)
            logger.info("Key vault auto-unlocked from environment master key.")
        except Exception as exc:  # noqa: BLE001 - startup resilience
            logger.warning("Vault auto-unlock failed", extra={"error": str(exc)})
    else:
        logger.info(
            "Key vault starts LOCKED (no NEXUS_VAULT_MASTER_KEY / auto-unlock disabled)."
        )

    bus = EventBus(max_queue=settings.event_bus_max_queue)
    llm_client = OpenAICompatibleClient(
        timeout=settings.provider_timeout_seconds,
        stream_timeout=settings.provider_stream_timeout_seconds,
    )
    router = ProviderRouter(
        settings=settings,
        vault=vault,
        client=llm_client,
        usage_sink=make_usage_sink(session_factory),
    )
    router.load_catalog()
    logger.info(
        "Provider catalog loaded",
        extra={"providers": sorted(router.definitions.keys())},
    )

    git_service = GitIngestionService(
        clone_root=resolve_clone_root(settings.clone_root),
        max_repo_size_mb=settings.max_repo_size_mb,
    )
    orchestrator = SwarmOrchestrator(
        settings=settings,
        session_factory=session_factory,
        bus=bus,
        router=router,
    )

    container = Container(
        settings=settings,
        engine=engine,
        session_factory=session_factory,
        vault=vault,
        bus=bus,
        llm_client=llm_client,
        router=router,
        git_service=git_service,
        orchestrator=orchestrator,
    )
    app.state.container = container

    await _bind_sealed_keys(container)

    yield

    container._closing = True  # noqa: SLF001
    await llm_client.aclose()
    await engine.dispose()
    logging.getLogger("nexus.main").info("Shutdown complete.")


def create_app() -> FastAPI:
    """Build the fully-configured FastAPI application."""
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description=(
            "Enterprise platform: GitHub ingestion, AES-256-GCM key vault, "
            "adaptive multi-provider AI routing (NVIDIA Nemotron, Qwen, OpenAI, "
            "Anthropic, Gemini) and self-healing multi-agent developer swarms."
        ),
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_error_handlers(app)

    prefix = settings.api_prefix
    app.include_router(health.router, prefix=prefix)
    app.include_router(repositories.router, prefix=prefix)
    app.include_router(vault.router, prefix=prefix)
    app.include_router(providers.router, prefix=prefix)
    app.include_router(swarm.router, prefix=prefix)

    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        return {
            "service": settings.app_name,
            "version": __version__,
            "docs": f"{prefix}/docs",
        }

    # Single-container production mode: serve the built SPA if it was shipped.
    frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if frontend_dist.is_dir():
        app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="spa")
        logger.info("Serving built frontend from frontend/dist")

    return app


app = create_app()
