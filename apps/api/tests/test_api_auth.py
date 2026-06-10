"""Tests that verify authentication and authorization enforcement across all API routes.

Two categories:
  1. Unauthenticated → 401  (no token at all)
  2. Cross-tenant → 403     (valid token for a different business_id)
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import settings
from tests.conftest import OTHER_BUSINESS_ID, TEST_BUSINESS_ID

# ---------------------------------------------------------------------------
# Protected routes — 401 without any token
# ---------------------------------------------------------------------------

_BID = str(TEST_BUSINESS_ID)
_OTHER = str(OTHER_BUSINESS_ID)
_FAKE_UUID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

PROTECTED_ROUTES = [
    # Business
    ("GET",   f"/api/v1/business/{_BID}"),
    ("PATCH", f"/api/v1/business/{_BID}"),
    # Knowledge
    ("GET",  f"/api/v1/knowledge/{_BID}"),
    ("POST", f"/api/v1/knowledge/{_BID}"),
    ("GET",  f"/api/v1/knowledge/{_BID}/{_FAKE_UUID}"),
    # Agents
    ("GET",  f"/api/v1/agents/{_BID}"),
    ("POST", f"/api/v1/agents/{_BID}"),
    ("GET",  f"/api/v1/agents/{_BID}/{_FAKE_UUID}"),
    # Leads
    ("GET",   f"/api/v1/leads/{_BID}"),
    ("GET",   f"/api/v1/leads/{_BID}/{_FAKE_UUID}"),
    ("PATCH", f"/api/v1/leads/{_BID}/{_FAKE_UUID}"),
    # WhatsApp
    ("GET",  f"/api/v1/whatsapp/{_BID}/accounts"),
    ("GET",  f"/api/v1/whatsapp/{_BID}/conversations"),
]


@pytest.mark.parametrize("method,path", PROTECTED_ROUTES)
async def test_unauthenticated_returns_401(anon_client, method, path):
    response = await getattr(anon_client, method.lower())(path)
    assert response.status_code == 401, (
        f"{method} {path} should return 401 without auth, got {response.status_code}"
    )


# ---------------------------------------------------------------------------
# Cross-tenant access — 403 with a valid token for a different business
# ---------------------------------------------------------------------------

CROSS_TENANT_ROUTES = [
    ("GET",   f"/api/v1/business/{_OTHER}"),
    ("PATCH", f"/api/v1/business/{_OTHER}"),
    ("GET",   f"/api/v1/knowledge/{_OTHER}"),
    ("GET",   f"/api/v1/agents/{_OTHER}"),
    ("GET",   f"/api/v1/leads/{_OTHER}"),
    ("GET",   f"/api/v1/whatsapp/{_OTHER}/accounts"),
    ("GET",   f"/api/v1/whatsapp/{_OTHER}/conversations"),
]


@pytest.mark.parametrize("method,path", CROSS_TENANT_ROUTES)
async def test_cross_tenant_returns_403(auth_client, method, path):
    """A valid token for TEST_BUSINESS_ID must not access OTHER_BUSINESS_ID resources."""
    # PATCH endpoints require a body to pass FastAPI's request parsing — send `{}`
    # so the request reaches the auth check rather than short-circuiting at 422.
    kwargs = {"json": {}} if method == "PATCH" else {}
    response = await getattr(auth_client, method.lower())(path, **kwargs)
    assert response.status_code == 403, (
        f"{method} {path} should return 403 for wrong business, got {response.status_code}"
    )


# ---------------------------------------------------------------------------
# Public routes — no token needed
# ---------------------------------------------------------------------------


async def test_health_check_is_public(anon_client):
    response = await anon_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_webhook_get_without_token_requires_verify_token(anon_client):
    """Meta's handshake GET doesn't use JWT auth — it uses the hub.verify_token."""
    response = await anon_client.get("/webhooks/whatsapp")
    # Without hub.mode and hub.verify_token it returns 403 (bad handshake), not 401
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# forgot-password — redirect_to open-redirect guard (H2)
# ---------------------------------------------------------------------------


async def test_forgot_password_rejects_unknown_redirect_origin(anon_client):
    response = await anon_client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "user@example.com", "redirect_to": "https://evil.example/reset-password"},
    )
    assert response.status_code == 400


async def test_forgot_password_accepts_allowed_redirect_origin(anon_client):
    origin = settings.allowed_origins[0]
    with patch("app.services.auth_service.send_password_recovery_email", new_callable=AsyncMock) as mock_send:
        response = await anon_client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "user@example.com", "redirect_to": f"{origin}/reset-password"},
        )
    assert response.status_code == 200
    mock_send.assert_awaited_once()
