"""Provider catalog, health telemetry and a routed chat playground endpoint."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.deps import ContainerDep
from app.db import dao
from app.schemas.provider import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ProviderCatalog,
    ProviderDefinition,
    ProviderRuntimeStatus,
    UsageSummary,
)

router = APIRouter(prefix="/providers", tags=["providers"])


@router.get("", response_model=ProviderCatalog)
async def list_providers(container: ContainerDep) -> ProviderCatalog:
    """Full provider catalog with live health/telemetry for each entry."""
    return ProviderCatalog(
        vault_config=container.router.vault_config_echo(),
        providers=[
            ProviderRuntimeStatus.model_validate(row)
            for row in container.router.snapshot()
        ],
    )


@router.get("/usage", response_model=UsageSummary)
async def usage(container: ContainerDep) -> UsageSummary:
    """Aggregated provider usage telemetry."""
    summary = await dao.usage_summary(container.session_factory)
    return UsageSummary.model_validate(summary)


@router.get("/{provider_id}", response_model=ProviderDefinition)
async def get_provider(provider_id: str, container: ContainerDep) -> ProviderDefinition:
    """Static catalog entry for one provider."""
    return container.router.get_definition(provider_id)


@router.post(
    "/chat",
    response_model=ChatCompletionResponse,
    status_code=status.HTTP_200_OK,
)
async def routed_chat(
    payload: ChatCompletionRequest, container: ContainerDep
) -> ChatCompletionResponse:
    """Ad-hoc routed completion — the simplest way to test the router live."""
    result = await container.router.chat(
        messages=[m.model_dump() for m in payload.messages],
        model=payload.model,
        prefer_provider_id=payload.provider_id,
        purpose="playground",
        job_id=None,
        max_tokens=payload.max_tokens,
        temperature=payload.temperature,
    )
    return ChatCompletionResponse(
        provider_id=result.provider_id,
        model=result.model,
        content=result.content,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        latency_ms=round(result.latency_ms, 1),
    )
