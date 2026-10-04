"""Unified Provider Router: adaptive failover, rate limits, budgets.

Selection strategy
------------------
1. Filter providers that (a) support the requested model (or default),
   (b) have an active sealed key, (c) have a closed/half-open circuit.
2. Order by explicit preference → catalog priority → health score
   (EWMA latency inflated by in-flight rate-limit pressure).
3. Attempt in order; on failure record telemetry, trip the breaker after
   ``N`` consecutive failures, and fail over to the next candidate.
4. Enforce a per-job token budget before every call (BudgetExceededError).
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable

from app.core.config import Settings
from app.core.errors import (
    BudgetExceededError,
    NotFoundError,
    ProviderError,
    ProviderExhaustedError,
    VaultLockedError,
)
from app.schemas.provider import ProviderDefinition
from app.services.llm_client import (
    ChatResult,
    OpenAICompatibleClient,
    ProviderAPIError,
)
from app.services.rate_limiter import CircuitBreaker, ProviderHealth, SlidingWindowRateLimiter
from app.services.vault import KeyVault, SealedSecret

UsageSink = Callable[
    [
        str | None,   # job_id
        str,          # provider_id
        str,          # model
        str,          # purpose
        int,          # prompt_tokens
        int,          # completion_tokens
        float,        # latency_ms
        bool,         # ok
        str | None,   # error_code
    ],
    Awaitable[None],
]

_EWMA_ALPHA = 0.35
_ESTIMATED_TOKENS_PER_CHAR = 1 / 4  # ~4 chars per token heuristic


@dataclass(slots=True)
class RoutedChatResult:
    """Chat completion annotated with routing metadata."""

    content: str
    provider_id: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
    attempts: list[dict[str, str]] = field(default_factory=list)


class TokenLedger:
    """Per-job sliding token budget enforcement."""

    def __init__(self, budget: int) -> None:
        self._budget = budget
        self._spent = 0
        self._lock = asyncio.Lock()

    @property
    def budget(self) -> int:
        return self._budget

    @property
    def spent(self) -> int:
        return self._spent

    def remaining(self) -> int:
        return max(0, self._budget - self._spent)

    async def check(self, estimated_prompt_tokens: int, max_completion_tokens: int) -> None:
        async with self._lock:
            projected = self._spent + estimated_prompt_tokens + max_completion_tokens
            if projected > self._budget:
                raise BudgetExceededError(
                    "Token budget for this job would be exceeded.",
                    details={
                        "budget": self._budget,
                        "spent": self._spent,
                        "projected": projected,
                    },
                )

    async def record(self, prompt_tokens: int, completion_tokens: int) -> None:
        async with self._lock:
            self._spent += prompt_tokens + completion_tokens

    def summary(self) -> dict[str, int]:
        return {"budget": self._budget, "spent": self._spent, "remaining": self.remaining()}


class ProviderRouter:
    """Facade over the provider catalog, vault keys, health and budgets."""

    def __init__(
        self,
        *,
        settings: Settings,
        vault: KeyVault,
        client: OpenAICompatibleClient,
        usage_sink: UsageSink | None = None,
    ) -> None:
        self._settings = settings
        self._vault = vault
        self._client = client
        self._usage_sink = usage_sink
        self._definitions: dict[str, ProviderDefinition] = {}
        self._health: dict[str, ProviderHealth] = {}
        self._key_records: dict[str, SealedSecret] = {}  # provider_id → sealed key
        self._key_meta: dict[str, dict[str, Any]] = {}   # provider_id → record metadata
        self._plaintext_cache: dict[str, str] = {}       # provider_id → decrypted key
        self._ledgers: dict[str, TokenLedger] = {}
        self._lock = asyncio.Lock()

    # ── Catalog ────────────────────────────────────────────────────────────
    def load_catalog(self, path: str | Path | None = None) -> list[ProviderDefinition]:
        """Load (or reload) the provider catalog JSON; returns definitions."""
        catalog_path = Path(path or self._settings.providers_config_path)
        if not catalog_path.exists():
            raise NotFoundError(f"Provider catalog not found: {catalog_path}")
        raw = json.loads(catalog_path.read_text(encoding="utf-8"))
        definitions: list[ProviderDefinition] = []
        for entry in raw.get("providers", []):
            definition = ProviderDefinition.model_validate(entry)
            definitions.append(definition)
            self._definitions[definition.provider_id] = definition
            if definition.provider_id not in self._health:
                self._health[definition.provider_id] = ProviderHealth(
                    rate_limiter=SlidingWindowRateLimiter(
                        self._settings.rate_limit_max_requests,
                        self._settings.rate_limit_window_seconds,
                    ),
                    breaker=CircuitBreaker(
                        self._settings.circuit_failure_threshold,
                        self._settings.circuit_reset_seconds,
                    ),
                )
        return definitions

    @property
    def definitions(self) -> dict[str, ProviderDefinition]:
        return dict(self._definitions)

    def get_definition(self, provider_id: str) -> ProviderDefinition:
        try:
            return self._definitions[provider_id]
        except KeyError as exc:
            raise NotFoundError(f"Unknown provider: {provider_id}") from exc

    # ── Key management ─────────────────────────────────────────────────────
    async def attach_key(
        self,
        *,
        provider_id: str,
        record_id: str,
        sealed: SealedSecret,
        fingerprint: str,
        status: str = "active",
        label: str = "",
    ) -> None:
        """Bind a freshly sealed key record to its provider slot."""
        async with self._lock:
            self.get_definition(provider_id)  # raises if unknown
            self._key_records[provider_id] = sealed
            self._key_meta[provider_id] = {
                "record_id": record_id,
                "fingerprint": fingerprint,
                "status": status,
                "label": label,
            }
            self._plaintext_cache.pop(provider_id, None)
            health = self._health[provider_id]
            health.breaker.record_success()

    async def detach_key(self, provider_id: str) -> None:
        """Remove the key binding (e.g. after deletion/revocation)."""
        async with self._lock:
            self._key_records.pop(provider_id, None)
            self._key_meta.pop(provider_id, None)
            self._plaintext_cache.pop(provider_id, None)

    def has_key(self, provider_id: str) -> bool:
        return provider_id in self._key_records

    async def resolve_key(self, provider_id: str) -> str:
        """Decrypt (and cache) the provider API key from the vault."""
        if provider_id in self._plaintext_cache:
            return self._plaintext_cache[provider_id]
        sealed = self._key_records.get(provider_id)
        if sealed is None:
            raise ProviderError(
                f"No API key configured for provider '{provider_id}'.",
                details={"provider_id": provider_id},
            )
        definition = self.get_definition(provider_id)
        aad = f"{definition.provider_id}:{self._key_meta[provider_id]['record_id']}"
        plaintext = self._vault.open(sealed, aad=aad)
        self._plaintext_cache[provider_id] = plaintext
        return plaintext

    # ── Budgets ────────────────────────────────────────────────────────────
    def get_ledger(self, job_id: str, *, create: bool = True) -> TokenLedger | None:
        if job_id in self._ledgers:
            return self._ledgers[job_id]
        if create:
            self._ledgers[job_id] = TokenLedger(self._settings.token_budget_per_job)
            return self._ledgers[job_id]
        return None

    def release_ledger(self, job_id: str) -> None:
        self._ledgers.pop(job_id, None)

    # ── Selection ──────────────────────────────────────────────────────────
    def candidates(
        self,
        *,
        model: str | None = None,
        prefer_provider_id: str | None = None,
    ) -> list[str]:
        """Ordered candidate provider ids for a request."""
        usable: list[str] = []
        for provider_id, definition in self._definitions.items():
            if provider_id not in self._key_records:
                continue
            if model is not None and model not in definition.supported_models:
                continue
            health = self._health[provider_id]
            if not health.breaker.allow_request():
                continue
            usable.append(provider_id)

        preferred = [p for p in usable if p == prefer_provider_id]
        rest = [p for p in usable if p != prefer_provider_id]
        rest.sort(
            key=lambda p: (
                self._definitions[p].priority,
                self._health[p].score(),
            )
        )
        return preferred + rest

    def resolve_model(self, provider_id: str, model: str | None) -> str:
        definition = self.get_definition(provider_id)
        if model is None:
            return definition.default_model
        if model not in definition.supported_models:
            raise ProviderError(
                f"Model '{model}' is not supported by provider '{provider_id}'.",
                details={"supported_models": definition.supported_models},
            )
        return model

    # ── Chat ───────────────────────────────────────────────────────────────
    async def chat(
        self,
        *,
        messages: list[dict[str, str]],
        model: str | None = None,
        prefer_provider_id: str | None = None,
        purpose: str = "chat",
        job_id: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.2,
    ) -> RoutedChatResult:
        """Route one chat completion with adaptive failover."""
        ledger = self.get_ledger(job_id) if job_id else None
        estimated_prompt = max(
            1, int(sum(len(m.get("content", "")) for m in messages) * _ESTIMATED_TOKENS_PER_CHAR)
        )

        candidate_ids = self.candidates(
            model=model, prefer_provider_id=prefer_provider_id
        )
        if not candidate_ids:
            raise ProviderExhaustedError(
                "No provider is currently available (missing keys, open circuits, or model mismatch).",
                details={"model": model, "prefer_provider_id": prefer_provider_id},
            )

        attempts: list[dict[str, str]] = []
        for provider_id in candidate_ids:
            definition = self.get_definition(provider_id)
            chosen_model = model or definition.default_model
            resolved_max_tokens = min(
                max_tokens or definition.max_tokens_limit, definition.max_tokens_limit
            )
            health = self._health[provider_id]

            if not health.rate_limiter.allow():
                attempts.append(
                    {"provider_id": provider_id, "outcome": "rate_limited"}
                )
                continue

            if ledger is not None:
                await ledger.check(estimated_prompt, resolved_max_tokens)

            api_key = await self._resolve_key_or_fail(provider_id, attempts)
            if api_key is None:
                continue

            started = time.perf_counter()
            try:
                result: ChatResult = await self._client.chat(
                    provider_id=provider_id,
                    base_url=definition.base_url,
                    api_key=api_key,
                    model=chosen_model,
                    messages=messages,
                    auth_scheme=definition.auth_scheme,
                    extra_headers=definition.extra_headers,
                    max_tokens=resolved_max_tokens,
                    temperature=temperature,
                )
            except ProviderAPIError as exc:
                await self._record_failure(
                    provider_id, chosen_model, purpose, job_id, started, exc
                )
                attempts.append(
                    {"provider_id": provider_id, "outcome": f"http_{exc.status_code}"}
                )
                if exc.status_code in (401, 403):
                    self._plaintext_cache.pop(provider_id, None)
                continue

            latency_ms = (time.perf_counter() - started) * 1000.0
            prompt_tokens = result.prompt_tokens or estimated_prompt
            completion_tokens = result.completion_tokens or _estimate_tokens(result.content)
            await self._record_success(
                provider_id,
                chosen_model,
                purpose,
                job_id,
                prompt_tokens,
                completion_tokens,
                latency_ms,
            )
            if ledger is not None:
                await ledger.record(prompt_tokens, completion_tokens)
            attempts.append({"provider_id": provider_id, "outcome": "ok"})
            return RoutedChatResult(
                content=result.content,
                provider_id=provider_id,
                model=chosen_model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=latency_ms,
                attempts=attempts,
            )

        raise ProviderExhaustedError(
            "All candidate providers failed for this request.",
            details={"attempts": attempts, "purpose": purpose},
        )

    # ── Streaming chat ─────────────────────────────────────────────────────
    async def stream_chat(
        self,
        *,
        messages: list[dict[str, str]],
        model: str | None = None,
        prefer_provider_id: str | None = None,
        purpose: str = "chat",
        job_id: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.2,
    ) -> "AsyncStreamSession":
        """Start a streamed completion; returns a session object."""
        return AsyncStreamSession(
            router=self,
            messages=messages,
            model=model,
            prefer_provider_id=prefer_provider_id,
            purpose=purpose,
            job_id=job_id,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    # ── Telemetry helpers ──────────────────────────────────────────────────
    async def _resolve_key_or_fail(
        self, provider_id: str, attempts: list[dict[str, str]]
    ) -> str | None:
        try:
            return await self.resolve_key(provider_id)
        except (VaultLockedError, ProviderError) as exc:
            attempts.append({"provider_id": provider_id, "outcome": f"key_error:{exc.error_code}"})
            return None

    async def _record_failure(
        self,
        provider_id: str,
        model: str,
        purpose: str,
        job_id: str | None,
        started: float,
        exc: ProviderAPIError,
    ) -> None:
        latency_ms = (time.perf_counter() - started) * 1000.0
        health = self._health[provider_id]
        health.total_requests += 1
        health.failed_requests += 1
        health.breaker.record_failure(exc.message)
        if self._usage_sink is not None:
            await self._usage_sink(
                job_id, provider_id, model, purpose, 0, 0, latency_ms, False, f"HTTP_{exc.status_code}"
            )

    async def _record_success(
        self,
        provider_id: str,
        model: str,
        purpose: str,
        job_id: str | None,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: float,
    ) -> None:
        health = self._health[provider_id]
        health.total_requests += 1
        if health.ewma_latency_ms is None:
            health.ewma_latency_ms = latency_ms
        else:
            health.ewma_latency_ms = (
                _EWMA_ALPHA * latency_ms + (1 - _EWMA_ALPHA) * health.ewma_latency_ms
            )
        health.breaker.record_success()
        if self._usage_sink is not None:
            await self._usage_sink(
                job_id, provider_id, model, purpose, prompt_tokens, completion_tokens, latency_ms, True, None
            )

    def snapshot(self) -> list[dict[str, Any]]:
        """Health/telemetry snapshot for the provider catalog API."""
        rows: list[dict[str, Any]] = []
        for provider_id, definition in sorted(
            self._definitions.items(), key=lambda kv: kv[1].priority
        ):
            health = self._health[provider_id]
            meta = self._key_meta.get(provider_id)
            rows.append(
                {
                    "provider_id": provider_id,
                    "display_name": definition.display_name,
                    "base_url": definition.base_url,
                    "default_model": definition.default_model,
                    "supported_models": definition.supported_models,
                    "max_tokens_limit": definition.max_tokens_limit,
                    "priority": definition.priority,
                    "key_configured": provider_id in self._key_records,
                    "key_fingerprint": (meta or {}).get("fingerprint"),
                    "key_status": (meta or {}).get("status") if meta else None,
                    "circuit": health.circuit_state.value,
                    "requests_in_window": health.rate_limiter.peek_count(),
                    "rate_limit_max": health.rate_limiter.max_requests,
                    "rate_limit_window_seconds": health.rate_limiter.window_seconds,
                    "ewma_latency_ms": health.ewma_latency_ms,
                    "total_requests": health.total_requests,
                    "failed_requests": health.failed_requests,
                    "last_error": health.breaker.last_error,
                }
            )
        return rows

    def vault_config_echo(self) -> dict[str, Any]:
        """Echo the reference vault_config block from the catalog file."""
        catalog_path = Path(self._settings.providers_config_path)
        if catalog_path.exists():
            try:
                raw = json.loads(catalog_path.read_text(encoding="utf-8"))
                vault_block = raw.get("vault_config")
                if isinstance(vault_block, dict):
                    return vault_block
            except (json.JSONDecodeError, OSError):
                pass
        return {
            "encryption_algorithm": "AES-256-GCM",
            "pbkdf2_iterations": self._settings.vault_pbkdf2_iterations,
        }


class AsyncStreamSession:
    """Lazily started streamed completion with failover on the first chunk.

    Provider selection and the HTTP request begin on the first ``__aiter__``;
    if the connection fails before any token is emitted, the session fails
    over to the next candidate transparently.
    """

    def __init__(
        self,
        *,
        router: ProviderRouter,
        messages: list[dict[str, str]],
        model: str | None,
        prefer_provider_id: str | None,
        purpose: str,
        job_id: str | None,
        max_tokens: int | None,
        temperature: float,
    ) -> None:
        self._router = router
        self._messages = messages
        self._model = model
        self._prefer = prefer_provider_id
        self._purpose = purpose
        self._job_id = job_id
        self._max_tokens = max_tokens
        self._temperature = temperature
        self.provider_id: str | None = None
        self.model: str | None = None
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.latency_ms = 0.0

    def __aiter__(self):
        return self._run()

    async def _run(self):
        router = self._router
        candidate_ids = router.candidates(
            model=self._model, prefer_provider_id=self._prefer
        )
        if not candidate_ids:
            raise ProviderExhaustedError("No provider available for streaming request.")
        ledger = router.get_ledger(self._job_id) if self._job_id else None
        estimated_prompt = max(
            1,
            int(sum(len(m.get("content", "")) for m in self._messages) * _ESTIMATED_TOKENS_PER_CHAR),
        )

        for provider_id in candidate_ids:
            definition = router.get_definition(provider_id)
            model = self._model or definition.default_model
            resolved_max_tokens = min(
                self._max_tokens or definition.max_tokens_limit, definition.max_tokens_limit
            )
            health = router._health[provider_id]  # noqa: SLF001 - session is router-internal
            if not health.rate_limiter.allow():
                continue
            if ledger is not None:
                await ledger.check(estimated_prompt, resolved_max_tokens)
            try:
                api_key = await router.resolve_key(provider_id)
            except (VaultLockedError, ProviderError):
                continue

            started = time.perf_counter()
            emitted = False
            content_parts: list[str] = []
            try:
                stream = router._client.stream_chat(  # noqa: SLF001
                    provider_id=provider_id,
                    base_url=definition.base_url,
                    api_key=api_key,
                    model=model,
                    messages=self._messages,
                    auth_scheme=definition.auth_scheme,
                    extra_headers=definition.extra_headers,
                    max_tokens=resolved_max_tokens,
                    temperature=self._temperature,
                )
                async for chunk in stream:
                    if chunk.content:
                        emitted = True
                        content_parts.append(chunk.content)
                        yield chunk.content
                    if chunk.usage:
                        self.prompt_tokens = chunk.usage.get("prompt_tokens", 0)
                        self.completion_tokens = chunk.usage.get("completion_tokens", 0)
                    if chunk.finish_reason:
                        break
            except ProviderAPIError as exc:
                if emitted:
                    await router._record_failure(  # noqa: SLF001
                        provider_id, model, self._purpose, self._job_id, started, exc
                    )
                    raise
                await router._record_failure(  # noqa: SLF001
                    provider_id, model, self._purpose, self._job_id, started, exc
                )
                continue  # clean failover — nothing was streamed yet

            self.provider_id = provider_id
            self.model = model
            self.latency_ms = (time.perf_counter() - started) * 1000.0
            if not self.prompt_tokens:
                self.prompt_tokens = estimated_prompt
            if not self.completion_tokens:
                self.completion_tokens = _estimate_tokens("".join(content_parts))
            await router._record_success(  # noqa: SLF001
                provider_id,
                model,
                self._purpose,
                self._job_id,
                self.prompt_tokens,
                self.completion_tokens,
                self.latency_ms,
            )
            if ledger is not None:
                await ledger.record(self.prompt_tokens, self.completion_tokens)
            return

        raise ProviderExhaustedError("All candidate providers failed while streaming.")


def _estimate_tokens(text: str) -> int:
    return max(1, int(len(text) * _ESTIMATED_TOKENS_PER_CHAR))
