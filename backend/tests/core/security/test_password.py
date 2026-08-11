"""Tests for password hashing and verification."""

from app.core.security.password import password_hasher


def test_hash_and_verify_round_trip():
    hashed = password_hasher.hash("TestPass123")
    assert password_hasher.is_valid_hash_format(hashed)
    assert password_hasher.verify("TestPass123", hashed) is True
    assert password_hasher.verify("WrongPassword", hashed) is False


def test_is_valid_hash_format_rejects_plaintext():
    assert password_hasher.is_valid_hash_format("plaintext-password") is False
