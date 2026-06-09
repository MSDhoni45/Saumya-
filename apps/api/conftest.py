"""Root-level conftest: set required environment variables before any app imports.

pydantic-settings reads env at module import time, so these must be set
before `tests/conftest.py` loads the FastAPI app. A root conftest.py is
the standard pytest mechanism — it executes before every package-level conftest.
"""

import os

# Cryptography: TOKEN_ENCRYPTION_KEY must be a valid Fernet key (32 URL-safe
# base64 bytes → 44 chars). Value below is base64.urlsafe_b64encode(b"x" * 32).
_TEST_VARS: dict[str, str] = {
    "DATABASE_URL": "postgresql+asyncpg://test:test@localhost/test",
    "REDIS_URL": "redis://localhost:6379/15",
    "SUPABASE_URL": "http://localhost:54321",
    "SUPABASE_JWKS_URL": "http://localhost:54321/.well-known/jwks.json",
    "SUPABASE_JWT_ISSUER": "http://localhost:54321/auth/v1",
    "SUPABASE_ANON_KEY": "test-anon-key",
    "SUPABASE_SERVICE_ROLE_KEY": "test-service-role-key",
    "WHATSAPP_APP_ID": "test-app-id",
    "WHATSAPP_APP_SECRET": "test-app-secret-for-hmac-signing!!",
    "WHATSAPP_WEBHOOK_VERIFY_TOKEN": "test-verify-token",
    "TOKEN_ENCRYPTION_KEY": "eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eA==",
    "ENVIRONMENT": "test",
    "DEBUG": "false",
    "AUTH_COOKIE_SECURE": "false",
}

for _key, _value in _TEST_VARS.items():
    os.environ.setdefault(_key, _value)
