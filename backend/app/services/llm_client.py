"""Async OpenAI-compatible chat-completions client (httpx).

Works against any endpoint implementing ``POST {base_url}/chat/completions``:
NVIDIA NIM, DashScope compatible-mode, OpenRouter, OpenAI, Anthropic's
OpenAI-compat surface, Gemini's OpenAI-compat surface, vLLM, Ollama, …
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Literal

import httpx

from app.core.errors import ProviderError

Role = Literal["system", "user", "assistant"]

_USER_AGENT = "nexus-ai-swarm/1.0 (+https://github.com/robert2687/agent-app)"


@dataclass(slots=True)
class ChatResult:
    """A complete (non-streaming) chat completion."""

    content: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    finish_reason: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class StreamChunk:
    """One streamed delta."""

    content: str = ""
    finish_reason: str | None = None
    usage: dict[str, int] | None = None


class ProviderAPIError(ProviderError):
    """HTTP-level failure from a provider endpoint."""

    def __init__(self, provider_id: str, status_code: int, message: str) -> None:
        super().__init__(message, details={"provider_id": provider_id, "status": status_code})
        self.provider_id = provider_id
        self.status_code = status_code


def build_headers(
    *,
    auth_scheme: str,
    api_key: str,
    extra_headers: dict[str, str] | None = None,
) -> dict[str, str]:
    """Construct request headers for the configured auth scheme."""
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": _USER_AGENT,
    }
    if auth_scheme == "x-api-key":
        headers["x-api-key"] = api_key
        headers["Authorization"] = f"Bearer {api_key}"
    else:
        headers["Authorization"] = f"Bearer {api_key}"
    if extra_headers:
        headers.update(extra_headers)
    return headers


class OpenAICompatibleClient:
    """Thin, fully-typed HTTP client for OpenAI-compatible providers."""

    def __init__(
        self,
        *,
        timeout: float = 120.0,
        stream_timeout: float = 300.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._timeout = timeout
        self._stream_timeout = stream_timeout
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=15.0),
            transport=transport,
            follow_redirects=True,
        )

    async def aclose(self) -> None:
        """Release the underlying connection pool."""
        await self._client.aclose()

    # ── Non-streaming ──────────────────────────────────────────────────────
    async def chat(
        self,
        *,
        provider_id: str,
        base_url: str,
        api_key: str,
        model: str,
        messages: list[dict[str, str]],
        auth_scheme: str = "bearer",
        extra_headers: dict[str, str] | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.2,
    ) -> ChatResult:
        url = f"{base_url.rstrip('/')}/chat/completions"
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        try:
            response = await self._client.post(
                url,
                json=payload,
                headers=build_headers(
                    auth_scheme=auth_scheme, api_key=api_key, extra_headers=extra_headers
                ),
            )
        except httpx.HTTPError as exc:
            raise ProviderAPIError(provider_id, 0, f"Transport error: {exc}") from exc

        if response.status_code >= 400:
            raise ProviderAPIError(
                provider_id, response.status_code, _error_body(response)
            )

        try:
            body = response.json()
        except ValueError as exc:
            raise ProviderAPIError(provider_id, 502, "Provider returned non-JSON body") from exc
        return _parse_chat_response(provider_id, body)

    # ── Streaming ──────────────────────────────────────────────────────────
    async def stream_chat(
        self,
        *,
        provider_id: str,
        base_url: str,
        api_key: str,
        model: str,
        messages: list[dict[str, str]],
        auth_scheme: str = "bearer",
        extra_headers: dict[str, str] | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.2,
    ) -> AsyncIterator[StreamChunk]:
        url = f"{base_url.rstrip('/')}/chat/completions"
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }
        try:
            async with self._client.stream(
                "POST",
                url,
                json=payload,
                headers=build_headers(
                    auth_scheme=auth_scheme, api_key=api_key, extra_headers=extra_headers
                ),
                timeout=httpx.Timeout(self._stream_timeout, connect=15.0),
            ) as response:
                if response.status_code >= 400:
                    body = (await response.aread()).decode("utf-8", "replace")
                    raise ProviderAPIError(
                        provider_id, response.status_code, _truncate(body)
                    )
                async for chunk in _iter_sse_chunks(response):
                    yield chunk
        except ProviderAPIError:
            raise
        except httpx.HTTPError as exc:
            raise ProviderAPIError(provider_id, 0, f"Stream transport error: {exc}") from exc


def _parse_chat_response(provider_id: str, body: dict[str, Any]) -> ChatResult:
    try:
        choices = body["choices"]
        message = choices[0]["message"]
        usage = body.get("usage") or {}
        return ChatResult(
            content=message.get("content") or "",
            prompt_tokens=int(usage.get("prompt_tokens", 0) or 0),
            completion_tokens=int(usage.get("completion_tokens", 0) or 0),
            finish_reason=choices[0].get("finish_reason"),
            raw=body,
        )
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise ProviderAPIError(
            provider_id, 502, f"Malformed completion payload: {body!r:.400}"
        ) from exc


async def _iter_sse_chunks(response: httpx.Response) -> AsyncIterator[StreamChunk]:
    """Parse ``data: {...}`` SSE lines into typed stream chunks."""
    async for line in response.aiter_lines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            return
        try:
            obj = json.loads(data)
        except json.JSONDecodeError:
            continue
        chunk = StreamChunk()
        choices = obj.get("choices") or []
        if choices:
            delta = choices[0].get("delta") or {}
            chunk.content = delta.get("content") or ""
            chunk.finish_reason = choices[0].get("finish_reason")
        if isinstance(obj.get("usage"), dict):
            chunk.usage = {
                "prompt_tokens": int(obj["usage"].get("prompt_tokens", 0) or 0),
                "completion_tokens": int(obj["usage"].get("completion_tokens", 0) or 0),
            }
        yield chunk


def _error_body(response: httpx.Response) -> str:
    try:
        body = response.json()
        message = body.get("error")
        if isinstance(message, dict):
            message = message.get("message") or str(message)
        if not message:
            message = response.text
    except ValueError:
        message = response.text
    return f"HTTP {response.status_code}: {_truncate(str(message))}"


def _truncate(text: str, limit: int = 512) -> str:
    return text if len(text) <= limit else text[: limit - 3] + "..."
