"""Swarm job endpoints: launch, inspect, stream (SSE + WebSocket), diff."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, status
from fastapi.responses import StreamingResponse
from fastapi.websockets import WebSocket, WebSocketDisconnect

from app.api.deps import ContainerDep
from app.api.routes.sse import stream_topic
from app.core.errors import JobStateError, NotFoundError
from app.db import dao
from app.schemas.swarm import (
    DiffSummary,
    SwarmEventOut,
    SwarmJobDetail,
    SwarmJobSummary,
    SwarmLaunchRequest,
)
from app.swarm.diff_engine import compute_diff, parse_unified_diff, to_payload
from app.swarm.orchestrator import TERMINAL_STATUSES

router = APIRouter(prefix="/swarm", tags=["swarm"])


@router.post("/jobs", response_model=SwarmJobSummary, status_code=status.HTTP_201_CREATED)
async def launch_job(payload: SwarmLaunchRequest, container: ContainerDep) -> SwarmJobSummary:
    """Launch a multi-agent swarm job against an ingested repository."""
    repo = await dao.get_repository(container.session_factory, payload.repository_id)
    if repo is None:
        raise NotFoundError(f"Repository {payload.repository_id} not found.")
    if repo.status != "ready":
        raise JobStateError(
            f"Repository is still '{repo.status}'; wait for ingestion to finish."
        )
    if not container.router.candidates(
        model=payload.preferred_model, prefer_provider_id=payload.preferred_provider_id
    ):
        raise JobStateError(
            "No provider is currently routable. Register and unlock at least one "
            "provider API key in the vault first."
        )

    config = {
        "preferred_model": payload.preferred_model,
        "preferred_provider_id": payload.preferred_provider_id,
        "validation_enabled": payload.validation_enabled,
        "repository_name": repo.name,
    }
    record = await dao.create_swarm_job(
        container.session_factory,
        repository_id=payload.repository_id,
        task=payload.task,
        config=config,
        max_repair_iterations=payload.max_repair_iterations,
    )
    container.orchestrator.launch(record.id)
    return SwarmJobSummary.model_validate(record)


@router.get("/jobs", response_model=list[SwarmJobSummary])
async def list_jobs(container: ContainerDep) -> list[SwarmJobSummary]:
    """List swarm jobs (newest first)."""
    records = await dao.list_swarm_jobs(container.session_factory)
    return [SwarmJobSummary.model_validate(record) for record in records]


@router.get("/jobs/{job_id}", response_model=SwarmJobDetail)
async def get_job(job_id: str, container: ContainerDep) -> SwarmJobDetail:
    """Fetch one job with all agent artifacts."""
    record = await dao.get_swarm_job(container.session_factory, job_id)
    if record is None:
        raise NotFoundError(f"Job {job_id} not found.")
    detail = SwarmJobDetail.model_validate(record)
    if record.repository is None:
        repo = await dao.get_repository(container.session_factory, record.repository_id)
        detail.repository_name = repo.name if repo else None
    else:
        detail.repository_name = record.repository.name
    return detail


@router.post("/jobs/{job_id}/cancel", response_model=SwarmJobSummary)
async def cancel_job(job_id: str, container: ContainerDep) -> SwarmJobSummary:
    """Request cooperative cancellation at the next stage boundary."""
    await container.orchestrator.cancel(job_id)
    record = await dao.get_swarm_job(container.session_factory, job_id)
    if record is None:  # pragma: no cover - cancel() validated existence
        raise NotFoundError(f"Job {job_id} not found.")
    return SwarmJobSummary.model_validate(record)


@router.get("/jobs/{job_id}/events", response_model=list[SwarmEventOut])
async def list_job_events(
    job_id: str, container: ContainerDep, after_id: int = 0
) -> list[SwarmEventOut]:
    """Persisted (non-token) event log for replay/backfill."""
    if await dao.get_swarm_job(container.session_factory, job_id) is None:
        raise NotFoundError(f"Job {job_id} not found.")
    records = await dao.list_swarm_events(
        container.session_factory, job_id, after_id=after_id
    )
    return [
        SwarmEventOut(
            id=record.id,
            type=record.type,
            agent=record.agent,
            data=record.data or {},
            created_at=record.created_at,
        )
        for record in records
    ]


@router.get("/jobs/{job_id}/stream")
async def stream_job(job_id: str, container: ContainerDep) -> StreamingResponse:
    """Live SSE stream: replayed log + live tokens/status/diff events."""

    async def replay_fetcher(last_id: int) -> list[dict[str, Any]]:
        records = await dao.list_swarm_events(
            container.session_factory, job_id, after_id=last_id
        )
        return [
            {
                "type": record.type,
                "seq": record.id,
                "data": {"agent": record.agent, **(record.data or {})},
            }
            for record in records
        ]

    async def terminal_check() -> bool:
        record = await dao.get_swarm_job(container.session_factory, job_id)
        # Terminal frames (job.completed / job.failed / job.cancelled) arrive
        # through the bus itself and end the stream; nothing to poll for.
        return record is None

    if await dao.get_swarm_job(container.session_factory, job_id) is None:
        raise NotFoundError(f"Job {job_id} not found.")
    return await stream_topic(
        container,
        f"job:{job_id}",
        terminal_check=terminal_check,
        replay_fetcher=replay_fetcher,
    )


@router.get("/jobs/{job_id}/diff", response_model=DiffSummary)
async def get_job_diff(job_id: str, container: ContainerDep, refresh: bool = False) -> DiffSummary:
    """Structured unified diff for the side-by-side viewer."""
    record = await dao.get_swarm_job(container.session_factory, job_id)
    if record is None:
        raise NotFoundError(f"Job {job_id} not found.")
    diff_text = record.diff or ""
    if refresh and record.status in TERMINAL_STATUSES:
        repo = await dao.get_repository(container.session_factory, record.repository_id)
        if repo and repo.clone_path:
            diff_text = await compute_diff(_to_path(repo.clone_path))
            await dao.update_swarm_job(container.session_factory, job_id, diff=diff_text)
    parsed = parse_unified_diff(diff_text)
    return DiffSummary.model_validate(to_payload(job_id, parsed))


def _to_path(value: str) -> Any:
    from pathlib import Path

    return Path(value)


@router.websocket("/jobs/{job_id}/ws")
async def job_websocket(websocket: WebSocket, job_id: str) -> None:
    """WebSocket mirror of the SSE stream (JSON frames)."""
    container = websocket.app.state.container
    await websocket.accept()
    if await dao.get_swarm_job(container.session_factory, job_id) is None:
        await websocket.send_text(json.dumps({"type": "error", "data": {"message": "job not found"}}))
        await websocket.close()
        return

    # Replay backlog, then follow the bus.
    records = await dao.list_swarm_events(container.session_factory, job_id)
    for record in records:
        await websocket.send_text(
            json.dumps(
                {
                    "type": record.type,
                    "agent": record.agent,
                    "seq": record.id,
                    "data": record.data or {},
                },
                default=str,
            )
        )

    subscription = container.bus.subscribe(f"job:{job_id}")
    try:
        while True:
            event = await subscription.next_event(timeout=15.0)
            if event is None:
                await websocket.send_text(json.dumps({"type": "ping"}))
                continue
            await websocket.send_text(
                json.dumps(
                    {"type": event.type, "agent": event.data.get("agent"), "seq": event.seq, "data": event.data},
                    default=str,
                )
            )
            if event.type in ("job.completed", "job.failed", "job.cancelled"):
                break
    except WebSocketDisconnect:
        pass
    finally:
        container.bus.unsubscribe(subscription)
