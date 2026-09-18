import warnings
from functools import lru_cache

from cryptography.fernet import Fernet

from app.config import get_settings


@lru_cache
def _get_fernet() -> Fernet:
    key = get_settings().session_encryption_key
    if not key:
        warnings.warn(
            "SESSION_ENCRYPTION_KEY is not set -- generating a random per-process key. "
            "This is fine for local dev, but every stored GitHub token becomes "
            "unreadable (and every session invalid) on restart. Set a persistent "
            "key for any real deployment.",
            stacklevel=2,
        )
        key = Fernet.generate_key().decode()
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_token(access_token: str) -> bytes:
    return _get_fernet().encrypt(access_token.encode())


def decrypt_token(encrypted: bytes) -> str:
    return _get_fernet().decrypt(encrypted).decode()
