"""Tests for the WhatsApp webhook handler."""

import hashlib
import hmac
import json

import pytest

from app.core.config import settings


def _sign(body: bytes) -> str:
    digest = hmac.new(settings.whatsapp_app_secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


# ---------------------------------------------------------------------------
# Verification handshake (GET)
# ---------------------------------------------------------------------------


async def test_webhook_handshake_accepts_valid_token(anon_client):
    response = await anon_client.get(
        "/webhooks/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": settings.whatsapp_webhook_verify_token,
            "hub.challenge": "challenge123",
        },
    )
    assert response.status_code == 200
    assert response.text == "challenge123"


async def test_webhook_handshake_rejects_wrong_token(anon_client):
    response = await anon_client.get(
        "/webhooks/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong-token",
            "hub.challenge": "challenge123",
        },
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Inbound webhook (POST)
# ---------------------------------------------------------------------------


async def test_webhook_rejects_missing_signature(anon_client):
    response = await anon_client.post(
        "/webhooks/whatsapp",
        content=b'{"object":"whatsapp_business_account"}',
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 401


async def test_webhook_rejects_invalid_signature(anon_client):
    body = b'{"object":"whatsapp_business_account"}'
    response = await anon_client.post(
        "/webhooks/whatsapp",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": "sha256=deadbeef",
        },
    )
    assert response.status_code == 401


async def test_webhook_accepts_valid_but_unknown_object_type(anon_client):
    body = json.dumps({"object": "instagram", "entry": []}).encode()
    response = await anon_client.post(
        "/webhooks/whatsapp",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": _sign(body),
        },
    )
    # Valid signature — payload is ignored but we return 200 (not an error)
    assert response.status_code == 200
    assert response.json()["status"] == "ignored"


async def test_webhook_accepts_malformed_json_with_valid_signature(anon_client):
    body = b"not-json"
    response = await anon_client.post(
        "/webhooks/whatsapp",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": _sign(body),
        },
    )
    # Malformed JSON should return 200 "ignored" — never 4xx/5xx (would cause Meta retries)
    assert response.status_code == 200
    assert response.json()["status"] == "ignored"
