"""Repository ingestion endpoints (async background clone/pull + SSE topic)."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Response, status

from app.api.deps import ContainerDep
from app.core.errors import NotFoundError, RepositoryIngestError
from app.core.logging import get_logger
from app.db import dao
from app.schemas.repository import (
    IngestAccepted,
    RepositoryDetail,
    RepositoryIngestRequest,
    RepositorySummary,
)
from app.services.git_ingestion import IngestionFailure, parse_repo_name

router = APIRouter(prefix="/repositories", tags=["repositories"])
logger = get_logger("nexus.repositories")

_running_ingestions: set[str] = set()


@router.post(
    "/ingest",
    response_model=IngestAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def ingest_repository(
    payload: RepositoryIngestRequest, container: ContainerDep
) -> IngestAccepted:
    """Queue an asynchronous clone/pull + enrichment for a repository."""
    url = str(payload.url)
    if url in _running_ingestions:
        raise RepositoryIngestError("This repository is currently being ingested.")

    record = await dao.create_repository(
        container.session_factory, url=url, name=parse_repo_name(url), depth=payload.depth
    )
    _running_ingestions.add(url)
    task = asyncio.create_task(
        _run_ingestion(container, record.id, url, payload.branch, payload.depth)
    )
    task.add_done_callback(lambda _: _running_ingestions.discard(url))
    return IngestAccepted(
        id=record.id,
        status=record.status,
        message="Ingestion queued. Poll GET /api/repositories/{id} or stream /api/repositories/{id}/events.",
    )


@router.get("", response_model=list[RepositorySummary])
async def list_repositories(container: ContainerDep) -> list[RepositorySummary]:
    """List ingested repositories (newest first)."""
    records = await dao.list_repositories(container.session_factory)
    return [RepositorySummary.model_validate(record) for record in records]


@router.get("/{repository_id}", response_model=RepositoryDetail)
async def get_repository(repository_id: str, container: ContainerDep) -> RepositoryDetail:
    """Fetch one repository with its dependency graph."""
    record = await dao.get_repository(container.session_factory, repository_id)
    if record is None:
        raise NotFoundError(f"Repository {repository_id} not found.")
    detail = RepositoryDetail.model_validate(record)
    return detail


@router.delete("/{repository_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_repository(repository_id: str, container: ContainerDep) -> Response:
    """Delete a repository record (clone data stays on disk for reuse)."""
    record = await dao.get_repository(container.session_factory, repository_id)
    if record is None:
        raise NotFoundError(f"Repository {repository_id} not found.")
    await dao.delete_repository(container.session_factory, repository_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{repository_id}/events")
async def stream_repository_events(repository_id: str, container: ContainerDep):
    """SSE stream of ingestion progress for one repository."""
    record = await dao.get_repository(container.session_factory, repository_id)
    if record is None:
        raise NotFoundError(f"Repository {repository_id} not found.")
    return await stream_topic(container, f"repo:{repository_id}", terminal_check=_repo_done(container, repository_id))


def _repo_done(container, repository_id: str):
    """Terminal predicate: stop the repo SSE stream once ingestion settles."""

    async def check() -> bool:
        record = await dao.get_repository(container.session_factory, repository_id)
        return record is None or record.status in ("ready", "failed")

    return check


async def _run_ingestion(
    container,
    repository_id: str,
    url: str,
    branch: str | None,
    depth: int,
) -> None:
    """Background ingestion task: clone → scan → parse → persist → publish."""
    topic = f"repo:{repository_id}"

    async def publish(type_: str, status: str, data: dict[str, object]) -> None:
        await container.bus.publish(
            topic, type_, {"repository_id": repository_id, "status": status, **data}
        )

    try:
        await dao.mark_repository(container.session_factory, repository_id, status="cloning")
        await publish("repo.update", "cloning", {"message": "Starting clone/pull"})

        def on_status(stage: str, detail: str) -> None:
            # Sync callback from the threadpool — surface via log only.
            logger.info("Ingestion stage", extra={"repo": url, "stage": stage, "detail": detail})

        snapshot = await container.git_service.ingest(
            url, branch=branch, depth=depth, on_status=on_status
        )
        await dao.mark_repository(
            container.session_factory, repository_id, status="parsing"
        )
        record = await dao.save_snapshot(container.session_factory, repository_id, snapshot)
        await publish(
            "repo.completed",
            "ready",
            {
                "file_count": record.file_count,
                "total_loc": record.total_loc,
                "languages": record.languages,
                "secret_findings": len(record.secret_findings or []),
                "head_commit": record.head_commit,
            },
        )
    except IngestionFailure as exc:
        await dao.mark_repository(
            container.session_factory, repository_id, status="failed", error=exc.reason
        )
        await publish("repo.failed", "failed", {"error": exc.reason})
    except Exception as exc:  # noqa: BLE001 - background task backstop
        logger.exception("Ingestion crashed")
        reason = f"Unexpected ingestion failure: {exc}"
        await dao.mark_repository(
            container.session_factory, repository_id, status="failed", error=reason
        )
        await publish("repo.failed", "failed", {"error": reason})


# Imported late to avoid a circular import with the SSE helper.
from app.api.routes.sse import stream_topic  # noqa: E402
