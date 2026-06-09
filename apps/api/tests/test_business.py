"""Tests for the business endpoint."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.conftest import TEST_BUSINESS_ID


def _make_business(business_id=TEST_BUSINESS_ID):
    biz = MagicMock()
    biz.id = business_id
    biz.name = "Acme Corp"
    biz.industry = "Technology"
    biz.timezone = "UTC"
    biz.onboarding_completed = False
    biz.created_at = datetime.now(tz=timezone.utc)
    biz.updated_at = datetime.now(tz=timezone.utc)
    return biz


async def test_get_business_not_found_returns_404(auth_client, mock_db):
    mock_db.get = AsyncMock(return_value=None)

    response = await auth_client.get(f"/api/v1/business/{TEST_BUSINESS_ID}")
    assert response.status_code == 404


async def test_update_business_not_found_returns_404(auth_client, mock_db):
    mock_db.get = AsyncMock(return_value=None)

    response = await auth_client.patch(
        f"/api/v1/business/{TEST_BUSINESS_ID}",
        json={"name": "New Name"},
    )
    assert response.status_code == 404


async def test_update_business_empty_name_rejected(auth_client, mock_db):
    biz = _make_business()
    mock_db.get = AsyncMock(return_value=biz)

    response = await auth_client.patch(
        f"/api/v1/business/{TEST_BUSINESS_ID}",
        json={"name": ""},
    )
    assert response.status_code == 422


async def test_update_business_name_too_long_rejected(auth_client):
    response = await auth_client.patch(
        f"/api/v1/business/{TEST_BUSINESS_ID}",
        json={"name": "x" * 201},
    )
    assert response.status_code == 422
