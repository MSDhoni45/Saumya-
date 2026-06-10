"""Unit tests for app/core/config.py — settings validation."""

from cryptography.fernet import Fernet
from pydantic import ValidationError
import pytest

from app.core.config import Settings


def test_valid_fernet_key_accepted():
    valid_key = Fernet.generate_key().decode()
    settings = Settings(token_encryption_key=valid_key)
    assert settings.token_encryption_key == valid_key


@pytest.mark.parametrize(
    "bad_key",
    [
        "not-a-valid-key",
        "",
        "short",
        "x" * 44,  # right length, but not valid base64/Fernet bytes
    ],
)
def test_invalid_fernet_key_rejected_at_startup(bad_key):
    with pytest.raises(ValidationError, match="TOKEN_ENCRYPTION_KEY must be a valid Fernet key"):
        Settings(token_encryption_key=bad_key)
