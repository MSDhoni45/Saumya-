"""IP-based sliding-window rate limiting via Redis.

Usage in a route:
    @router.post("/signup")
    async def signup(
        ...,
        _rl: None = Depends(rate_limit(max_requests=5, window_seconds=60)),
    ):
"""

import time
import uuid

import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, Request, status

from app.core.config import settings

_redis: aioredis.Redis | None = None

# Atomic check-and-record: prune the window, count, and only record the
# request if it's under the limit — all in one server-side step. A plain
# MULTI/EXEC pipeline can't do this because the zadd-then-count ordering
# always records rejected requests too, letting a sustained burst extend
# its own ban window indefinitely and inflate the set.
#
# KEYS[1] = window key
# ARGV    = window_start, now, max_requests, ttl_seconds, member
# Returns 1 if allowed, 0 if rate-limited.
_SLIDING_WINDOW_LUA = """
redis.call('ZREMRANGEBYSCORE', KEYS[1], 0, ARGV[1])
local count = redis.call('ZCARD', KEYS[1])
if count >= tonumber(ARGV[3]) then
    return 0
end
redis.call('ZADD', KEYS[1], ARGV[2], ARGV[5])
redis.call('EXPIRE', KEYS[1], ARGV[4])
return 1
"""


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

        allowed = await _get_redis().eval(  # type: ignore[misc]
            _SLIDING_WINDOW_LUA,
            1,
            key,
            str(window_start),
            str(now),
            str(max_requests),
            str(window_seconds + 1),
            f"{now}:{uuid.uuid4().hex}",
        )
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests — please try again later.",
                headers={"Retry-After": str(window_seconds)},
            )

    return Depends(_check)
