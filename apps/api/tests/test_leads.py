"""Tests for the leads API — pagination, filtering, and input validation."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.conftest import TEST_BUSINESS_ID


def _make_paginated_result(count: int = 0):
    """Create a mock session.execute result that satisfies the count + item queries."""
    count_result = MagicMock()
    count_result.scalar_one.return_value = count
    return count_result


# ---------------------------------------------------------------------------
# Input validation (422 without touching DB)
# ---------------------------------------------------------------------------


async def test_list_leads_page_must_be_positive(auth_client):
    response = await auth_client.get(
        f"/api/v1/leads/{TEST_BUSINESS_ID}",
        params={"page": 0},
    )
    assert response.status_code == 422


async def test_list_leads_page_size_capped_at_100(auth_client):
    response = await auth_client.get(
        f"/api/v1/leads/{TEST_BUSINESS_ID}",
        params={"page_size": 9999},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Business logic
# ---------------------------------------------------------------------------


async def test_list_leads_empty_result(auth_client, mock_db):
    count_result = MagicMock()
    count_result.scalar_one.return_value = 0

    items_result = MagicMock()
    items_result.scalars.return_value.all.return_value = []

    mock_db.execute = AsyncMock(side_effect=[count_result, items_result])

    response = await auth_client.get(f"/api/v1/leads/{TEST_BUSINESS_ID}")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 0
    assert body["items"] == []
    assert body["page"] == 1
    assert body["pages"] == 1


async def test_get_lead_not_found_returns_404(auth_client, mock_db):
    mock_db.get = AsyncMock(return_value=None)
    fake_id = uuid.uuid4()

    response = await auth_client.get(f"/api/v1/leads/{TEST_BUSINESS_ID}/{fake_id}")
    assert response.status_code == 404


async def test_update_lead_unknown_lead_returns_404(auth_client, mock_db):
    mock_db.get = AsyncMock(return_value=None)
    fake_id = uuid.uuid4()

    response = await auth_client.patch(
        f"/api/v1/leads/{TEST_BUSINESS_ID}/{fake_id}",
        json={"stage": "qualified"},
    )
    assert response.status_code == 404


async def test_add_note_unknown_lead_returns_404(auth_client, mock_db):
    mock_db.get = AsyncMock(return_value=None)
    fake_id = uuid.uuid4()

    response = await auth_client.post(
        f"/api/v1/leads/{TEST_BUSINESS_ID}/{fake_id}/notes",
        json={"content": "Follow up tomorrow"},
    )
    assert response.status_code == 404


async def test_lead_timeline_unknown_lead_returns_404(auth_client, mock_db):
    mock_db.get = AsyncMock(return_value=None)
    fake_id = uuid.uuid4()

    response = await auth_client.get(f"/api/v1/leads/{TEST_BUSINESS_ID}/{fake_id}/timeline")
    assert response.status_code == 404
