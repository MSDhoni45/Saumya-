"""Shared pytest fixtures for the WhatsAgent API test suite.

Auth strategy: override `get_current_business` with a fixed BusinessContext so
tests never touch Supabase JWKS or real JWTs. The `anon_client` fixture omits
the override so the real `_bearer_token` dependency fires — no Authorization
header means a clean 401.

DB strategy: override `get_db_session` with a mock AsyncSession. Tests that
need specific DB return values set `mock_db.get.return_value` or
`mock_db.execute.return_value` before making the request.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.api.deps import BusinessContext, get_current_business
from app.db.session import get_db_session
from app.main import app

# ---------------------------------------------------------------------------
# Stable IDs reused across fixtures and tests
# ---------------------------------------------------------------------------

TEST_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
TEST_BUSINESS_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")
OTHER_BUSINESS_ID = uuid.UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")


# ---------------------------------------------------------------------------
# Core fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def business_ctx() -> BusinessContext:
    return BusinessContext(
        user_id=TEST_USER_ID,
        business_id=TEST_BUSINESS_ID,
        role="business_admin",
    )


@pytest.fixture
def mock_db() -> AsyncMock:
    """Mock AsyncSession pre-wired with common return shapes."""
    session = AsyncMock()
    session.add = MagicMock()

    # Default: session.get(Model, pk) → None (tests override as needed)
    session.get = AsyncMock(return_value=None)

    # Default: session.execute(...) → empty result set
    empty_result = MagicMock()
    empty_result.scalars.return_value.all.return_value = []
    empty_result.scalars.return_value.first.return_value = None
    empty_result.scalar_one.return_value = 0
    empty_result.scalar_one_or_none.return_value = None
    empty_result.all.return_value = []
    session.execute = AsyncMock(return_value=empty_result)

    return session


@pytest_asyncio.fixture
async def auth_client(business_ctx: BusinessContext, mock_db: AsyncMock) -> AsyncClient:
    """Authenticated HTTP client; all requests act as TEST_BUSINESS_ID."""
    async def _override_db():
        yield mock_db

    app.dependency_overrides[get_current_business] = lambda: business_ctx
    app.dependency_overrides[get_db_session] = _override_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def anon_client() -> AsyncClient:
    """Unauthenticated HTTP client — no auth dependency override."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
