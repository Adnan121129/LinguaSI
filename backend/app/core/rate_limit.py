"""Rate limiting.

A single-process sliding-window limiter is used by default. When REDIS_URL is configured
(needed once the API runs on more than one instance) a Redis fixed-window counter is used
instead so limits are shared across instances.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict, deque

from fastapi import Request

from app.core.config import settings
from app.core.errors import RateLimitedError

logger = logging.getLogger("linguasi.ratelimit")


class MemoryRateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str, limit: int, window_seconds: int) -> bool:
        now = time.monotonic()
        with self._lock:
            bucket = self._hits[key]
            while bucket and now - bucket[0] > window_seconds:
                bucket.popleft()
            if len(bucket) >= limit:
                return False
            bucket.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


class RedisRateLimiter:
    def __init__(self, url: str) -> None:
        import redis  # imported lazily: only needed when REDIS_URL is set

        self._redis = redis.Redis.from_url(url, socket_timeout=0.5, socket_connect_timeout=0.5)
        self._fallback = MemoryRateLimiter()

    def hit(self, key: str, limit: int, window_seconds: int) -> bool:
        window = int(time.time() // window_seconds)
        redis_key = f"lsi:rl:{key}:{window}"
        try:
            pipe = self._redis.pipeline()
            pipe.incr(redis_key)
            pipe.expire(redis_key, window_seconds + 1)
            count, _ = pipe.execute()
            return int(count) <= limit
        except Exception:  # Redis outage must not take the API down
            logger.warning("Redis rate limiter unavailable, using in-memory limiter", exc_info=True)
            return self._fallback.hit(key, limit, window_seconds)

    def reset(self) -> None:
        self._fallback.reset()


def _build_limiter() -> MemoryRateLimiter | RedisRateLimiter:
    if settings.redis_url:
        try:
            return RedisRateLimiter(settings.redis_url)
        except Exception:
            logger.warning("Could not initialise Redis rate limiter, falling back to memory", exc_info=True)
    return MemoryRateLimiter()


limiter = _build_limiter()


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def enforce(key: str, limit: int, window_seconds: int, message: str | None = None) -> None:
    if not settings.rate_limit_enabled:
        return
    if not limiter.hit(key, limit, window_seconds):
        raise RateLimitedError(message)


def rate_limit(scope: str, limit: int, window_seconds: int):
    """FastAPI dependency factory limiting requests per client IP for a named scope."""

    def dependency(request: Request) -> None:
        enforce(f"{scope}:{client_ip(request)}", limit, window_seconds)

    return dependency
