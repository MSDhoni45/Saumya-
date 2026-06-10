"""Unit tests for app/core/security.py — pure functions, no HTTP or DB."""

import hashlib
import hmac
from unittest.mock import MagicMock, patch

import jwt
import pytest

from app.core.config import settings
from app.core.security import (
    TokenClaims,
    TokenError,
    decode_access_token,
    is_allowed_redirect_url,
    verify_whatsapp_webhook_handshake,
    verify_whatsapp_webhook_signature,
)


# ---------------------------------------------------------------------------
# decode_access_token
# ---------------------------------------------------------------------------


def _make_signing_key_mock(payload: dict) -> MagicMock:
    """Return a mock that mimics PyJWKClient.get_signing_key_from_jwt."""
    key_mock = MagicMock()
    key_mock.key = "test-secret"
    return key_mock


def test_decode_access_token_returns_claims():
    claims_payload = {"sub": "user-uuid-123", "email": "dev@example.com"}
    with (
        patch("app.core.security._jwks_client") as mock_client_fn,
        patch("jwt.decode", return_value=claims_payload),
    ):
        mock_client_fn.return_value.get_signing_key_from_jwt.return_value = _make_signing_key_mock(claims_payload)
        result = decode_access_token("any.token.here")

    assert isinstance(result, TokenClaims)
    assert result.user_id == "user-uuid-123"
    assert result.email == "dev@example.com"


def test_decode_access_token_missing_sub_raises():
    with (
        patch("app.core.security._jwks_client") as mock_client_fn,
        patch("jwt.decode", return_value={"email": "x@y.com"}),
    ):
        mock_client_fn.return_value.get_signing_key_from_jwt.return_value = _make_signing_key_mock({})
        with pytest.raises(TokenError, match="sub"):
            decode_access_token("any.token.here")


def test_decode_access_token_expired_raises():
    with (
        patch("app.core.security._jwks_client") as mock_client_fn,
        patch("jwt.decode", side_effect=jwt.ExpiredSignatureError("expired")),
    ):
        mock_client_fn.return_value.get_signing_key_from_jwt.return_value = _make_signing_key_mock({})
        with pytest.raises(TokenError):
            decode_access_token("any.token.here")


# ---------------------------------------------------------------------------
# verify_whatsapp_webhook_signature
# ---------------------------------------------------------------------------


def _make_signature(body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def test_valid_webhook_signature_accepted():
    body = b'{"object":"test"}'
    sig = _make_signature(body, settings.whatsapp_app_secret)
    assert verify_whatsapp_webhook_signature(body, sig) is True


def test_tampered_body_rejected():
    body = b'{"object":"test"}'
    sig = _make_signature(body, settings.whatsapp_app_secret)
    assert verify_whatsapp_webhook_signature(b'{"object":"tampered"}', sig) is False


def test_wrong_secret_rejected():
    body = b'{"object":"test"}'
    sig = _make_signature(body, "wrong-secret")
    assert verify_whatsapp_webhook_signature(body, sig) is False


def test_missing_signature_header_rejected():
    assert verify_whatsapp_webhook_signature(b"body", None) is False


def test_malformed_signature_prefix_rejected():
    body = b"body"
    bad_sig = "md5=" + hmac.new(settings.whatsapp_app_secret.encode(), body, hashlib.sha256).hexdigest()
    assert verify_whatsapp_webhook_signature(body, bad_sig) is False


# ---------------------------------------------------------------------------
# verify_whatsapp_webhook_handshake
# ---------------------------------------------------------------------------


def test_valid_handshake_accepted():
    assert verify_whatsapp_webhook_handshake("subscribe", settings.whatsapp_webhook_verify_token) is True


def test_wrong_mode_rejected():
    assert verify_whatsapp_webhook_handshake("unsubscribe", settings.whatsapp_webhook_verify_token) is False


def test_wrong_token_rejected():
    assert verify_whatsapp_webhook_handshake("subscribe", "wrong-token") is False


def test_none_inputs_rejected():
    assert verify_whatsapp_webhook_handshake(None, None) is False


# ---------------------------------------------------------------------------
# is_allowed_redirect_url
# ---------------------------------------------------------------------------


def test_allowed_origin_accepted():
    origin = settings.allowed_origins[0]
    assert is_allowed_redirect_url(f"{origin}/reset-password") is True


def test_allowed_origin_with_trailing_slash_accepted():
    origin = settings.allowed_origins[0].rstrip("/")
    assert is_allowed_redirect_url(f"{origin}/") is True


def test_unknown_origin_rejected():
    assert is_allowed_redirect_url("https://evil.example/reset-password") is False


def test_protocol_relative_url_rejected():
    # //evil.example resolves to scheme-relative absolute URL in browsers
    assert is_allowed_redirect_url("//evil.example/reset-password") is False


def test_javascript_scheme_rejected():
    assert is_allowed_redirect_url("javascript:alert(1)") is False


def test_origin_lookalike_subdomain_rejected():
    origin = settings.allowed_origins[0]
    parsed_host = origin.split("://", 1)[1]
    assert is_allowed_redirect_url(f"https://evil-{parsed_host}/reset") is False


def test_path_only_url_rejected():
    assert is_allowed_redirect_url("/reset-password") is False


def test_malformed_url_rejected():
    assert is_allowed_redirect_url("http://[invalid") is False
