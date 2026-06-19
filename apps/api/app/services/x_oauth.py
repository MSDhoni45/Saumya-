"""X (Twitter) OAuth 2.0 PKCE helpers.

Public API:
  generate_authorize_url(business_id)     → {"url": str, "state": str}
  exchange_code_for_tokens(code, state)   → token dict + business_id
  refresh_access_token(refresh_token)     → token dict
"""

import base64
import hashlib
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx

from app.core.config import settings

_X_AUTH_URL = "https://twitter.com/i/oauth2/authorize"
_X_TOKEN_URL = "https://api.twitter.com/2/oauth2/token"
# Scopes required for posting, DMs, search, and offline refresh
_SCOPES = "tweet.read tweet.write users.read dm.read dm.write offline.access"
_STATE_TTL_SECONDS = 600  # 10 minutes to complete the OAuth dance


def _generate_code_verifier() -> str:
    """Random 86-char URL-safe base64 string — RFC 7636 §4.1."""
    return base64.urlsafe_b64encode(os.urandom(64)).rstrip(b"=").decode()


def _compute_code_challenge(verifier: str) -> str:
    """SHA-256 of verifier, base64url-encoded without padding — RFC 7636 §4.2."""
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def _callback_uri() -> str:
    base = (settings.app_frontend_url or "http://localhost:8000").rstrip("/")
    return f"{base}/api/v1/x/oauth/callback"


async def generate_authorize_url(business_id: uuid.UUID) -> dict[str, str]:
    """Build the PKCE authorization URL and persist state+verifier in Redis.

    Returns {"url": "https://twitter.com/...", "state": "<uuid>"}.
    The frontend should redirect the user's browser to `url`.
    """
    from redis.asyncio import Redis as AsyncRedis

    verifier = _generate_code_verifier()
    challenge = _compute_code_challenge(verifier)
    state = str(uuid.uuid4())

    redis = AsyncRedis.from_url(settings.redis_url, decode_responses=True)
    try:
        payload = json.dumps({"business_id": str(business_id), "code_verifier": verifier})
        await redis.setex(f"x:oauth:state:{state}", _STATE_TTL_SECONDS, payload)
    finally:
        await redis.aclose()

    params = {
        "response_type": "code",
        "client_id": settings.x_client_id,
        "redirect_uri": _callback_uri(),
        "scope": _SCOPES,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    return {"url": f"{_X_AUTH_URL}?{urlencode(params)}", "state": state}


async def exchange_code_for_tokens(code: str, state: str) -> dict:
    """Exchange a callback authorization code for access + refresh tokens.

    Reads and deletes the Redis state entry (one-time use).
    Returns the token response enriched with `business_id` and `token_expires_at`.
    Raises ValueError on state mismatch or X API failure.
    """
    from redis.asyncio import Redis as AsyncRedis

    redis = AsyncRedis.from_url(settings.redis_url, decode_responses=True)
    try:
        raw = await redis.get(f"x:oauth:state:{state}")
        if raw is None:
            raise ValueError("OAuth state not found or expired — restart the connect flow")
        await redis.delete(f"x:oauth:state:{state}")
        stored = json.loads(raw)
    finally:
        await redis.aclose()

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            _X_TOKEN_URL,
            data={
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": _callback_uri(),
                "code_verifier": stored["code_verifier"],
            },
            auth=(settings.x_client_id or "", settings.x_client_secret or ""),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    if resp.is_error:
        raise ValueError(f"X token exchange failed ({resp.status_code}): {resp.text}")

    tokens: dict = resp.json()
    tokens["business_id"] = stored["business_id"]
    tokens["token_expires_at"] = (
        datetime.now(tz=timezone.utc) + timedelta(seconds=tokens.get("expires_in", 7200))
    ).isoformat()
    return tokens


async def refresh_access_token(refresh_token: str) -> dict:
    """Refresh an expiring access token. Returns the new token response dict."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            _X_TOKEN_URL,
            data={"grant_type": "refresh_token", "refresh_token": refresh_token},
            auth=(settings.x_client_id or "", settings.x_client_secret or ""),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    if resp.is_error:
        raise ValueError(f"X token refresh failed ({resp.status_code}): {resp.text}")
    return resp.json()
