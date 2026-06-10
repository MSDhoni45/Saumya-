import hashlib
import hmac
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import urlparse

import jwt
from jwt import PyJWKClient

from app.core.config import settings


class TokenError(Exception):
    """Raised when a bearer token fails signature/claim validation. Maps to a 401."""


@dataclass(frozen=True, slots=True)
class TokenClaims:
    user_id: str
    email: str | None


@lru_cache
def _jwks_client() -> PyJWKClient:
    # Cached for process lifetime: PyJWKClient fetches the JWKS lazily on
    # first use and re-fetches automatically on a `kid` it doesn't recognize
    # (covers Supabase's periodic key rotation) — no per-request network call
    # in the steady state.
    return PyJWKClient(settings.supabase_jwks_url)


def decode_access_token(token: str) -> TokenClaims:
    """Validate a Supabase-issued access token and extract identity claims.

    Verifies signature (against Supabase's published JWKS), expiry, issuer,
    and audience — the full set of checks recommended for resource servers
    that only consume tokens (never mint or refresh them themselves).
    """
    try:
        signing_key = _jwks_client().get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256", "ES256"],
            audience=settings.supabase_jwt_audience,
            issuer=settings.supabase_jwt_issuer,
        )
    except jwt.PyJWTError as exc:
        raise TokenError(f"Invalid or expired access token: {exc}") from exc

    user_id = payload.get("sub")
    if not user_id:
        raise TokenError("Access token is missing the 'sub' claim")

    return TokenClaims(user_id=user_id, email=payload.get("email"))


def verify_whatsapp_webhook_signature(payload: bytes, signature_header: str | None) -> bool:
    """Verify Meta's `X-Hub-Signature-256` header against the raw request body.

    Meta signs the raw payload bytes with the app secret (HMAC-SHA256) and sends
    the hex digest prefixed with ``sha256=``. Comparison must be constant-time to
    avoid timing side-channels, and must run against the *raw* bytes — any
    re-serialization (e.g. parsing then re-dumping JSON) would change the digest.
    """
    if not signature_header or not signature_header.startswith("sha256="):
        return False

    expected_digest = signature_header.removeprefix("sha256=")
    computed_digest = hmac.new(
        key=settings.whatsapp_app_secret.encode("utf-8"),
        msg=payload,
        digestmod=hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected_digest, computed_digest)


def verify_whatsapp_webhook_handshake(mode: str | None, token: str | None) -> bool:
    """Validate the GET verification handshake Meta performs when registering a webhook."""
    return mode == "subscribe" and token == settings.whatsapp_webhook_verify_token


@lru_cache
def _allowed_redirect_origins() -> frozenset[str]:
    origins = {origin.rstrip("/") for origin in settings.allowed_origins}
    if settings.app_frontend_url:
        origins.add(settings.app_frontend_url.rstrip("/"))
    return frozenset(origins)


def is_allowed_redirect_url(url: str) -> bool:
    """Reject password-recovery `redirect_to` URLs that don't point at a known frontend origin.

    Supabase forwards this URL verbatim into the recovery email link — without
    an allow-list check, an attacker could pass `redirect_to=https://evil.example`
    and phish users via a legitimate-looking password reset email (open redirect).
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return False
    origin = f"{parsed.scheme}://{parsed.netloc}"
    return origin in _allowed_redirect_origins()
