"""Tests for the adaptive provider router (mock transport — no network)."""

from __future__ import annotations

import json

import httpx
import pytest

from app.core.errors import BudgetExceededError, ProviderExhaustedError
from app.services.provider_router import TokenLedger
from tests.conftest import attach_key, make_router_sync


def _chat_response(content: str, model: str) -> bytes:
    return json.dumps(
        {
            "choices": [{"message": {"role": "assistant", "content": content}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            "model": model,
        }
    ).encode("utf-8")


class TestCandidateSelection:
    async def test_no_keys_no_candidates(self, settings, vault, mock_catalog_path) -> None:
        router = make_router_sync(
            settings=settings,
            vault=vault,
            catalog_path=mock_catalog_path,
            transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b"{}")),
        )
        assert router.candidates() == []
        with pytest.raises(ProviderExhaustedError):
            await router.chat(messages=[{"role": "user", "content": "hi"}])

    async def test_model_filter(self, settings, vault, mock_catalog_path) -> None:
        router = make_router_sync(
            settings=settings,
            vault=vault,
            catalog_path=mock_catalog_path,
            transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b"{}")),
        )
        await attach_key(router, vault, "alpha", "sk-alpha")
        await attach_key(router, vault, "beta", "sk-beta")
        assert router.candidates(model="beta-large") == ["beta"]
        assert router.candidates(model="alpha-large") == ["alpha"]

    async def test_priority_ordering(self, settings, vault, mock_catalog_path) -> None:
        router = make_router_sync(
            settings=settings,
            vault=vault,
            catalog_path=mock_catalog_path,
            transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b"{}")),
        )
        await attach_key(router, vault, "alpha", "sk-alpha")
        await attach_key(router, vault, "beta", "sk-beta")
        assert router.candidates() == ["alpha", "beta"]  # alpha priority 10 < beta 20


class TestFailover:
    async def test_fails_over_to_healthy_provider(
        self, settings, vault, mock_catalog_path
    ) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if "alpha.test" in str(request.url):
                return httpx.Response(500, json={"error": {"message": "upstream exploded"}})
            return httpx.Response(200, content=_chat_response("from-beta", "beta-large"))

        router = make_router_sync(
            settings=settings, vault=vault, catalog_path=mock_catalog_path,
            transport=httpx.MockTransport(handler),
        )
        await attach_key(router, vault, "alpha", "sk-alpha")
        await attach_key(router, vault, "beta", "sk-beta")

        result = await router.chat(messages=[{"role": "user", "content": "hi"}])
        assert result.provider_id == "beta"
        assert result.content == "from-beta"
        assert result.attempts[0]["outcome"] == "http_500"

    async def test_all_failing_raises_exhausted(self, settings, vault, mock_catalog_path) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, json={"error": {"message": "down"}})

        router = make_router_sync(
            settings=settings, vault=vault, catalog_path=mock_catalog_path,
            transport=httpx.MockTransport(handler),
        )
        await attach_key(router, vault, "alpha", "sk-alpha")
        await attach_key(router, vault, "beta", "sk-beta")

        with pytest.raises(ProviderExhaustedError):
            await router.chat(messages=[{"role": "user", "content": "hi"}])
        snapshot = {row["provider_id"]: row for row in router.snapshot()}
        assert snapshot["alpha"]["failed_requests"] >= 1
        assert snapshot["beta"]["failed_requests"] >= 1

    async def test_success_records_latency_and_usage(
        self, settings, vault, mock_catalog_path
    ) -> None:
        captured: list[tuple] = []

        async def usage_sink(*args) -> None:
            captured.append(args)

        from app.services.llm_client import OpenAICompatibleClient

        client = OpenAICompatibleClient(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, content=_chat_response("ok", "alpha-large"))
            )
        )
        from app.services.provider_router import ProviderRouter

        router = ProviderRouter(settings=settings, vault=vault, client=client, usage_sink=usage_sink)
        router.load_catalog(str(mock_catalog_path))
        await attach_key(router, vault, "alpha", "sk-alpha")

        result = await router.chat(messages=[{"role": "user", "content": "hi"}])
        assert result.content == "ok"
        assert result.latency_ms >= 0
        assert len(captured) == 1
        assert captured[0][1] == "alpha"  # provider_id positional
        snapshot = {row["provider_id"]: row for row in router.snapshot()}
        assert snapshot["alpha"]["ewma_latency_ms"] is not None
        assert snapshot["alpha"]["total_requests"] == 1


class TestStreaming:
    async def test_stream_failover_before_first_token(
        self, settings, vault, mock_catalog_path
    ) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if "alpha.test" in str(request.url):
                return httpx.Response(401, json={"error": {"message": "bad key"}})
            stream = (
                b'data: {"choices":[{"delta":{"content":"he"}}]}\n\n'
                b'data: {"choices":[{"delta":{"content":"llo"}}]}\n\n'
                b"data: [DONE]\n\n"
            )
            return httpx.Response(200, content=stream, headers={"Content-Type": "text/event-stream"})

        router = make_router_sync(
            settings=settings, vault=vault, catalog_path=mock_catalog_path,
            transport=httpx.MockTransport(handler),
        )
        await attach_key(router, vault, "alpha", "sk-alpha")
        await attach_key(router, vault, "beta", "sk-beta")

        session = await router.stream_chat(messages=[{"role": "user", "content": "hi"}])
        tokens = [delta async for delta in session]
        assert "".join(tokens) == "hello"
        assert session.provider_id == "beta"


class TestTokenLedger:
    async def test_budget_exceeded(self, settings, vault, mock_catalog_path) -> None:
        router = make_router_sync(
            settings=settings, vault=vault, catalog_path=mock_catalog_path,
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, content=_chat_response("ok", "alpha-large"))
            ),
        )
        await attach_key(router, vault, "alpha", "sk-alpha")
        router.get_ledger("job-1")._budget = 0  # force exhaustion

        with pytest.raises(BudgetExceededError):
            await router.chat(
                messages=[{"role": "user", "content": "hi"}], job_id="job-1"
            )

    def test_ledger_accounting(self) -> None:
        ledger = TokenLedger(budget=100)
        ledger._spent = 90  # noqa: SLF001 - test seam
        assert ledger.remaining() == 10
        summary = ledger.summary()
        assert summary == {"budget": 100, "spent": 90, "remaining": 10}
