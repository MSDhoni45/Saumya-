import hashlib
import hmac

from app.core.config import settings


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
