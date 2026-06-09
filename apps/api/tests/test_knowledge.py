"""Tests for the knowledge base and document endpoints."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import TEST_BUSINESS_ID


# ---------------------------------------------------------------------------
# Knowledge base CRUD
# ---------------------------------------------------------------------------


async def test_list_kbs_returns_empty(auth_client, mock_db):
    mock_db.execute.return_value.scalars.return_value.all.return_value = []

    response = await auth_client.get(f"/api/v1/knowledge/{TEST_BUSINESS_ID}")
    assert response.status_code == 200
    assert response.json() == []


async def test_create_kb_returns_201(auth_client, mock_db):
    kb_id = uuid.uuid4()

    created_kb = MagicMock()
    created_kb.id = kb_id
    created_kb.business_id = TEST_BUSINESS_ID
    created_kb.name = "Product FAQ"
    created_kb.description = None
    created_kb.documents = []
    from datetime import datetime, timezone
    now = datetime.now(tz=timezone.utc)
    created_kb.created_at = now
    created_kb.updated_at = now

    mock_db.refresh = AsyncMock()
    mock_db.add = MagicMock()

    # After add + flush, the kb is stored; refresh is mocked to populate the obj
    async def _mock_refresh(obj, attrs=None):
        pass

    mock_db.refresh = AsyncMock(side_effect=_mock_refresh)

    with patch("app.api.v1.knowledge.KnowledgeBase", return_value=created_kb):
        response = await auth_client.post(
            f"/api/v1/knowledge/{TEST_BUSINESS_ID}",
            json={"name": "Product FAQ"},
        )

    assert response.status_code == 201


async def test_create_kb_missing_name_returns_422(auth_client):
    response = await auth_client.post(
        f"/api/v1/knowledge/{TEST_BUSINESS_ID}",
        json={},
    )
    assert response.status_code == 422


async def test_get_kb_not_found_returns_404(auth_client, mock_db):
    mock_db.execute.return_value.scalar_one_or_none.return_value = None
    fake_id = uuid.uuid4()

    response = await auth_client.get(f"/api/v1/knowledge/{TEST_BUSINESS_ID}/{fake_id}")
    assert response.status_code == 404


async def test_add_document_unknown_kb_returns_404(auth_client, mock_db):
    mock_db.execute.return_value.scalar_one_or_none.return_value = None
    fake_id = uuid.uuid4()

    response = await auth_client.post(
        f"/api/v1/knowledge/{TEST_BUSINESS_ID}/{fake_id}/documents",
        json={"title": "Test doc", "content": "Hello world"},
    )
    assert response.status_code == 404


async def test_add_document_missing_fields_returns_422(auth_client):
    fake_id = uuid.uuid4()

    response = await auth_client.post(
        f"/api/v1/knowledge/{TEST_BUSINESS_ID}/{fake_id}/documents",
        json={"title": "No content field"},
    )
    assert response.status_code == 422


async def test_delete_document_not_found_returns_404(auth_client, mock_db):
    mock_db.get = AsyncMock(return_value=None)
    kb_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    response = await auth_client.delete(
        f"/api/v1/knowledge/{TEST_BUSINESS_ID}/{kb_id}/documents/{doc_id}"
    )
    assert response.status_code == 404
