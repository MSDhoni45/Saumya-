from functools import lru_cache

from cryptography.fernet import Fernet

from app.core.config import settings


@lru_cache
def _fernet() -> Fernet:
    return Fernet(settings.token_encryption_key.encode("utf-8"))


def encrypt_secret(plaintext: str) -> str:
    """Encrypt a secret (WhatsApp/Google access & refresh tokens) before storing it.

    Symmetric (Fernet/AES-128-CBC + HMAC) rather than hashing — these values
    must be recoverable to make outbound API calls on the tenant's behalf.
    """
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_secret(ciphertext: str) -> str:
    return _fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
