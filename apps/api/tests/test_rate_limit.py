"""Unit tests for app/core/rate_limit.py — atomic sliding-window behavior."""

from unittest.mock import MagicMock

import fakeredis.aioredis
import pytest
from fastapi import HTTPException

from app.core import rate_limit as rate_limit_module


def _make_request(path: str = "/api/v1/auth/login", ip: str = "10.0.0.1") -> MagicMock:
    request = MagicMock()
    request.url.path = path
    request.client.host = ip
    return request


@pytest.fixture
def check(monkeypatch: pytest.MonkeyPatch):
    """The inner dependency function, backed by a fresh in-memory Redis."""
    monkeypatch.setattr(rate_limit_module, "_redis", fakeredis.aioredis.FakeRedis(decode_responses=True))
    return rate_limit_module.rate_limit(max_requests=3, window_seconds=60).dependency


async def test_allows_up_to_max_requests(check):
    request = _make_request()
    for _ in range(3):
        await check(request)  # must not raise


async def test_rejects_request_over_limit(check):
    request = _make_request()
    for _ in range(3):
        await check(request)
    with pytest.raises(HTTPException) as exc_info:
        await check(request)
    assert exc_info.value.status_code == 429
    assert exc_info.value.headers["Retry-After"] == "60"


async def test_rejected_requests_do_not_extend_window(check):
    """Rejected requests must NOT be recorded — a sustained burst can't keep
    the window full forever (the bug in the old zadd-then-count pipeline)."""
    redis = rate_limit_module._redis
    request = _make_request()
    for _ in range(3):
        await check(request)

    key = f"rl:{request.url.path}:{request.client.host}"
    assert await redis.zcard(key) == 3

    for _ in range(5):
        with pytest.raises(HTTPException):
            await check(request)

    # Still exactly 3 recorded — rejected attempts left no trace.
    assert await redis.zcard(key) == 3


async def test_limits_are_per_ip(check):
    for _ in range(3):
        await check(_make_request(ip="10.0.0.1"))
    # Different IP, fresh budget.
    await check(_make_request(ip="10.0.0.2"))


async def test_limits_are_per_path(check):
    for _ in range(3):
        await check(_make_request(path="/api/v1/auth/login"))
    await check(_make_request(path="/api/v1/auth/signup"))


async def test_window_expires_old_entries(check, monkeypatch: pytest.MonkeyPatch):
    request = _make_request()
    real_time = rate_limit_module.time.time
    base = real_time()

    monkeypatch.setattr(rate_limit_module.time, "time", lambda: base)
    for _ in range(3):
        await check(request)
    with pytest.raises(HTTPException):
        await check(request)

    # 61 seconds later the old entries fall out of the window.
    monkeypatch.setattr(rate_limit_module.time, "time", lambda: base + 61)
    await check(request)
