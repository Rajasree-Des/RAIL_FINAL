"""Encrypt/decrypt automation credentials and session state."""

import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings

logger = logging.getLogger(__name__)


def _derive_fernet_key(secret: str) -> bytes:
    digest = hashlib.sha256(secret.encode()).digest()
    return base64.urlsafe_b64encode(digest)


def _get_fernet() -> Fernet:
    key = settings.automation_encryption_key
    if not key:
        key = settings.jwt_secret_key
    return Fernet(_derive_fernet_key(key))


def encrypt_secret(plaintext: str) -> str:
    if not plaintext:
        return ""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> str:
    if not ciphertext:
        return ""
    try:
        return _get_fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as e:
        logger.error("Failed to decrypt automation secret")
        raise ValueError("Invalid encrypted credential") from e


def mask_secret(value: str) -> str:
    """Safe representation for logs/API — never expose passwords."""
    if not value:
        return ""
    if len(value) <= 4:
        return "****"
    return f"{value[:2]}****{value[-2:]}"
