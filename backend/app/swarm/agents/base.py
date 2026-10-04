"""Base class shared by every swarm agent role."""

from __future__ import annotations

from typing import Any, ClassVar

from app.core.errors import ProviderExhaustedError, ProviderError
from app.services.event_bus import EventBus
from app.services.provider_router import ProviderRouter
from app.swarm.context import SwarmContext


class BaseAgent:
    """A swarm agent: system persona + routed LLM completion + event emission."""

    role: ClassVar[str] = "base"
    description: ClassVar[str] = "Base agent"

    def __init__(self, router: ProviderRouter, bus: EventBus, job_id: str) -> None:
        self._router = router
        self._bus = bus
        self._job_id = job_id
        self._topic = f"job:{job_id}"
        self._last_summary: str = ""  # set by subclasses after each run

    # ── Events ─────────────────────────────────────────────────────────────
    async def _emit(self, type_: str, data: dict[str, Any]) -> None:
        await self._bus.publish(self._topic, type_, {"agent": self.role, **data})

    async def _emit_token(self, delta: str) -> None:
        await self._bus.publish(
            self._topic,
            "agent.token",
            {"agent": self.role, "delta": delta},
        )

    # ── Completion helpers ─────────────────────────────────────────────────
    async def _complete(
        self,
        ctx: SwarmContext,
        *,
        system: str,
        user: str,
        purpose: str,
        max_tokens: int = 4096,
        temperature: float = 0.2,
    ) -> str:
        """Stream a completion (token events emitted live), with sync fallback."""
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        parts: list[str] = []
        session = await self._router.stream_chat(
            messages=messages,
            model=ctx.preferred_model,
            prefer_provider_id=ctx.preferred_provider_id,
            purpose=purpose,
            job_id=self._job_id,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        try:
            async for delta in session:
                parts.append(delta)
                await self._emit_token(delta)
        except (ProviderExhaustedError, ProviderError):
            # Last-resort: non-streaming attempt (different code path/headers).
            result = await self._router.chat(
                messages=messages,
                model=ctx.preferred_model,
                prefer_provider_id=ctx.preferred_provider_id,
                purpose=purpose,
                job_id=self._job_id,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            content = result.content
            ctx.add_tokens(result.prompt_tokens, result.completion_tokens)
            if content:
                await self._emit_token(content)
            return content

        content = "".join(parts)
        ctx.add_tokens(session.prompt_tokens, session.completion_tokens)
        return content

    # ── Hook ───────────────────────────────────────────────────────────────
    async def run(self, ctx: SwarmContext) -> dict[str, Any]:
        """Execute the agent; overridden by each role."""
        raise NotImplementedError

    # ── Prompt building utilities ──────────────────────────────────────────
    @staticmethod
    def _file_listing(ctx: SwarmContext, limit: int = 120) -> str:
        files: list[str] = []
        for window in ctx.context_windows:
            files.extend(window.files)
        listing = "\n".join(files[:limit])
        if len(files) > limit:
            listing += f"\n… (+{len(files) - limit} more files)"
        return listing or "(no files ingested)"

    @staticmethod
    def _window_content(ctx: SwarmContext, max_chars: int = 60_000) -> str:
        chunks: list[str] = []
        budget = max_chars
        for window in ctx.context_windows:
            if budget <= 0:
                break
            take = window.content[:budget]
            chunks.append(take)
            budget -= len(take)
        return "\n\n".join(chunks)
