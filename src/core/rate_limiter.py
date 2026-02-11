"""Async-safe token-bucket rate limiter shared across all agents.

Prevents exceeding Groq free-tier limits (~30 requests/minute).
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field


@dataclass
class TokenBucketRateLimiter:
    requests_per_minute: int = 30
    burst_size: int = 5

    _tokens: float = field(init=False, default=0.0)
    _last_refill: float = field(init=False, default=0.0)
    _lock: asyncio.Lock = field(init=False, default_factory=asyncio.Lock)

    def __post_init__(self) -> None:
        self._tokens = float(self.burst_size)
        self._last_refill = time.monotonic()

    async def acquire(self) -> None:
        """Wait until a token is available, then consume one."""
        async with self._lock:
            self._refill()
            while self._tokens < 1.0:
                wait_time = 60.0 / self.requests_per_minute
                # Release lock while sleeping so other coroutines aren't blocked
                self._lock.release()
                await asyncio.sleep(wait_time)
                await self._lock.acquire()
                self._refill()
            self._tokens -= 1.0

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        refill = elapsed * (self.requests_per_minute / 60.0)
        self._tokens = min(self._tokens + refill, float(self.burst_size))
        self._last_refill = now

    @property
    def tokens_remaining(self) -> float:
        self._refill()
        return self._tokens


# Module-level singleton (initialised lazily via get_rate_limiter)
_limiter: TokenBucketRateLimiter | None = None


def get_rate_limiter(
    requests_per_minute: int = 30,
    burst_size: int = 5,
) -> TokenBucketRateLimiter:
    global _limiter
    if _limiter is None:
        _limiter = TokenBucketRateLimiter(
            requests_per_minute=requests_per_minute,
            burst_size=burst_size,
        )
    return _limiter
