"""Sliding-window rate limiter and circuit breaker for provider routing."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Deque


class CircuitState(str, Enum):
    """Circuit-breaker states (closed → open → half_open → closed)."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class SlidingWindowRateLimiter:
    """Per-provider sliding-window request limiter."""

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        if max_requests < 1 or window_seconds < 1:
            raise ValueError("Rate limit bounds must be positive.")
        self._max = max_requests
        self._window = window_seconds
        self._events: Deque[float] = deque()

    @property
    def max_requests(self) -> int:
        return self._max

    @property
    def window_seconds(self) -> int:
        return self._window

    def _prune(self, now: float) -> None:
        cutoff = now - self._window
        while self._events and self._events[0] <= cutoff:
            self._events.popleft()

    def allow(self) -> bool:
        """Return True and record the request if capacity is available."""
        now = time.monotonic()
        self._prune(now)
        if len(self._events) >= self._max:
            return False
        self._events.append(now)
        return True

    def peek_count(self) -> int:
        """Requests currently inside the window (without consuming capacity)."""
        self._prune(time.monotonic())
        return len(self._events)

    def retry_after_seconds(self) -> float:
        """Seconds until the oldest event leaves the window (0 if allowed)."""
        now = time.monotonic()
        self._prune(now)
        if len(self._events) < self._max:
            return 0.0
        return max(0.0, self._events[0] + self._window - now)


class CircuitBreaker:
    """Consecutive-failure circuit breaker with half-open probing."""

    def __init__(self, failure_threshold: int, reset_seconds: int) -> None:
        if failure_threshold < 1 or reset_seconds < 1:
            raise ValueError("Circuit breaker bounds must be positive.")
        self._threshold = failure_threshold
        self._reset_seconds = reset_seconds
        self._failures = 0
        self._state = CircuitState.CLOSED
        self._opened_at = 0.0
        self._last_error: str | None = None

    @property
    def state(self) -> CircuitState:
        if self._state is CircuitState.OPEN:
            if time.monotonic() - self._opened_at >= self._reset_seconds:
                self._state = CircuitState.HALF_OPEN
        return self._state

    @property
    def last_error(self) -> str | None:
        return self._last_error

    def allow_request(self) -> bool:
        """Whether a request may be attempted right now."""
        return self.state is not CircuitState.OPEN

    def record_success(self) -> None:
        self._failures = 0
        self._state = CircuitState.CLOSED
        self._last_error = None

    def record_failure(self, error: str) -> CircuitState:
        self._failures += 1
        self._last_error = error[:256]
        if self._failures >= self._threshold:
            self._state = CircuitState.OPEN
            self._opened_at = time.monotonic()
        return self._state


@dataclass
class ProviderHealth:
    """Composite telemetry for a single provider endpoint."""

    rate_limiter: SlidingWindowRateLimiter
    breaker: CircuitBreaker
    ewma_latency_ms: float | None = None
    total_requests: int = 0
    failed_requests: int = 0

    @property
    def circuit_state(self) -> CircuitState:
        return self.breaker.state

    def score(self) -> float:
        """Latency-aware routing score (lower is better; None → cold start win)."""
        base = 1000.0 if self.ewma_latency_ms is None else self.ewma_latency_ms
        pressure = self.rate_limiter.peek_count() / max(1, self.rate_limiter.max_requests)
        penalty = 0.0 if self.circuit_state is CircuitState.CLOSED else 10_000.0
        return base * (1.0 + pressure) + penalty
