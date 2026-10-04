"""Tests for the sliding-window rate limiter and circuit breaker."""

from __future__ import annotations

from app.services.rate_limiter import (
    CircuitBreaker,
    CircuitState,
    ProviderHealth,
    SlidingWindowRateLimiter,
)


class TestSlidingWindow:
    def test_allows_up_to_limit(self) -> None:
        limiter = SlidingWindowRateLimiter(max_requests=3, window_seconds=60)
        assert limiter.allow()
        assert limiter.allow()
        assert limiter.allow()
        assert not limiter.allow()

    def test_peek_does_not_consume(self) -> None:
        limiter = SlidingWindowRateLimiter(max_requests=2, window_seconds=60)
        assert limiter.peek_count() == 0
        assert limiter.peek_count() == 0
        limiter.allow()
        assert limiter.peek_count() == 1

    def test_window_expires(self) -> None:
        limiter = SlidingWindowRateLimiter(max_requests=1, window_seconds=1)
        assert limiter.allow()
        assert not limiter.allow()
        import time

        time.sleep(1.05)
        assert limiter.allow()

    def test_retry_after(self) -> None:
        limiter = SlidingWindowRateLimiter(max_requests=1, window_seconds=30)
        assert limiter.retry_after_seconds() == 0.0
        limiter.allow()
        remaining = limiter.retry_after_seconds()
        assert 0.0 < remaining <= 30.0


class TestCircuitBreaker:
    def test_opens_after_threshold(self) -> None:
        breaker = CircuitBreaker(failure_threshold=3, reset_seconds=60)
        assert breaker.state is CircuitState.CLOSED
        breaker.record_failure("boom 1")
        breaker.record_failure("boom 2")
        assert breaker.state is CircuitState.CLOSED
        breaker.record_failure("boom 3")
        assert breaker.state is CircuitState.OPEN
        assert not breaker.allow_request()

    def test_success_resets(self) -> None:
        breaker = CircuitBreaker(failure_threshold=2, reset_seconds=60)
        breaker.record_failure("boom")
        breaker.record_success()
        breaker.record_failure("boom")
        assert breaker.state is CircuitState.CLOSED

    def test_half_open_after_cooldown(self) -> None:
        breaker = CircuitBreaker(failure_threshold=1, reset_seconds=1)
        breaker.record_failure("boom")
        assert breaker.state is CircuitState.OPEN
        import time

        time.sleep(1.05)
        assert breaker.state is CircuitState.HALF_OPEN
        assert breaker.allow_request()
        breaker.record_success()
        assert breaker.state is CircuitState.CLOSED


class TestProviderHealth:
    def test_score_penalizes_open_circuit(self) -> None:
        health = ProviderHealth(
            rate_limiter=SlidingWindowRateLimiter(10, 60),
            breaker=CircuitBreaker(1, 60),
        )
        closed_score = health.score()
        health.breaker.record_failure("boom")
        assert health.score() > closed_score

    def test_cold_start_scores_better_than_slow(self) -> None:
        cold = ProviderHealth(SlidingWindowRateLimiter(10, 60), CircuitBreaker(1, 60))
        slow = ProviderHealth(SlidingWindowRateLimiter(10, 60), CircuitBreaker(1, 60))
        slow.ewma_latency_ms = 5000.0
        assert cold.score() < slow.score()
