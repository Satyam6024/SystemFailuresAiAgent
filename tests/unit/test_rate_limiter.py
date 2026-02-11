"""Unit tests for src/core/rate_limiter.py."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import patch

import pytest

from src.core.rate_limiter import TokenBucketRateLimiter


class TestTokenBucketRateLimiter:
    def test_initial_tokens(self):
        limiter = TokenBucketRateLimiter(requests_per_minute=30, burst_size=5)
        assert limiter._tokens == 5.0

    def test_initial_tokens_custom_burst(self):
        limiter = TokenBucketRateLimiter(requests_per_minute=60, burst_size=10)
        assert limiter._tokens == 10.0

    @pytest.mark.asyncio
    async def test_acquire_consumes_token(self):
        limiter = TokenBucketRateLimiter(requests_per_minute=30, burst_size=5)
        initial = limiter._tokens
        await limiter.acquire()
        # After acquire, tokens should be reduced (roughly by 1, accounting for tiny refill)
        assert limiter._tokens < initial

    @pytest.mark.asyncio
    async def test_burst_allows_rapid_requests(self):
        limiter = TokenBucketRateLimiter(requests_per_minute=30, burst_size=5)
        # Should be able to do 5 rapid requests (burst)
        for _ in range(5):
            await limiter.acquire()
        # After burst, tokens should be near zero
        assert limiter._tokens < 1.0

    @pytest.mark.asyncio
    async def test_refill_over_time(self):
        limiter = TokenBucketRateLimiter(requests_per_minute=60, burst_size=3)
        # Drain tokens
        for _ in range(3):
            await limiter.acquire()

        # Simulate time passing (1 second = 1 token at 60/min)
        limiter._last_refill = time.monotonic() - 2.0
        limiter._refill()
        assert limiter._tokens >= 1.5  # ~2 tokens refilled

    def test_refill_caps_at_burst_size(self):
        limiter = TokenBucketRateLimiter(requests_per_minute=60, burst_size=5)
        # Simulate lots of time passing
        limiter._last_refill = time.monotonic() - 120.0
        limiter._refill()
        assert limiter._tokens == 5.0  # capped at burst_size

    def test_tokens_remaining_property(self):
        limiter = TokenBucketRateLimiter(requests_per_minute=30, burst_size=5)
        remaining = limiter.tokens_remaining
        assert remaining <= 5.0
        assert remaining > 0.0

    @pytest.mark.asyncio
    async def test_concurrent_acquire(self):
        """Multiple concurrent acquires should not exceed burst."""
        limiter = TokenBucketRateLimiter(requests_per_minute=600, burst_size=10)
        results = await asyncio.gather(
            *[limiter.acquire() for _ in range(10)]
        )
        assert len(results) == 10
        # All should complete, tokens near zero
        assert limiter._tokens < 1.0