"""IP-based sliding-window rate limiting via Redis.

Usage in a route:
    @router.post("/signup")
    async def signup(
        ...,
        _rl: None = Depends(rate_limit(max_requests=5, window_seconds=60)),
    ):
"""

import time

import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, Request, status

from app.core.config import settings

_redis: aioredis.Redis | None = None


def _get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis


def rate_limit(max_requests: int, window_seconds: int):
    """Return a FastAPI dependency that enforces an IP-based sliding window rate limit."""

    async def _check(request: Request) -> None:
        ip = request.client.host if request.client else "unknown"
        key = f"rl:{request.url.path}:{ip}"
        now = time.time()
        window_start = now - window_seconds

        pipe = _get_redis().pipeline()
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zadd(key, {f"{now}:{id(object())}": now})
        pipe.zcard(key)
        pipe.expire(key, window_seconds + 1)
        results = await pipe.execute()

        count: int = results[2]
        if count > max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests — please try again later.",
                headers={"Retry-After": str(window_seconds)},
            )

    return Depends(_check)
