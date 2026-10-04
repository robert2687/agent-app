"""Schemas describing AI providers surfaced by the Provider Router."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

AuthScheme = Literal["bearer", "x-api-key"]


class ProviderDefinition(BaseModel):
    """Static catalog entry for an OpenAI-compatible provider endpoint."""

    provider_id: str
    display_name: str
    base_url: str
    default_model: str
    supported_models: list[str] = Field(default_factory=list)
    auth_scheme: AuthScheme = "bearer"
    auth_header: str = "Bearer"
    extra_headers: dict[str, str] = Field(default_factory=dict)
    max_tokens_limit: int = 4096
    context_window: int = 32_768
    priority: int = 50
    notes: str | None = None


class ProviderRuntimeStatus(BaseModel):
    """Live health/telemetry snapshot of one provider."""

    provider_id: str
    display_name: str
    base_url: str
    default_model: str
    supported_models: list[str]
    max_tokens_limit: int
    priority: int
    key_configured: bool
    key_fingerprint: str | None = None
    key_status: Literal["active", "invalid", "revoked"] | None = None
    circuit: Literal["closed", "open", "half_open"]
    requests_in_window: int
    rate_limit_max: int
    rate_limit_window_seconds: int
    ewma_latency_ms: float | None
    total_requests: int
    failed_requests: int
    last_error: str | None = None


class ProviderCatalog(BaseModel):
    """Full provider catalog with vault_config echo (reference schema)."""

    vault_config: dict[str, Any]
    providers: list[ProviderRuntimeStatus]


class ChatMessage(BaseModel):
    """A single OpenAI-compatible chat message."""

    role: Literal["system", "user", "assistant"]
    content: str


class ChatCompletionRequest(BaseModel):
    """Ad-hoc (playground) chat request routed through the provider router."""

    messages: list[ChatMessage] = Field(min_length=1, max_length=64)
    model: str | None = None
    provider_id: str | None = None
    max_tokens: int = Field(default=2048, ge=16, le=32_768)
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)


class ChatCompletionResponse(BaseModel):
    """Routed chat completion result."""

    provider_id: str
    model: str
    content: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float


class UsageSummary(BaseModel):
    """Aggregated usage telemetry."""

    total_requests: int
    ok_requests: int
    failed_requests: int
    prompt_tokens: int
    completion_tokens: int
    avg_latency_ms: float
    by_provider: dict[str, dict[str, float]]
    window_start: datetime | None = None
